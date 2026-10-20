"""Atomic revision checks and durable operation receipts shared by all editors."""

import json
import time
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import OperationalError, transaction
from django.db.models import F
from django.http import Http404
from django.utils.crypto import salted_hmac

from .errors import DomainError, conflict
from .models import AuditEvent, MutationReceipt


def json_value(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def run_mutation(actor, *, scope, expected_revision, request_id, payload, change, authorize=None):
    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise DomainError("A valid operation ID is required.") from None
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise DomainError("A valid saved revision is required.")
    scope_key = f"{scope._meta.label_lower}:{scope.pk}"
    encoded = json.dumps(payload, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":"))
    # A keyed digest also protects low-entropy secrets in account-management payloads.
    digest = salted_hmac("register.mutation", encoded, algorithm="sha256").hexdigest()
    for attempt in range(3):
        try:
            with transaction.atomic():
                active_actor = get_user_model().objects.filter(pk=actor.pk, is_active=True).first()
                if not active_actor:
                    raise Http404
                if authorize is not None:
                    authorize(active_actor)
                current = scope._meta.model.objects.get(pk=scope.pk)
                if hasattr(current, "owner_id"):
                    if current.owner_id != active_actor.pk:
                        raise Http404
                elif current.pk != active_actor.pk and not active_actor.is_superuser:
                    raise Http404
                receipt = MutationReceipt.objects.filter(actor=actor, request_id=request_id).first()
                if receipt:
                    if receipt.scope != scope_key or receipt.payload_digest != digest:
                        raise conflict("This operation ID was already used for a different change.")
                    return receipt.response
                before = json_value(current.audit_state())
                if current.revision != expected_revision:
                    raise conflict(
                        "Someone saved a newer version. Review it before applying your change.",
                        revision=current.revision,
                        current=before,
                        attempted=json_value(payload.get("values", {})),
                    )
                if (
                    not type(current)
                    .objects.filter(pk=current.pk, revision=expected_revision)
                    .update(revision=F("revision") + 1)
                ):
                    raise conflict("A newer change was saved. Reload and review it.")
                current.revision += 1
                data = change(current)
                response = json_value(
                    {
                        "revision": current.revision,
                        "request_id": request_id,
                        "data": data,
                        "warnings": [],
                    }
                )
                AuditEvent.objects.create(
                    actor=actor,
                    scope=scope_key,
                    action=payload["action"],
                    request_id=request_id,
                    before=before,
                    after=json_value({"scope": current.audit_state(), "result": data}),
                )
                MutationReceipt.objects.create(
                    actor=actor,
                    scope=scope_key,
                    request_id=request_id,
                    payload_digest=digest,
                    response=response,
                )
                return response
        except OperationalError as error:
            if "locked" not in str(error).lower() and "busy" not in str(error).lower():
                raise
            if attempt == 2:
                raise DomainError(
                    "Storage is busy. Retry this same change shortly.",
                    code="storage_busy",
                    status=503,
                ) from error
            time.sleep(0.05 * (attempt + 1))
