from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

pytestmark = pytest.mark.django_db


def test_login_and_logout_are_protected(client, faculty):
    assert client.get("/").status_code == 302
    assert (
        client.post("/login/", {"username": "teacher1", "password": "incorrect"}).status_code == 200
    )
    assert (
        client.post(
            "/login/", {"username": "TEACHER1", "password": "Synthetic-passphrase-47"}
        ).status_code
        == 302
    )
    assert client.get("/").status_code == 200
    assert client.get("/logout/").status_code == 405
    assert client.post("/logout/").status_code == 302
    assert client.get("/").status_code == 302


def test_faculty_cannot_administer_accounts(client, faculty):
    client.force_login(faculty)
    assert client.get("/admin/faculty/").status_code == 403
    assert client.post("/admin/faculty/", {}).status_code == 403


def test_csrf_is_required(faculty):
    client = Client(enforce_csrf_checks=True)
    assert (
        client.post(
            "/login/", {"username": "teacher1", "password": "Synthetic-passphrase-47"}
        ).status_code
        == 403
    )


def test_login_throttle_username_and_address(client, faculty):
    for _ in range(5):
        client.post("/login/", {"username": "teacher1", "password": "wrong"})
    response = client.post(
        "/login/", {"username": "teacher1", "password": "Synthetic-passphrase-47"}
    )
    assert response.status_code == 429
    assert client.post("/login/", {"username": "new-name", "password": "wrong"}).status_code == 429
    assert (
        Client(REMOTE_ADDR="127.0.0.2")
        .post("/login/", {"username": "teacher1", "password": "Synthetic-passphrase-47"})
        .status_code
        == 429
    )


def test_admin_create_reset_disable_and_audit(administrator, client):
    from accounts.services import create_faculty, reset_faculty_password, set_faculty_active
    from core.models import AuditEvent

    result = create_faculty(
        administrator,
        username="newteacher",
        display_name="New Faculty",
        temporary_password="Initial-synthetic-secret-53",
        expected_revision=0,
        request_id=uuid4(),
    )
    user = get_user_model().objects.get(pk=result["data"]["id"])
    assert user.is_active
    assert client.login(username="newteacher", password="Initial-synthetic-secret-53")
    reset_faculty_password(
        administrator,
        user.pk,
        "Replacement-synthetic-secret-53",
        expected_revision=0,
        request_id=uuid4(),
    )
    assert client.get("/").status_code == 302
    assert client.login(username="newteacher", password="Replacement-synthetic-secret-53")
    set_faculty_active(administrator, user.pk, False, expected_revision=1, request_id=uuid4())
    set_faculty_active(administrator, user.pk, True, expected_revision=2, request_id=uuid4())
    assert client.get("/").status_code == 302
    assert "secret-53" not in str(list(AuditEvent.objects.values()))


def test_disabled_user_cannot_login(client, faculty):
    faculty.is_active = False
    faculty.save()
    assert not client.login(username="teacher1", password="Synthetic-passphrase-47")


def test_safe_next_redirect(client, faculty):
    result = client.post(
        "/login/?next=https://example.org/",
        {"username": "teacher1", "password": "Synthetic-passphrase-47"},
    )
    assert result.url == "/"
