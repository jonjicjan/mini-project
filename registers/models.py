import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Register(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="registers"
    )
    academic_year = models.CharField(max_length=30)
    semester = models.CharField(max_length=20)
    branch = models.CharField(max_length=100)
    section = models.CharField(max_length=30)
    subject_code = models.CharField(max_length=40)
    subject_name = models.CharField(max_length=200)
    faculty_name = models.CharField(max_length=150)
    term_start = models.DateField()
    term_end = models.DateField()
    revision = models.PositiveIntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "subject_name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(term_end__gte=models.F("term_start")), name="register_valid_term"
            )
        ]

    def clean(self):
        if (
            isinstance(self.term_start, date)
            and isinstance(self.term_end, date)
            and self.term_end < self.term_start
        ):
            raise ValidationError({"term_end": "The term must end on or after its start date."})

    def audit_state(self):
        return {
            field: getattr(self, field)
            for field in [
                "id",
                "academic_year",
                "semester",
                "branch",
                "section",
                "subject_code",
                "subject_name",
                "faculty_name",
                "term_start",
                "term_end",
                "revision",
                "archived_at",
            ]
        }


class Enrollment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    register = models.ForeignKey(Register, on_delete=models.PROTECT, related_name="students")
    usn = models.CharField(max_length=40)
    name = models.CharField(max_length=150)
    serial_number = models.PositiveIntegerField()
    eligible_from = models.DateField()
    eligible_to = models.DateField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["serial_number", "id"]
        constraints = [
            models.UniqueConstraint(fields=["register", "usn"], name="unique_register_usn"),
            models.CheckConstraint(
                condition=models.Q(eligible_to__isnull=True)
                | models.Q(eligible_to__gte=models.F("eligible_from")),
                name="valid_enrollment_dates",
            ),
        ]

    def clean(self):
        self.usn = self.usn.strip().upper()
        self.name = self.name.strip()
        if self.eligible_to and self.eligible_from and self.eligible_to < self.eligible_from:
            raise ValidationError({"eligible_to": "Must not precede eligibility start."})


class LessonPlanRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    register = models.ForeignKey(Register, on_delete=models.PROTECT, related_name="lessons")
    original_number = models.PositiveIntegerField()
    topic = models.TextField(max_length=2000)
    original_date = models.DateField(null=True, blank=True)
    original_period = models.CharField(max_length=20, blank=True)
    reported_execution_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(max_length=2000, blank=True)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["original_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["register", "original_number"], name="unique_lesson_number"
            )
        ]

    def __str__(self):
        return f"{self.original_number}. {self.topic[:90]}"
