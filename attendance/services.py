from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.errors import DomainError
from registers.entries import mutate_register
from registers.models import Enrollment
from scheduling.models import Session

from .calculations import summarise_statuses
from .models import AttendanceEntry


def eligible(student, day):
    return student.eligible_from <= day and (not student.eligible_to or day <= student.eligible_to)


def save_attendance(
    actor, register_id, *, session_id, cells, complete=False, expected_revision, request_id
):
    def change(register):
        session = get_object_or_404(Session, register=register, pk=session_id)
        if not session.time_confirmed:
            raise DomainError(
                "Confirm this historical class's start and end times under Classes & tests before recording attendance."
            )
        if session.status == "cancelled" or session.date > timezone.localdate():
            raise DomainError(
                "Attendance can only be recorded for a non-cancelled class dated today or earlier."
            )
        if not isinstance(cells, list) or len(cells) > 2000:
            raise DomainError("Invalid attendance batch.")
        students = {str(s.pk): s for s in register.students.all()}
        seen = set()
        for cell in cells:
            student_id, status = str(cell.get("enrollment_id")), cell.get("status")
            if student_id not in students or student_id in seen:
                raise DomainError("Select each student once from this register.")
            seen.add(student_id)
            if status not in ("present", "absent", "unmarked", "not_applicable"):
                raise DomainError("Unknown attendance status.")
            if eligible(students[student_id], session.date) == (status == "not_applicable"):
                raise DomainError("Attendance must match the student's eligibility dates.")
            entry, _ = AttendanceEntry.objects.get_or_create(
                enrollment_id=student_id, session=session, defaults={"status": status}
            )
            entry.status, entry.revision = status, entry.revision + 1
            entry.save()
        if complete:
            for student in students.values():
                status = "present" if eligible(student, session.date) else "not_applicable"
                entry, _ = AttendanceEntry.objects.get_or_create(
                    enrollment=student, session=session, defaults={"status": status}
                )
                if entry.status == "unmarked":
                    entry.status = status
                    entry.revision += 1
                    entry.save()
            session.status = "conducted"
            session.actual_date = session.actual_date or session.scheduled_date
            session.fixed = True
            session.revision += 1
            session.save()
        return {"session_id": str(session.pk), "completed": complete, "changed": len(cells)}

    return mutate_register(
        actor,
        register_id,
        action="save_attendance",
        values={"session_id": str(session_id), "cells": cells, "complete": complete},
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )


def attendance_summary(register_id, enrollment_id, *, through):
    student = get_object_or_404(Enrollment, register_id=register_id, pk=enrollment_id)
    return attendance_summaries(register_id, through=through)[str(student.pk)]


def attendance_summaries(register_id, *, through):
    from scheduling.models import ScheduleConflict

    sessions = sorted(
        [
            s
            for s in Session.objects.filter(register_id=register_id, status="conducted")
            if s.date <= through
        ],
        key=lambda s: (s.date, s.start_time, str(s.pk)),
    )
    entries = {
        (student_id, session_id): status
        for student_id, session_id, status in AttendanceEntry.objects.filter(
            enrollment__register_id=register_id, session_id__in=[s.pk for s in sessions]
        ).values_list("enrollment_id", "session_id", "status")
    }
    has_conflicts = ScheduleConflict.objects.filter(
        session_id__in=[s.pk for s in sessions], resolved_at__isnull=True
    ).exists()
    results = {}
    for student in Enrollment.objects.filter(register_id=register_id):
        result = summarise_statuses(
            [
                entries.get((student.pk, s.pk), "unmarked")
                if eligible(student, s.date)
                else "not_applicable"
                for s in sessions
            ]
        )
        result["sequence"] = {
            str(s.pk): value for s, value in zip(sessions, result["sequence"], strict=True)
        }
        result["provisional"] |= has_conflicts
        results[str(student.pk)] = result
    return results


def column_totals(register_id, session_id, enrollment_ids):
    session = get_object_or_404(Session, pk=session_id, register_id=register_id)
    entries = {e.enrollment_id: e.status for e in session.attendance.all()}
    totals = {"present": 0, "absent": 0, "unmarked": 0}
    for student in Enrollment.objects.filter(register_id=register_id, pk__in=enrollment_ids):
        if eligible(student, session.date):
            status = entries.get(student.pk, "unmarked")
            if status in totals:
                totals[status] += 1
    return totals
