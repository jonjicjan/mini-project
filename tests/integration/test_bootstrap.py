from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def test_bootstrap_prompts_and_creates_only_initial_admin(monkeypatch):
    inputs = iter(["college-admin", "College Administrator"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda prompt: "Synthetic-bootstrap-secret-73")
    output = StringIO()
    call_command("bootstrap_admin", stdout=output)
    user = get_user_model().objects.get(username="college-admin")
    assert user.is_superuser
    assert user.check_password("Synthetic-bootstrap-secret-73")
    assert "secret-73" not in output.getvalue()
    with pytest.raises(CommandError, match="already exists"):
        call_command("bootstrap_admin", stdout=output)
    call_command("bootstrap_admin", if_missing=True, stdout=output)
    assert get_user_model().objects.filter(is_superuser=True).count() == 1


def test_bootstrap_rejects_mismatched_passwords(monkeypatch):
    inputs = iter(["college-admin", "College Administrator"])
    passwords = iter(["Synthetic-bootstrap-secret-73", "Different-secret-74"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(passwords))
    with pytest.raises(CommandError, match="do not match"):
        call_command("bootstrap_admin", stdout=StringIO())
    assert not get_user_model().objects.exists()
