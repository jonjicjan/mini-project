from datetime import timedelta

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginAttempt


def attempt_login(request, username, password):
    """Reserve each attempt atomically; slow password hashing happens outside the write lock."""
    user_key = salted_hmac(
        "login-user", username.strip().casefold(), algorithm="sha256"
    ).hexdigest()
    address_key = salted_hmac(
        "login-address", request.META.get("REMOTE_ADDR", "unknown"), algorithm="sha256"
    ).hexdigest()
    since = timezone.now() - timedelta(minutes=15)
    with transaction.atomic():
        LoginAttempt.objects.filter(created_at__lt=since).delete()
        if (
            LoginAttempt.objects.filter(username_digest=user_key).count() >= 5
            or LoginAttempt.objects.filter(address_digest=address_key).count() >= 5
        ):
            return None, True
        attempt = LoginAttempt.objects.create(username_digest=user_key, address_digest=address_key)
    user = authenticate(request, username=username, password=password)
    if user is not None:
        LoginAttempt.objects.filter(pk=attempt.pk).delete()
    return user, False
