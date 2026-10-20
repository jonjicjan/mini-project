from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import close_old_connections


@pytest.mark.django_db
def test_failed_change_has_no_audit_or_receipt(faculty, register):
    from core.models import AuditEvent, MutationReceipt
    from core.mutations import run_mutation

    def fail(current):
        current.subject_name = "Must roll back"
        current.save()
        raise ValueError("synthetic failure")

    with pytest.raises(ValueError):
        run_mutation(
            faculty,
            scope=register,
            expected_revision=0,
            request_id=uuid4(),
            payload={"action": "test"},
            change=fail,
        )
    register.refresh_from_db()
    assert register.subject_name == "Software Engineering"
    assert register.revision == 0
    assert not MutationReceipt.objects.exists()
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_two_connections_cannot_win_same_revision(faculty, register):
    from core.errors import DomainError
    from registers.services import update_register

    barrier = Barrier(2)

    def edit(name):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                return update_register(
                    faculty,
                    register.pk,
                    values={"subject_name": name},
                    expected_revision=0,
                    request_id=uuid4(),
                )["revision"]
            except DomainError as error:
                return error.status
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(edit, ["First", "Second"])) == [1, 409]
    register.refresh_from_db()
    assert register.revision == 1
