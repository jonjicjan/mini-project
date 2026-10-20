"""Online SQLite backups. Issued Word files live in SQLite and are included atomically."""

import hashlib
import json
import os
import sqlite3
import tempfile
import time
import uuid
import zipfile
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

FORMAT_VERSION = 1
ALLOWED_FILES = {"database.sqlite3", "manifest.json"}


@contextmanager
def host_lock(data_dir):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    stream = (data_dir / "runtime.lock").open("a+b")
    stream.seek(0)
    if os.fstat(stream.fileno()).st_size == 0:
        stream.write(b"0")
        stream.flush()
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise RuntimeError(
            "The application is running or another maintenance process holds its lock."
        ) from None
    try:
        yield
    finally:
        stream.seek(0)
        if os.name == "nt":
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def database_info(path):
    with closing(
        sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
    ) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup database failed integrity checks.")
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not {"django_migrations", "accounts_user", "registers_register"} <= tables:
            raise ValueError("This is not a Faculty Register database.")
        migrations = sorted(
            [list(row) for row in connection.execute("SELECT app,name FROM django_migrations")]
        )
    return {"integrity": "ok", "migrations": migrations}


def create_backup(*, data_dir, destination, now=None):
    data_dir, destination = Path(data_dir), Path(destination)
    database = data_dir / "register.sqlite3"
    if not database.is_file():
        raise ValueError("No register database exists in the selected data directory.")
    destination.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    name = f"register-{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}.zip"
    target = destination / name
    with tempfile.TemporaryDirectory(prefix="backup-", dir=destination) as temp:
        copied = Path(temp) / "database.sqlite3"
        started = time.monotonic()

        def progress(status, remaining, total):
            if time.monotonic() - started > 60:
                raise TimeoutError("Backup timed out waiting for database access.")

        with closing(sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(copied)) as output:
                source.backup(output, pages=256, progress=progress, sleep=0.05)
        info = database_info(copied)
        manifest = {
            "format_version": FORMAT_VERSION,
            "application": "faculty-register",
            "created_at": now.isoformat(),
            "database_sha256": digest(copied),
            **info,
        }
        partial = Path(temp) / "archive.partial"
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(copied, "database.sqlite3")
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        validate_backup(partial)
        os.replace(partial, target)
    return target


def validate_backup(path):
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != 2 or set(names) != ALLOWED_FILES:
                raise ValueError("Unexpected or unsafe paths in backup archive.")
            if (
                archive.getinfo("manifest.json").file_size > 2_000_000
                or archive.getinfo("database.sqlite3").file_size > 2_000_000_000
            ):
                raise ValueError("Backup exceeds the supported validation size.")
            manifest = json.loads(archive.read("manifest.json"))
            if (
                manifest.get("format_version") != FORMAT_VERSION
                or manifest.get("application") != "faculty-register"
            ):
                raise ValueError("Unsupported backup version or application.")
            with tempfile.TemporaryDirectory(prefix="verify-register-") as temp:
                database = Path(temp) / "database.sqlite3"
                with archive.open("database.sqlite3") as source, database.open("wb") as output:
                    import shutil

                    shutil.copyfileobj(source, output)
                if digest(database) != manifest["database_sha256"]:
                    raise ValueError("Backup checksum does not match.")
                info = database_info(database)
                if info["migrations"] != manifest["migrations"]:
                    raise ValueError("Backup migration manifest does not match its database.")
            return manifest
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, sqlite3.Error) as error:
        raise ValueError("Invalid or damaged backup archive.") from error


def prune_backups(directory, *, keep_daily=30):
    if keep_daily < 1:
        raise ValueError("Retain at least one daily backup.")
    by_day = {}
    for path in sorted(Path(directory).glob("register-*.zip"), reverse=True):
        try:
            manifest = validate_backup(path)
        except (ValueError, OSError):
            continue
        by_day.setdefault(manifest["created_at"][:10], []).append(path)
    removed = []
    for day in sorted(by_day, reverse=True)[keep_daily:]:
        for path in by_day[day]:
            path.unlink()
            removed.append(path)
    return removed


def restore_backup(*, archive, data_dir, maintenance=False):
    if not maintenance:
        raise ValueError("Stop the application and explicitly select maintenance mode.")
    data_dir = Path(data_dir)
    manifest = validate_backup(archive)
    with host_lock(data_dir):
        marker = data_dir / "maintenance.flag"
        marker.write_text("Restore in progress", encoding="utf-8")
        try:
            database = data_dir / "register.sqlite3"
            if database.exists():
                current = database_info(database)
                if current["migrations"] != manifest["migrations"]:
                    raise ValueError(
                        "Backup schema differs from this installation. Restore into a matching isolated installation first."
                    )
                recovery = create_backup(data_dir=data_dir, destination=data_dir / "recovery")
            else:
                recovery = None
            with tempfile.TemporaryDirectory(prefix="restore-", dir=data_dir) as temp:
                staged = Path(temp) / "restored.sqlite3"
                with (
                    zipfile.ZipFile(archive) as source,
                    source.open("database.sqlite3") as incoming,
                    staged.open("wb") as output,
                ):
                    import shutil

                    shutil.copyfileobj(incoming, output)
                with closing(sqlite3.connect(staged)) as connection:
                    connection.execute("DELETE FROM django_session")
                    connection.commit()
                database_info(staged)
                # The supervisor lock guarantees no application process is using the DB.
                # Refuse WAL sidecars instead of discarding possibly uncheckpointed data.
                if any(Path(str(database) + suffix).exists() for suffix in ("-wal", "-shm")):
                    raise RuntimeError(
                        "Database WAL files remain. Stop all database users and checkpoint before restoring."
                    )
                os.replace(staged, database)
            return {"restored": str(database), "recovery": str(recovery) if recovery else None}
        finally:
            marker.unlink(missing_ok=True)
