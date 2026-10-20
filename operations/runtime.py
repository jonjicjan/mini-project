"""One Windows supervisor owns Waitress, Caddy and the daily backup schedule."""

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .backups import create_backup, digest, host_lock, prune_backups, validate_backup


def runtime_config(data_dir):
    root = Path(data_dir).resolve(strict=True)
    config = json.loads((root / "runtime.json").read_text(encoding="utf-8-sig"))
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", config["hostname"]):
        raise ValueError("Use a hostname or IPv4 address without a scheme, port or path.")
    for key in ("http_port", "https_port"):
        if type(config[key]) is not int or not 1024 <= config[key] <= 65535:
            raise ValueError("Ports must be integers between 1024 and 65535.")
    if config["http_port"] == config["https_port"]:
        raise ValueError("HTTP and HTTPS ports must differ.")
    address = ipaddress.ip_address(config["bind_address"])
    if (
        not address.is_private
        or address.is_unspecified
        or address.is_multicast
        or address.version != 4
    ):
        raise ValueError("Bind HTTPS to a specific private or loopback IPv4 address.")
    binary = Path(config["caddy_path"]).resolve(strict=True)
    if digest(binary).lower() != config["caddy_sha256"].lower():
        raise ValueError("Caddy checksum changed. Verify the approved binary before starting.")
    if len((root / "secret.key").read_text().strip()) < 50:
        raise ValueError("The installation secret is missing or too short.")
    if not (root / "register.sqlite3").is_file() or not (root / "static").is_dir():
        raise ValueError("Run setup, migrations and collectstatic first.")
    config["data_dir"] = str(root)
    config["caddy_path"] = str(binary)
    return config


def environment(config):
    root = Path(config["data_dir"])
    return os.environ | {
        "REGISTER_ENV": "production",
        "REGISTER_DATA_DIR": str(root),
        "REGISTER_SECRET_KEY": (root / "secret.key").read_text().strip(),
        "REGISTER_ALLOWED_HOSTS": config["hostname"],
        "REGISTER_TRUST_PROXY": "1",
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "PYTHONUNBUFFERED": "1",
        "XDG_DATA_HOME": str(root / "caddy-data"),
        "XDG_CONFIG_HOME": str(root / "caddy-config"),
    }


def daily_backup(root, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    directory = root / "backups"
    for path in sorted(directory.glob(f"register-{now.strftime('%Y%m%d')}T*.zip"), reverse=True):
        try:
            validate_backup(path)
            return None
        except (OSError, ValueError):
            continue
    result = create_backup(data_dir=root, destination=directory, now=now)
    prune_backups(directory, keep_daily=30)
    return result


def caddyfile(config):
    # JSON quoting also safely quotes literal Windows paths in Caddyfile strings.
    static = json.dumps((Path(config["data_dir"]) / "static").as_posix())
    return (
        "{\n  admin off\n  auto_https disable_redirects\n}\n"
        f"https://{config['hostname']}:{config['https_port']} {{\n"
        f"  bind {config['bind_address']}\n  tls internal\n"
        f"  handle_path /static/* {{\n    root * {static}\n    file_server\n  }}\n"
        f"  handle {{\n    reverse_proxy 127.0.0.1:{config['http_port']}\n  }}\n}}\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--worker", action="store_true")
    options = parser.parse_args(argv)
    config = runtime_config(options.data_dir)
    root = Path(config["data_dir"])
    if options.stop:
        (root / "stop.request").write_text("stop", encoding="utf-8")
        return 0
    os.environ.update(environment(config))
    if options.worker:
        from waitress import serve

        from config.wsgi import application

        serve(
            application,
            host="127.0.0.1",
            port=config["http_port"],
            threads=4,
            trusted_proxy="127.0.0.1",
            trusted_proxy_count=1,
            trusted_proxy_headers={"x-forwarded-for", "x-forwarded-proto", "x-forwarded-host"},
            clear_untrusted_proxy_headers=True,
        )
        return 0
    with host_lock(root):
        if (root / "maintenance.flag").exists():
            raise RuntimeError("Maintenance flag exists. Finish maintenance before starting.")
        daily_backup(root)
        (root / "stop.request").unlink(missing_ok=True)
        config_path = root / "Caddyfile"
        config_path.write_text(caddyfile(config), encoding="utf-8")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        processes = []
        logs = root / "logs"
        logs.mkdir(exist_ok=True)
        with (logs / "runtime.log").open("a", encoding="utf-8") as log:
            try:
                for command in (
                    [
                        sys.executable,
                        "-m",
                        "operations.runtime",
                        "--data-dir",
                        str(root),
                        "--worker",
                    ],
                    [
                        config["caddy_path"],
                        "run",
                        "--config",
                        str(config_path),
                        "--adapter",
                        "caddyfile",
                    ],
                ):
                    processes.append(
                        subprocess.Popen(
                            command,
                            cwd=Path(__file__).resolve().parents[1],
                            env=environment(config),
                            stdout=log,
                            stderr=log,
                            creationflags=flags,
                        )
                    )
                print(
                    f"Faculty Register: https://{config['hostname']}:{config['https_port']}/",
                    flush=True,
                )
                next_backup = time.monotonic() + 60
                while not (root / "stop.request").exists():
                    if any(p.poll() is not None for p in processes):
                        raise RuntimeError(
                            "A server process stopped. See the installation runtime log."
                        )
                    if time.monotonic() >= next_backup:
                        try:
                            daily_backup(root)
                        except (OSError, ValueError, RuntimeError) as error:
                            log.write(
                                f"Backup failed: {type(error).__name__}. Check storage and backup status.\n"
                            )
                            log.flush()
                        next_backup = time.monotonic() + 60
                    time.sleep(1)
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                for process in processes:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                (root / "stop.request").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
