import uuid

from django.db import models


class TimetableEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    register = models.ForeignKey(
        "registers.Register", on_delete=models.PROTECT, related_name="timetable_entries"
    )
    weekday = models.PositiveSmallIntegerField(
        choices=list(
            enumerate(
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            )
        )
    )
    period = models.CharField(max_length=20)
    start_time = models.TimeField()
    end_time = models.TimeField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(condition=models.Q(weekday__lte=6), name="valid_weekday"),
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")), name="valid_slot_times"
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="valid_slot_dates",
            ),
        ]


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    register = models.ForeignKey(
        "registers.Register", on_delete=models.PROTECT, related_name="sessions"
    )
    lesson = models.ForeignKey(
        "registers.LessonPlanRow", on_delete=models.PROTECT, null=True, blank=True
    )
    kind = models.CharField(
        max_length=10,
        choices=[("lesson", "Lesson"), ("extra", "Extra class"), ("test", "Internal test")],
        default="lesson",
    )
    scheduled_date = models.DateField()
    actual_date = models.DateField(null=True, blank=True)
    period = models.CharField(max_length=20)
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(
        max_length=12,
        choices=[("planned", "Planned"), ("conducted", "Conducted"), ("cancelled", "Cancelled")],
        default="planned",
    )
    test_number = models.PositiveSmallIntegerField(null=True, blank=True)
    fixed = models.BooleanField(default=True)
    time_confirmed = models.BooleanField(default=True)
    exception_reason = models.CharField(max_length=500, blank=True)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["scheduled_date", "start_time", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["register", "test_number"], name="unique_internal_test"
            ),
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")), name="valid_session_times"
            ),
            models.CheckConstraint(
                condition=models.Q(test_number__isnull=True)
                | models.Q(test_number__gte=1, test_number__lte=3),
                name="valid_test_number",
            ),
        ]

    @property
    def date(self):
        return self.actual_date or self.scheduled_date

    def __str__(self):
        return f"{self.date} · {self.period} · {self.get_kind_display()}"


class Holiday(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    register = models.ForeignKey(
        "registers.Register", on_delete=models.PROTECT, related_name="holidays"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=300)

    class Meta:
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")), name="valid_holiday_dates"
            )
        ]


class ScheduleConflict(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name="conflicts")
    holiday = models.ForeignKey(Holiday, on_delete=models.PROTECT)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(max_length=30, blank=True)
    reason = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "holiday"], name="unique_session_holiday")
        ]
