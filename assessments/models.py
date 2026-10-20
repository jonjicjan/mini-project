from django.core.exceptions import ValidationError
from django.db import models


class RegisterMarkingRule(models.Model):
    register = models.OneToOneField(
        "registers.Register", on_delete=models.PROTECT, related_name="marking_rule"
    )
    definition = models.JSONField()


class Mark(models.Model):
    enrollment = models.ForeignKey(
        "registers.Enrollment", on_delete=models.PROTECT, related_name="marks"
    )
    assessment_key = models.CharField(
        max_length=2, choices=[(k, k) for k in ["A1", "A2", "A3", "T1", "T2", "T3"]]
    )
    value = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=[("missing", "Missing"), ("scored", "Scored"), ("absent", "Absent")],
        default="missing",
    )
    revision = models.PositiveIntegerField(default=0)

    def clean(self):
        if self.status == "scored":
            from .calculations import decimal

            rule = self.enrollment.register.marking_rule.definition
            if self.value is None or not 0 <= self.value <= decimal(
                rule["assessments"][self.assessment_key]
            ):
                raise ValidationError({"value": "Mark exceeds the configured range."})
        elif self.value is not None:
            raise ValidationError({"value": "Absent and missing marks must not contain a number."})

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "assessment_key"], name="unique_assessment_mark"
            )
        ]
