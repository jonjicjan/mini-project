from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from core.errors import DomainError
from core.mutations import run_mutation


def require_admin(actor):
    if (
        not actor.is_authenticated
        or not get_user_model()
        .objects.filter(pk=actor.pk, is_superuser=True, is_active=True)
        .exists()
    ):
        raise PermissionDenied


def validate_user(user, password=None):
    try:
        user.full_clean(exclude=["password"])
        if password is not None:
            validate_password(password, user)
    except ValidationError as error:
        raise DomainError(
            "Check the account details.",
            field_errors=getattr(error, "message_dict", {"password": error.messages}),
        ) from error


def create_faculty(
    actor, *, username, display_name, temporary_password, expected_revision, request_id
):
    require_admin(actor)

    def change(current):
        user = get_user_model()(
            username=username.strip().lower(), display_name=display_name.strip()
        )
        validate_user(user, temporary_password)
        user.set_password(temporary_password)
        user.save()
        return user.audit_state()

    return run_mutation(
        actor,
        scope=actor,
        expected_revision=expected_revision,
        request_id=request_id,
        payload={
            "action": "create_faculty",
            "username": username,
            "display_name": display_name,
            "password": temporary_password,
        },
        change=change,
        authorize=require_admin,
    )


def reset_faculty_password(actor, user_id, password, *, expected_revision, request_id):
    require_admin(actor)
    target = get_object_or_404(get_user_model(), pk=user_id, is_superuser=False)

    def change(current):
        validate_user(current, password)
        current.set_password(password)
        current.session_version += 1
        current.save()
        return current.audit_state()

    return run_mutation(
        actor,
        scope=target,
        expected_revision=expected_revision,
        request_id=request_id,
        payload={"action": "reset_password", "password": password},
        change=change,
        authorize=require_admin,
    )


def set_faculty_active(actor, user_id, active, *, expected_revision, request_id):
    require_admin(actor)
    target = get_object_or_404(get_user_model(), pk=user_id, is_superuser=False)
    if not isinstance(active, bool):
        raise DomainError("Account status must be true or false.")

    def change(current):
        current.is_active = active
        current.session_version += 1
        current.save()
        return current.audit_state()

    return run_mutation(
        actor,
        scope=target,
        expected_revision=expected_revision,
        request_id=request_id,
        payload={"action": "set_active", "active": active},
        change=change,
        authorize=require_admin,
    )
