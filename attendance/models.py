from django.db import models


class AttendanceEntry(models.Model):
    enrollment = models.ForeignKey(
        "registers.Enrollment", on_delete=models.PROTECT, related_name="attendance"
    )
    session = models.ForeignKey(
        "scheduling.Session", on_delete=models.PROTECT, related_name="attendance"
    )
    status = models.CharField(
        max_length=16,
        choices=[
            ("unmarked", "Unmarked"),
            ("present", "Present"),
            ("absent", "Absent"),
            ("not_applicable", "Not applicable"),
        ],
    )
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "session"], name="unique_attendance_cell")
        ]
