from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import OperationalError

pytestmark = pytest.mark.django_db


def test_busy_database_retry_and_atomic_receipt(faculty, register):
    from core.models import AuditEvent, MutationReceipt
    from core.mutations import run_mutation

    calls = 0

    def busy_then_save(current):
        nonlocal calls
        calls += 1
        current.subject_name = "Saved after retry"
        current.save()
        if calls < 3:
            raise OperationalError("database is locked")
        return current.audit_state()

    with patch("core.mutations.time.sleep"):
        result = run_mutation(
            faculty,
            scope=register,
            expected_revision=0,
            request_id=uuid4(),
            payload={"action": "test_busy"},
            change=busy_then_save,
        )
    assert result["revision"] == 1
    assert calls == 3
    assert MutationReceipt.objects.count() == AuditEvent.objects.count() == 1


def test_busy_database_eventually_returns_retryable_failure(faculty, register):
    from core.errors import DomainError
    from core.models import MutationReceipt
    from core.mutations import run_mutation

    def always_busy(current):
        raise OperationalError("database is locked")

    with patch("core.mutations.time.sleep"), pytest.raises(DomainError) as error:
        run_mutation(
            faculty,
            scope=register,
            expected_revision=0,
            request_id=uuid4(),
            payload={"action": "test_busy"},
            change=always_busy,
        )
    assert error.value.status == 503
    register.refresh_from_db()
    assert register.revision == 0
    assert not MutationReceipt.objects.exists()


def test_changed_request_payload_never_reuses_receipt(faculty, register, register_values):
    from core.errors import DomainError
    from registers.models import Register
    from registers.services import update_register

    another = Register.objects.create(owner=faculty, **register_values)
    request_id = uuid4()
    update_register(
        faculty,
        register.pk,
        expected_revision=0,
        request_id=request_id,
        values={"subject_name": "One"},
    )
    with pytest.raises(DomainError) as error:
        update_register(
            faculty,
            another.pk,
            expected_revision=0,
            request_id=request_id,
            values={"subject_name": "One"},
        )
    assert error.value.status == 409
    another.refresh_from_db()
    assert another.revision == 0


def test_disabled_actor_cannot_write_with_a_stale_user_object(faculty, register):
    from django.http import Http404

    from registers.services import update_register

    type(faculty).objects.filter(pk=faculty.pk).update(is_active=False)
    with pytest.raises(Http404):
        update_register(
            faculty,
            register.pk,
            expected_revision=0,
            request_id=uuid4(),
            values={"subject_name": "Must not save"},
        )


def test_admin_permission_is_rechecked_inside_transaction(administrator, monkeypatch):
    from django.core.exceptions import PermissionDenied

    from accounts import services
    from core.mutations import run_mutation

    def revoke_before_transaction(actor, **kwargs):
        type(actor).objects.filter(pk=actor.pk).update(is_superuser=False)
        return run_mutation(actor, **kwargs)

    monkeypatch.setattr(services, "run_mutation", revoke_before_transaction)
    with pytest.raises(PermissionDenied):
        services.create_faculty(
            administrator,
            username="must-not-exist",
            display_name="Synthetic",
            temporary_password="Synthetic-example-password-27",
            expected_revision=0,
            request_id=uuid4(),
        )
    assert not type(administrator).objects.filter(username="must-not-exist").exists()
