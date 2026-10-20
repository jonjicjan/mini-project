from datetime import date, timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.errors import DomainError, conflict
from registers.entries import clean_save, mutate_register
from registers.models import Register

from .models import Holiday, ScheduleConflict, Session, TimetableEntry


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def validate_session(session):
    register = session.register
    if not register.term_start <= session.date <= register.term_end:
        raise DomainError("The class date must be within the register's term.")
    if session.status == "conducted" and session.date > timezone.localdate():
        raise DomainError("A future class cannot be conducted.")
    if session.kind == "test" and session.test_number not in (1, 2, 3):
        raise DomainError("Select Test 1, 2 or 3.")
    if session.kind != "test" and session.test_number is not None:
        raise DomainError("A test number is only valid for an internal test.")
    if session.lesson_id and session.lesson.register_id != register.pk:
        raise DomainError("The lesson must belong to this register.")
    if session.status != "cancelled":
        candidates = (
            Session.objects.filter(register__owner=register.owner)
            .exclude(pk=session.pk)
            .exclude(status="cancelled")
        )
        for other in candidates:
            if other.date == session.date and overlaps(
                other.start_time, other.end_time, session.start_time, session.end_time
            ):
                raise DomainError(
                    f"This time overlaps another class on {session.date}: {other.register.subject_code}, period {other.period}."
                )
        if (
            register.holidays.filter(
                start_date__lte=session.date, end_date__gte=session.date
            ).exists()
            and not session.exception_reason
        ):
            raise DomainError(
                "This date is a holiday. Enter an exception reason to keep an actual class."
            )


def save_session(actor, register_id, *, values, expected_revision, request_id):
    def change(register):
        data = dict(values)
        session_id = data.pop("id", None)
        replacement = data.pop("replacement", None)
        session = (
            get_object_or_404(Session, register=register, pk=session_id)
            if session_id
            else Session(register=register)
        )
        if session_id and session.status == "conducted" and not data.get("exception_reason"):
            raise DomainError(
                "Enter a reason when correcting a conducted class; its attendance will be retained."
            )
        if replacement:
            replaced = get_object_or_404(Session, register=register, pk=replacement)
            if replaced.status != "planned" or replaced.attendance.exists():
                raise DomainError(
                    "Only an unrecorded planned class can be replaced. Resolve recorded history first."
                )
            replaced.status = "cancelled"
            replaced.revision += 1
            replaced.save()
        allowed = {
            "lesson",
            "kind",
            "scheduled_date",
            "actual_date",
            "period",
            "start_time",
            "end_time",
            "status",
            "test_number",
            "exception_reason",
        }
        if set(data) - allowed:
            raise DomainError("Unknown session fields.")
        for key, value in data.items():
            setattr(session, key, value)
        session.fixed = True
        session.time_confirmed = True
        validate_session(session)
        session.revision += 1
        clean_save(session)
        return {"session_id": str(session.pk), "status": session.status}

    # Model objects must be converted for the idempotency digest and audit.
    payload = {k: str(v.pk) if hasattr(v, "pk") else v for k, v in values.items()}
    return mutate_register(
        actor,
        register_id,
        action="save_session",
        values=payload,
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )


def save_slot(actor, register_id, *, values, expected_revision, request_id):
    def change(register):
        data = dict(values)
        slot_id = data.pop("id", None)
        slot = (
            get_object_or_404(TimetableEntry, register=register, pk=slot_id)
            if slot_id
            else TimetableEntry(register=register)
        )
        for key, value in data.items():
            if key not in {
                "weekday",
                "period",
                "start_time",
                "end_time",
                "effective_from",
                "effective_to",
            }:
                raise DomainError("Unknown timetable field.")
            setattr(slot, key, value)
        try:
            slot.full_clean()
        except Exception as error:
            from django.core.exceptions import ValidationError

            if isinstance(error, ValidationError):
                raise DomainError(
                    "Check the timetable values.", field_errors=error.message_dict
                ) from error
            raise
        for other in TimetableEntry.objects.filter(
            register__owner=actor, weekday=slot.weekday
        ).exclude(pk=slot.pk):
            if overlaps(slot.start_time, slot.end_time, other.start_time, other.end_time) and (
                slot.effective_from <= (other.effective_to or other.register.term_end)
                and other.effective_from <= (slot.effective_to or register.term_end)
            ):
                raise DomainError(
                    "This slot overlaps another effective timetable entry for this faculty member."
                )
        clean_save(slot)
        return {
            "slot_id": str(slot.pk),
            "note": "Existing sessions retain their saved times. Preview scheduling to move future lessons.",
        }

    return mutate_register(
        actor,
        register_id,
        action="save_timetable",
        values=values,
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )


