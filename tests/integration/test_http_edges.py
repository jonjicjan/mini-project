from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_account_create_through_form_and_replay(client, administrator):
    client.force_login(administrator)
    payload = {
        "username": "newteacher",
        "display_name": "New Teacher",
        "temporary_password": "Initial-synthetic-secret-53",
        "expected_revision": 0,
        "request_id": str(uuid4()),
    }
    assert client.get("/admin/faculty/").status_code == 200
    assert client.post("/admin/faculty/", payload).status_code == 302
    assert client.post("/admin/faculty/", payload).status_code == 302
    assert get_user_model().objects.filter(username="newteacher").count() == 1


def test_account_weak_password_and_duplicate_username(client, administrator, faculty):
    client.force_login(administrator)
    base = {
        "username": "TEACHER1",
        "display_name": "Duplicate",
        "temporary_password": "123456789012",
        "expected_revision": 0,
        "request_id": str(uuid4()),
    }
    assert client.post("/admin/faculty/", base).status_code == 422
    assert not get_user_model().objects.filter(username="TEACHER1").exists()


def test_throttle_expires(client, faculty):
    from accounts.models import LoginAttempt

    for _ in range(5):
        client.post("/login/", {"username": "teacher1", "password": "wrong"})
    LoginAttempt.objects.update(created_at=timezone.now() - timedelta(minutes=16))
    assert (
        client.post(
            "/login/", {"username": "teacher1", "password": "Synthetic-passphrase-47"}
        ).status_code
        == 302
    )


def test_archive_form_replay_does_not_restore(client, faculty, register):
    client.force_login(faculty)
    url = f"/registers/{register.pk}/archive/"
    payload = {"archived": "yes", "expected_revision": 0, "request_id": str(uuid4())}
    assert client.post(url, payload).status_code == 302
    assert client.post(url, payload).status_code == 302
    register.refresh_from_db()
    assert register.archived_at is not None
    assert register.revision == 1


def test_api_rejects_bad_json_dates_and_owner_changes(client, faculty, register):
    client.force_login(faculty)
    url = f"/api/registers/{register.pk}/"
    for values in [{"term_start": "not-a-date"}, {"owner_id": 999}, {"term_end": "2020-01-01"}]:
        response = client.post(
            url,
            {"values": values, "expected_revision": 0, "request_id": str(uuid4())},
            content_type="application/json",
        )
        assert response.status_code == 422
    assert client.post(url, "[", content_type="application/json").status_code == 422
    assert client.post(url, "[]", content_type="application/json").status_code == 422
    assert client.post(url, {"values": {}}, content_type="application/json").status_code == 422


def test_api_conflict_contains_saved_and_attempted_values(client, faculty, register):
    client.force_login(faculty)
    url = f"/api/registers/{register.pk}/"
    response = client.post(
        url,
        {
            "values": {"subject_name": "New name"},
            "expected_revision": 0,
            "request_id": str(uuid4()),
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    response = client.post(
        url,
        {
            "values": {"subject_name": "Stale name"},
            "expected_revision": 0,
            "request_id": str(uuid4()),
        },
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["current"]["subject_name"] == "New name"
    assert response.json()["attempted"]["subject_name"] == "Stale name"


def test_csrf_required_for_authenticated_mutations(faculty, register):
    client = Client(enforce_csrf_checks=True)
    client.force_login(faculty)
    assert (
        client.post(
            f"/api/registers/{register.pk}/",
            {
                "values": {"subject_name": "Must not save"},
                "expected_revision": 0,
                "request_id": str(uuid4()),
            },
            content_type="application/json",
        ).status_code
        == 403
    )


def test_archived_register_cannot_be_edited(client, faculty, register):
    from registers.services import set_archived

    set_archived(faculty, register.pk, True, expected_revision=0, request_id=uuid4())
    client.force_login(faculty)
    response = client.post(
        f"/api/registers/{register.pk}/",
        {
            "values": {"subject_name": "Must not save"},
            "expected_revision": 1,
            "request_id": str(uuid4()),
        },
        content_type="application/json",
    )
    assert response.status_code == 409
