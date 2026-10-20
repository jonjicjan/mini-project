from django.core.exceptions import ValidationError
from django.db.models import Max
from django.shortcuts import get_object_or_404

from core.dates import parse_date
from core.errors import DomainError, conflict
from core.mutations import run_mutation
from registers.models import Enrollment, LessonPlanRow
from registers.services import owned_register


def mutate_register(actor, register_id, *, action, values, change, expected_revision, request_id):
    register = owned_register(actor, register_id)

    def guarded(current):
        if current.archived_at:
            raise conflict("Restore this register before changing its records.")
        result = change(current)
        current.save(update_fields=["updated_at"])
        return result

    return run_mutation(
        actor,
        scope=register,
        payload={"action": action, "values": values},
        change=guarded,
        expected_revision=expected_revision,
        request_id=request_id,
    )


def clean_save(instance):
    try:
        instance.full_clean()
    except ValidationError as error:
        raise DomainError("Check the entered values.", field_errors=error.message_dict) from error
    instance.save()
    return instance


def save_rows(register, table, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
        raise DomainError("Supply between 1 and 2,000 rows.")
    from registers.paste import parse_time_str, parse_weekday_value
    from scheduling.models import TimetableEntry
    from scheduling.services import overlaps

    seen, saved = set(), []
    batch_saved_slots = []
    for values in rows:
        values = dict(values)
        model = (
            Enrollment
            if table == "students"
            else LessonPlanRow
            if table == "lessons"
            else TimetableEntry
        )
        allowed = (
            {"id", "usn", "name", "serial_number", "eligible_from", "eligible_to"}
            if table == "students"
            else {
                "id",
                "original_number",
                "topic",
                "original_date",
                "original_period",
                "reported_execution_date",
                "remarks",
            }
            if table == "lessons"
            else {
                "id",
                "weekday",
                "period",
                "start_time",
                "end_time",
                "effective_from",
                "effective_to",
            }
        )
        if set(values) - allowed:
            raise DomainError("Unknown row fields.")

        if table == "students":
            key = "usn"
            identity = str(values.get(key, "")).strip().upper()
        elif table == "lessons":
            key = "original_number"
            identity = str(values.get(key, "")).strip().upper()
        else:
            key = "period"
            w_val = values.get("weekday")
            p_val = str(values.get("period", "")).strip().upper()
            s_val = str(values.get("start_time", "")).strip()
            identity = f"{w_val}-{p_val or s_val}"

        if not identity or identity in seen:
            raise DomainError("Identifiers must be present and unique in a batch.")
        seen.add(identity)

        if key == "original_number":
            try:
                identity = int(identity)
                if identity < 1:
                    raise ValueError
            except ValueError:
                raise DomainError("Lesson numbers must be positive integers.") from None

        if values.get("id"):
            instance = get_object_or_404(model, register=register, pk=values.pop("id"))
        elif table == "timetable":
            w_int = parse_weekday_value(values["weekday"])
            p_str = str(values["period"]).strip()
            instance = model.objects.filter(register=register, weekday=w_int, period=p_str).first()
        else:
            instance = model.objects.filter(register=register, **{key: identity}).first()

        existing = instance is not None
        instance = instance or model(register=register)

        if table == "timetable":
            instance.weekday = parse_weekday_value(values["weekday"])
            instance.period = str(values["period"]).strip()
            instance.start_time = parse_time_str(values["start_time"])
            instance.end_time = parse_time_str(values["end_time"])
            eff_from = values.get("effective_from")
            instance.effective_from = parse_date(eff_from) if eff_from else register.term_start
            eff_to = values.get("effective_to")
            instance.effective_to = parse_date(eff_to) if eff_to else None

            for other in TimetableEntry.objects.filter(
                register__owner=register.owner, weekday=instance.weekday
            ).exclude(pk=instance.pk):
                if overlaps(
                    instance.start_time, instance.end_time, other.start_time, other.end_time
                ) and (
                    instance.effective_from <= (other.effective_to or other.register.term_end)
                    and other.effective_from <= (instance.effective_to or register.term_end)
                ):
                    raise DomainError(
                        f"Slot {instance.period} on {instance.get_weekday_display()} overlaps another effective timetable entry for this faculty member."
                    )
            for other in batch_saved_slots:
                if other.weekday == instance.weekday and overlaps(
                    instance.start_time, instance.end_time, other.start_time, other.end_time
                ) and (
                    instance.effective_from <= (other.effective_to or register.term_end)
                    and other.effective_from <= (instance.effective_to or register.term_end)
                ):
                    raise DomainError(
                        f"Slot {instance.period} on {instance.get_weekday_display()} overlaps another slot in this batch."
                    )
        else:
            values[key] = identity
            if table == "students" and not existing:
                instance.serial_number = (
                    register.students.aggregate(n=Max("serial_number"))["n"] or 0
                ) + 1
                instance.eligible_from = register.term_start
            for field, value in values.items():
                if field.endswith("date") or field in ("eligible_from", "eligible_to"):
                    if not value and field == "eligible_from":
                        continue
                    try:
                        value = parse_date(value) if value else None
                    except ValueError as error:
                        raise DomainError(str(error)) from error
                setattr(instance, field, value)
            if existing and table == "students":
                old = Enrollment.objects.get(pk=instance.pk)
                if (old.eligible_from, old.eligible_to) != (
                    instance.eligible_from,
                    instance.eligible_to,
                ) and old.attendance.exists():
                    raise DomainError(
                        "Eligibility dates are locked after attendance is recorded. Correct attendance history first."
                    )

        if hasattr(instance, "revision"):
            instance.revision += 1
        clean_save(instance)
        if table == "timetable":
            batch_saved_slots.append(instance)

        if table == "lessons" and (instance.reported_execution_date or instance.original_date):
            from django.utils import timezone

            from scheduling.models import Session

            historical_date = instance.reported_execution_date or instance.original_date
            if (
                instance.reported_execution_date
                and instance.reported_execution_date > timezone.localdate()
            ):
                raise DomainError("An execution date cannot be in the future.")
            if not register.term_start <= historical_date <= register.term_end:
                raise DomainError("Lesson dates must fall within the term.")

            if (
                historical_date <= timezone.localdate()
                and not Session.objects.filter(lesson=instance).exists()
            ):
                from datetime import time

                if historical_date > register.term_end or historical_date < register.term_start:
                    raise DomainError("Execution dates must fall within the term.")
                clean_save(
                    Session(
                        register=register,
                        lesson=instance,
                        scheduled_date=instance.original_date or historical_date,
                        actual_date=instance.reported_execution_date,
                        period=instance.original_period or "1",
                        start_time=time(9),
                        end_time=time(10),
                        status="conducted" if instance.reported_execution_date else "planned",
                        fixed=True,
                        time_confirmed=False,
                        exception_reason="Imported execution date; confirm historical time and attendance.",
                    )
                )
        saved.append(str(instance.pk))
    return {"saved_ids": saved, "count": len(saved)}


def apply_paste(actor, register_id, *, table, rows, expected_revision, request_id):
    if table not in ("students", "lessons", "timetable"):
        raise DomainError("Unknown table.")
    return mutate_register(
        actor,
        register_id,
        action=f"save_{table}",
        values={"rows": rows},
        change=lambda register: save_rows(register, table, rows),
        expected_revision=expected_revision,
        request_id=request_id,
    )
