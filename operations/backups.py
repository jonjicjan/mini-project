"""Online backups of the register database.

SQLite installations copy the live database file atomically. PostgreSQL
installations serialise every table with Django's serializer, because the
database server holds the data instead of a file. Issued Word files live in the
database, so both kinds of archive contain them.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from django.apps import apps
from django.core import serializers
from django.core.management import call_command
from django.core.management.color import no_style
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder

FORMAT_VERSION = 1
SQLITE_MEMBER = "database.sqlite3"
POSTGRES_MEMBER = "database.json"
ALLOWED_FILES = {SQLITE_MEMBER, POSTGRES_MEMBER, "manifest.json"}


def uses_postgres():
    return connection.vendor == "postgresql"


def applied_migrations():
    return sorted([list(key) for key in MigrationRecorder(connection).applied_migrations()])


def write_json_dump(path):
    records = []
    for model in apps.get_models():
        if model._meta.app_label == "sessions":
            continue
        records.extend(json.loads(serializers.serialize("json", model._default_manager.all())))
    Path(path).write_text(
        json.dumps({"migrations": applied_migrations(), "records": records}), encoding="utf-8"
    )


def json_dump_info(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    records = document["records"]
    if not isinstance(records, list):
        raise ValueError("Backup does not contain serialised records.")
    return {
        "integrity": "ok",
        "migrations": sorted([list(entry) for entry in document["migrations"]]),
        "records": len(records),
    }


def truncate_all():
    style = no_style()
    tables = connection.introspection.django_table_names(only_existing=True, include_views=False)
    statements = connection.ops.sql_flush(style, tables, reset_sequences=True, allow_cascade=True)
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def reset_sequences():
    with connection.cursor() as cursor:
        for statement in connection.ops.sequence_reset_sql(no_style(), apps.get_models()):
            cursor.execute(statement)


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
    destination.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    name = f"register-{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}.zip"
    target = destination / name
    with tempfile.TemporaryDirectory(prefix="backup-", dir=destination) as temp:
        if uses_postgres():
            member = POSTGRES_MEMBER
            payload = Path(temp) / member
            write_json_dump(payload)
            info = json_dump_info(payload)
        else:
            member = SQLITE_MEMBER
            database = data_dir / "register.sqlite3"
            if not database.is_file():
                raise ValueError("No register database exists in the selected data directory.")
            payload = Path(temp) / member
            started = time.monotonic()

            def progress(status, remaining, total):
                if time.monotonic() - started > 60:
                    raise TimeoutError("Backup timed out waiting for database access.")

            with closing(
                sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
            ) as source:
                with closing(sqlite3.connect(payload)) as output:
                    source.backup(output, pages=256, progress=progress, sleep=0.05)
            info = database_info(payload)
        manifest = {
            "format_version": FORMAT_VERSION,
            "application": "faculty-register",
            "engine": connection.vendor,
            "database_member": member,
            "created_at": now.isoformat(),
            "database_sha256": digest(payload),
            **info,
        }
        partial = Path(temp) / "archive.partial"
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(payload, member)
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        validate_backup(partial)
        os.replace(partial, target)
    return target


def validate_backup(path):
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != 2 or "manifest.json" not in names:
                raise ValueError("Unexpected or unsafe paths in backup archive.")
            manifest = json.loads(archive.read("manifest.json"))
            member = manifest.get("database_member")
            if member is None:
                member = SQLITE_MEMBER if SQLITE_MEMBER in names else None
            if member not in ALLOWED_FILES or set(names) != {member, "manifest.json"}:
                raise ValueError("Unexpected or unsafe paths in backup archive.")
            if (
                archive.getinfo("manifest.json").file_size > 2_000_000
                or archive.getinfo(member).file_size > 2_000_000_000
            ):
                raise ValueError("Backup exceeds the supported validation size.")
            if (
                manifest.get("format_version") != FORMAT_VERSION
                or manifest.get("application") != "faculty-register"
            ):
                raise ValueError("Unsupported backup version or application.")
            with tempfile.TemporaryDirectory(prefix="verify-register-") as temp:
                database = Path(temp) / member
                with archive.open(member) as source, database.open("wb") as output:
                    shutil.copyfileobj(source, output)
                if digest(database) != manifest["database_sha256"]:
                    raise ValueError("Backup checksum does not match.")
                info = (
                    database_info(database) if member == SQLITE_MEMBER else json_dump_info(database)
                )
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
    if uses_postgres():
        return restore_postgres(archive=archive, manifest=manifest, data_dir=data_dir)
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


def restore_postgres(*, archive, manifest, data_dir):
    with host_lock(data_dir):
        marker = data_dir / "maintenance.flag"
        marker.write_text("Restore in progress", encoding="utf-8")
        try:
            if applied_migrations() != manifest["migrations"]:
                raise ValueError(
                    "Backup schema differs from this installation. Restore into a matching isolated installation first."
                )
            recovery = create_backup(data_dir=data_dir, destination=data_dir / "recovery")
            with tempfile.TemporaryDirectory(prefix="restore-", dir=data_dir) as temp:
                staged = Path(temp) / POSTGRES_MEMBER
                with (
                    zipfile.ZipFile(archive) as source,
                    source.open(POSTGRES_MEMBER) as incoming,
                    staged.open("wb") as output,
                ):
                    shutil.copyfileobj(incoming, output)
                records = Path(temp) / "records.json"
                records.write_text(
                    json.dumps(json.loads(staged.read_text(encoding="utf-8"))["records"]),
                    encoding="utf-8",
                )
                # One transaction: a failed load leaves the existing register untouched.
                with transaction.atomic():
                    truncate_all()
                    call_command("loaddata", str(records), verbosity=0)
                    reset_sequences()
            return {
                "restored": f"postgresql:{connection.settings_dict['NAME']}",
                "recovery": str(recovery),
            }
        finally:
            marker.unlink(missing_ok=True)
