from datetime import date
from uuid import uuid4

import pytest
from django.http import Http404

pytestmark = pytest.mark.django_db


def test_ownership_at_service_and_http_boundary(client, other_faculty, register):
    from registers.services import owned_register, update_register

    with pytest.raises(Http404):
        owned_register(other_faculty, register.pk)
    with pytest.raises(Http404):
        update_register(
            other_faculty,
            register.pk,
            expected_revision=0,
            request_id=uuid4(),
            values={"subject_name": "Stolen"},
        )
    client.force_login(other_faculty)
    assert client.get(f"/registers/{register.pk}/").status_code == 404
    assert client.post(f"/registers/{register.pk}/", {}).status_code == 404
    assert register.subject_name not in client.get("/").content.decode()


def test_update_retry_conflict_and_validation(faculty, register):
    from core.errors import DomainError
    from registers.services import update_register

    request_id = uuid4()
    kwargs = dict(
        expected_revision=0, request_id=request_id, values={"subject_name": "Updated subject"}
    )
    result = update_register(faculty, register.pk, **kwargs)
    assert result["revision"] == 1
    assert update_register(faculty, register.pk, **kwargs) == result
    for bad in [dict(kwargs, request_id=uuid4()), dict(kwargs, values={"subject_name": "Other"})]:
        with pytest.raises(DomainError) as error:
            update_register(faculty, register.pk, **bad)
        assert error.value.status == 409
    with pytest.raises(DomainError) as error:
        update_register(
            faculty,
            register.pk,
            expected_revision=1,
            request_id=uuid4(),
            values={"term_end": date(2020, 1, 1)},
        )
    assert error.value.status == 422
    register.refresh_from_db()
    assert register.revision == 1
    assert register.subject_name == "Updated subject"


def test_archive_preserves_register_and_allows_restore(faculty, register):
    from registers.models import Register
    from registers.services import set_archived

    set_archived(faculty, register.pk, True, expected_revision=0, request_id=uuid4())
    assert Register.objects.get(pk=register.pk).archived_at is not None
    set_archived(faculty, register.pk, False, expected_revision=1, request_id=uuid4())
    assert Register.objects.get(pk=register.pk).archived_at is None


def test_create_is_idempotent(faculty, register_values):
    from registers.models import Register
    from registers.services import create_register

    kwargs = dict(values=register_values, expected_revision=0, request_id=uuid4())
    first = create_register(faculty, **kwargs)
    assert create_register(faculty, **kwargs) == first
    assert Register.objects.count() == 1


def test_render_create_edit_and_validation(client, faculty, register_values):
    client.force_login(faculty)
    assert client.get("/registers/new/").status_code == 200
    response = client.post(
        "/registers/new/", {**register_values, "expected_revision": 0, "request_id": str(uuid4())}
    )
    assert response.status_code == 302
    edit = client.get(response.url)
    assert edit.status_code == 200
    assert b"Software Engineering" in edit.content