def save_holiday(actor, register_id, *, values, expected_revision, request_id):
    def change(register):
        holiday = clean_save(Holiday(register=register, **values))
        count = 0
        for session in register.sessions.exclude(status="cancelled"):
            if holiday.start_date <= session.date <= holiday.end_date:
                ScheduleConflict.objects.get_or_create(session=session, holiday=holiday)
                count += 1
        return {"holiday_id": str(holiday.pk), "conflicts": count}

    return mutate_register(
        actor,
        register_id,
        action="add_holiday",
        values=values,
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )


def resolve_conflict(
    actor, register_id, *, conflict_id, action, reason, expected_revision, request_id
):
    def change(register):
        item = get_object_or_404(ScheduleConflict, pk=conflict_id, session__register=register)
        if not reason.strip() or action not in ("keep_actual", "cancel"):
            raise DomainError("Select a resolution and enter a reason.")
        item.session.exception_reason = reason.strip()
        if action == "cancel":
            item.session.status = "cancelled"
        item.session.revision += 1
        item.session.save()
        item.resolved_at, item.resolution, item.reason = timezone.now(), action, reason.strip()
        item.save()
        return {"conflict_id": str(item.pk), "resolution": action}

    return mutate_register(
        actor,
        register_id,
        action="resolve_schedule_conflict",
        values={"conflict_id": str(conflict_id), "action": action, "reason": reason},
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )


def preview_rebuild(register, *, effective_from):
    today = timezone.localdate()
    entries = list(register.timetable_entries.all())
    holidays = list(register.holidays.all())
    existing = list(register.sessions.exclude(status="cancelled"))
    movable = {
        s.lesson_id: s
        for s in existing
        if s.lesson_id
        and not s.fixed
        and s.status == "planned"
        and s.scheduled_date >= max(today, effective_from)
        and not s.attendance.exists()
    }
    fixed_lessons = {s.lesson_id for s in existing if s.lesson_id not in movable}
    occupied = [
        s
        for s in Session.objects.filter(register__owner=register.owner).exclude(status="cancelled")
        if s.pk not in {v.pk for v in movable.values()}
    ]
    slots = []
    day = max(register.term_start, effective_from, today)
    while day <= register.term_end:
        if not any(h.start_date <= day <= h.end_date for h in holidays):
            for entry in entries:
                if (
                    entry.weekday == day.weekday()
                    and entry.effective_from <= day
                    and (not entry.effective_to or day <= entry.effective_to)
                ):
                    if not any(
                        s.date == day
                        and overlaps(entry.start_time, entry.end_time, s.start_time, s.end_time)
                        for s in occupied
                    ):
                        slots.append((day, entry))
        day += timedelta(days=1)
    slots.sort(key=lambda pair: (pair[0], pair[1].start_time, str(pair[1].pk)))
    moves, unplaced = [], []
    for lesson in register.lessons.all():
        if lesson.pk in fixed_lessons:
            continue
        if not slots:
            unplaced.append(str(lesson.pk))
            continue
        day, entry = slots.pop(0)
        old = movable.get(lesson.pk)
        moves.append(
            {
                "id": str(old.pk) if old else None,
                "lesson_id": str(lesson.pk),
                "date": str(day),
                "period": entry.period,
                "start": str(entry.start_time),
                "end": str(entry.end_time),
            }
        )
    return {
        "source_revisions": {
            str(r.pk): r.revision for r in Register.objects.filter(owner=register.owner)
        },
        "effective_from": str(effective_from),
        "today": str(today),
        "moves": moves,
        "unplaced": unplaced,
    }


def apply_rebuild(actor, register_id, *, preview, expected_revision, request_id):
    def change(register):
        current = preview_rebuild(
            register, effective_from=date.fromisoformat(preview["effective_from"])
        )
        # The enclosing mutation already advances this register's revision once.
        current["source_revisions"][str(register.pk)] -= 1
        if current != preview:
            raise conflict("The schedule or a related register changed. Generate a new preview.")
        from datetime import time

        for move in preview["moves"]:
            session = (
                get_object_or_404(Session, register=register, pk=move["id"])
                if move["id"]
                else Session(register=register)
            )
            session.lesson_id = move["lesson_id"]
            session.scheduled_date = date.fromisoformat(move["date"])
            session.start_time, session.end_time = (
                time.fromisoformat(move["start"]),
                time.fromisoformat(move["end"]),
            )
            session.period, session.fixed = move["period"], False
            session.revision += 1
            clean_save(session)
        return {"scheduled": len(preview["moves"]), "unplaced": preview["unplaced"]}

    return mutate_register(
        actor,
        register_id,
        action="apply_schedule",
        values=preview,
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )
