import uuid

from django.conf import settings
from django.db import models


class ExportRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    register = models.ForeignKey(
        "registers.Register", on_delete=models.PROTECT, related_name="exports"
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source_revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)
    document = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
