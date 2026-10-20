import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    display_name = models.CharField(max_length=150, blank=True)
    revision = models.PositiveIntegerField(default=0)
    session_version = models.PositiveIntegerField(default=0)

    class Meta(AbstractUser.Meta):
        constraints = [models.UniqueConstraint(Lower("username"), name="case_insensitive_username")]

    def audit_state(self):
        return {
            "id": self.pk,
            "username": self.username,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "revision": self.revision,
            "session_version": self.session_version,
        }


class LoginAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username_digest = models.CharField(max_length=64, db_index=True)
    address_digest = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
