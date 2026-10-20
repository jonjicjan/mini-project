from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.errors import DomainError, conflict
from core.mutations import run_mutation

from .models import Register

EDITABLE_FIELDS = {
    "academic_year",
    "semester",
    "branch",
    "section",
    "subject_code",
    "subject_name",
    "faculty_name",
    "term_start",
    "term_end",
}


def owned_register(actor, register_id):
    if not actor.is_authenticated or not actor.is_active:
        raise Http404
    return get_object_or_404(Register, pk=register_id, owner=actor)


def assign_values(register, values):
    unknown = set(values) - EDITABLE_FIELDS
    if unknown:
        raise DomainError(
            "These fields cannot be edited.",
            field_errors={key: ["Not editable."] for key in unknown},
        )
    for key, value in values.items():
        setattr(register, key, value.strip() if isinstance(value, str) else value)
    try:
        register.full_clean()
        if not register._state.adding and hasattr(register, "sessions"):
            if any(
                not register.term_start <= session.date <= register.term_end
                for session in register.sessions.all()
            ):
                raise DomainError(
                    "Term dates must still include every saved class. Correct class dates before shortening the term."
                )
    except ValidationError as error:
        raise DomainError("Check the register details.", field_errors=error.message_dict) from error


def create_register(actor, *, values, expected_revision, request_id):
    if not actor.is_authenticated or not actor.is_active:
        raise Http404

    def change(current):
        register = Register(owner=current)
        assign_values(register, values)
        register.save()
        return register.audit_state()

    return run_mutation(
        actor,
        scope=actor,
        expected_revision=expected_revision,
        request_id=request_id,
        payload={"action": "create_register", "values": values},
        change=change,
    )


def update_register(actor, register_id, *, expected_revision, request_id, values):
    register = owned_register(actor, register_id)

    def change(current):
        if current.archived_at:
            raise conflict("Restore this register before editing it.")
        assign_values(current, values)
        current.save()
        return current.audit_state()

    return run_mutation(
        actor,
        scope=register,
        expected_revision=expected_revision,
        request_id=request_id,
        payload={"action": "update_register", "values": values},
        change=change,
    )


def set_archived(actor, register_id, archived, *, expected_revision, request_id):
    register = owned_register(actor, register_id)
    if not isinstance(archived, bool):
        raise DomainError("Archive status must be true or false.")

    def change(current):
        current.archived_at = timezone.now() if archived else None
        current.save()
        return current.audit_state()

    return run_mutation(
        actor,
        scope=register,
        expected_revision=expected_revision,
        request_id=request_id,
        payload={"action": "archive_register", "archived": archived},
        change=change,
    )
