"""Tests never open the development or installation database."""

import os
import tempfile
from pathlib import Path

os.environ["REGISTER_ENV"] = "development"
os.environ["REGISTER_DATA_DIR"] = tempfile.mkdtemp(prefix="register-tests-")
os.environ["REGISTER_SECRET_KEY"] = "synthetic-test-key-" * 5
os.environ["REGISTER_ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"
# The suite runs on its own throwaway SQLite file, never the configured server.
os.environ.pop("REGISTER_DATABASE_URL", None)
from .settings import *  # noqa: E402,F403

DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": str(Path(os.environ["REGISTER_DATA_DIR"]) / "test.sqlite3")
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
