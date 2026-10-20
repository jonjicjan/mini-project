import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZipFile

import pytest
from django.db import connection
from django.urls import reverse

from operations.backups import (
    create_backup,
    host_lock,
    prune_backups,
    restore_backup,
    validate_backup,
)
from operations.runtime import daily_backup, runtime_config

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def installation(tmp_path, register):
    root = tmp_path / "data"
    root.mkdir()
    with closing(sqlite3.connect(root / "register.sqlite3")) as destination:
        connection.connection.backup(destination)
    return root


def test_backup_restore_integrity_recovery_and_sessions(installation, tmp_path):
    archive = create_backup(data_dir=installation, destination=tmp_path / "backups")
    assert validate_backup(archive)["integrity"] == "ok"
    with closing(sqlite3.connect(installation / "register.sqlite3")) as conn:
        original = conn.execute("SELECT subject_name FROM registers_register").fetchone()[0]
        conn.execute("UPDATE registers_register SET subject_name='Changed'")
        conn.execute("INSERT INTO django_session VALUES ('example','data','2099-01-01')")
        conn.commit()
    with pytest.raises(ValueError):
        restore_backup(archive=archive, data_dir=installation)
    result = restore_backup(archive=archive, data_dir=installation, maintenance=True)
    assert Path(result["recovery"]).is_file()
    assert validate_backup(result["recovery"])["integrity"] == "ok"
    with closing(sqlite3.connect(installation / "register.sqlite3")) as conn:
        assert conn.execute("SELECT subject_name FROM registers_register").fetchone()[0] == original
        assert conn.execute("SELECT count(*) FROM django_session").fetchone()[0] == 0


def test_corrupt_unsafe_backups_and_running_server_leave_database_intact(installation, tmp_path):
    archive = create_backup(data_dir=installation, destination=tmp_path / "backups")
    original = (installation / "register.sqlite3").read_bytes()
    with host_lock(installation):
        with pytest.raises(RuntimeError):
            restore_backup(archive=archive, data_dir=installation, maintenance=True)
    malicious = tmp_path / "bad.zip"
    with ZipFile(malicious, "w") as zipped:
        zipped.writestr("../register.sqlite3", "bad")
        zipped.writestr("manifest.json", "{}")
    with pytest.raises(ValueError):
        restore_backup(archive=malicious, data_dir=installation, maintenance=True)
    assert (installation / "register.sqlite3").read_bytes() == original
    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(b"not a zip")
    with pytest.raises(ValueError):
        validate_backup(corrupt)


def test_failed_replace_keeps_current_database(installation, tmp_path, monkeypatch):
    archive = create_backup(data_dir=installation, destination=tmp_path / "backups")
    original = (installation / "register.sqlite3").read_bytes()
    import operations.backups as backups

    replace = backups.os.replace

    def locked(source, target):
        if Path(target).name == "register.sqlite3":
            raise PermissionError("File held open")
        replace(source, target)

    monkeypatch.setattr(backups.os, "replace", locked)
    with pytest.raises(PermissionError):
        restore_backup(archive=archive, data_dir=installation, maintenance=True)
    assert (installation / "register.sqlite3").read_bytes() == original
    assert not (installation / "maintenance.flag").exists()


def test_missed_daily_backup_and_retention(installation):
    now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    assert daily_backup(installation, now)
    assert daily_backup(installation, now) is None
    create_backup(
        data_dir=installation, destination=installation / "backups", now=now - timedelta(days=1)
    )
    create_backup(
        data_dir=installation, destination=installation / "backups", now=now - timedelta(days=2)
    )
    assert len(prune_backups(installation / "backups", keep_daily=2)) == 1


def test_faculty_cannot_access_system_backups(client, faculty):
    client.force_login(faculty)
    assert client.get(reverse("backups")).status_code == 404
    assert client.post(reverse("backups")).status_code == 404
    assert client.get(reverse("backup-download", args=["register-example.zip"])).status_code == 404


def test_runtime_refuses_invalid_hosts_ports_and_binary(installation):
    (installation / "secret.key").write_text("synthetic-only-" * 6)
    config = {
        "hostname": "bad/host",
        "http_port": 8000,
        "https_port": 8443,
        "bind_address": "127.0.0.1",
        "caddy_path": "missing",
        "caddy_sha256": "invalid",
    }
    (installation / "runtime.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match="hostname"):
        runtime_config(installation)
    config["hostname"], config["http_port"] = "localhost", 8443
    (installation / "runtime.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match="differ"):
        runtime_config(installation)
