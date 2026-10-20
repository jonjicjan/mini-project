import io
import uuid
from datetime import date, time
from decimal import Decimal
from zipfile import ZipFile

import pytest
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from assessments.calculations import calculate_score, default_rule, validate_rule
from assessments.services import save_marks, save_rule
from attendance.calculations import summarise_statuses
from attendance.services import attendance_summary, save_attendance
from core.dates import parse_date
from core.errors import DomainError
from exports.models import ExportRecord
from exports.snapshot import build_export_snapshot, create_export
from registers.entries import apply_paste
from registers.paste import preview_paste
from scheduling.models import ScheduleConflict
from scheduling.services import (
    apply_rebuild,
    preview_rebuild,
    resolve_conflict,
    save_holiday,
    save_session,
    save_slot,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: date(2026, 10, 4))


def operation(register):
    register.refresh_from_db()
    return {"expected_revision": register.revision, "request_id": uuid.uuid4()}


def add_student(faculty, register, usn="001", **values):
    apply_paste(
        faculty,
        register.pk,
        table="students",
        rows=[{"usn": usn, "name": "Sample Student", "eligible_from": "2026-08-01", **values}],
        **operation(register),
    )
    return register.students.get(usn=usn)


def add_session(faculty, register, day=date(2026, 10, 1), **values):
    result = save_session(
        faculty,
        register.pk,
        values={
            "scheduled_date": day,
            "period": "1",
            "start_time": time(9),
            "end_time": time(10),
            "kind": "lesson",
            **values,
        },
        **operation(register),
    )
    return register.sessions.get(pk=result["data"]["session_id"])


def test_paste_dates_csv_unicode_and_atomicity(faculty, register):
    assert parse_date("29/02/2024") == date(2024, 2, 29)
    for invalid in ["01/02/26", "29/02/2025", "2026-13-01"]:
        with pytest.raises(ValueError):
            parse_date(invalid)
    preview = preview_paste(
        '001,"Student, One"\n002,विद्यार्थी',
        table="students",
        delimiter="comma",
        mapping={"usn": 0, "name": 1},
    )
    assert not preview["errors"] and preview["rows"][0]["usn"] == "001"
    apply_paste(faculty, register.pk, table="students", rows=preview["rows"], **operation(register))
    first = register.students.get(usn="001")
    apply_paste(
        faculty,
        register.pk,
        table="students",
        rows=[{"usn": "002", "name": "Updated"}, {"usn": "001", "name": "Corrected"}],
        **operation(register),
    )
    first.refresh_from_db()
    assert first.name == "Corrected" and first.serial_number == 1
    op = operation(register)
    with pytest.raises(DomainError):
        apply_paste(
            faculty,
            register.pk,
            table="students",
            rows=[{"usn": "003", "name": "Good"}, {"usn": "004", "name": ""}],
            **op,
        )
    assert register.students.count() == 2
    register.refresh_from_db()
    assert register.revision == op["expected_revision"]
    assert preview_paste("001\tA\n001\tB", table="students")["errors"]


def test_timetable_paste_apply_and_conflict(faculty, register):
    text = (
        "weekday\tperiod\tstart_time\tend_time\teffective_from\teffective_to\n"
        "Monday\t1\t09:00\t10:00\t2026-08-01\t2026-12-31\n"
        "Monday\t2\t10:00\t11:00\t2026-08-01\t2026-12-31\n"
        "Tuesday\t3\t11:15\t12:15\t2026-08-01\t2026-12-31\n"
    )
    preview = preview_paste(text, table="timetable", delimiter="tab")
    assert not preview["errors"]
    assert len(preview["rows"]) == 3

    apply_paste(faculty, register.pk, table="timetable", rows=preview["rows"], **operation(register))
    register.refresh_from_db()
    assert register.timetable_entries.count() == 3

    slot1 = register.timetable_entries.get(weekday=0, period="1")
    assert slot1.start_time.strftime("%H:%M") == "09:00"
    assert slot1.end_time.strftime("%H:%M") == "10:00"

    # Attempting to apply an overlapping slot raises DomainError and rolls back atomically
    op = operation(register)
    with pytest.raises(DomainError, match="overlaps"):
        apply_paste(
            faculty,
            register.pk,
            table="timetable",
            rows=[{"weekday": "Monday", "period": "Conflict", "start_time": "09:30", "end_time": "10:30"}],
            **op,
        )
    assert register.timetable_entries.count() == 3
    register.refresh_from_db()
    assert register.revision == op["expected_revision"]


def test_manual_attendance_late_joiner_corrections_and_ownership(faculty, other_faculty, register):
    student = add_student(faculty, register)
    late = add_student(faculty, register, "002", eligible_from="2026-10-02")
    session = add_session(faculty, register)
    assert attendance_summary(register.pk, student.pk, through=date(2026, 10, 4))["eligible"] == 0
    op = operation(register)
    response = save_attendance(
        faculty,
        register.pk,
        session_id=session.pk,
        cells=[{"enrollment_id": str(student.pk), "status": "absent"}],
        complete=True,
        **op,
    )
    assert (
        save_attendance(
            faculty,
            register.pk,
            session_id=session.pk,
            cells=[{"enrollment_id": str(student.pk), "status": "absent"}],
            complete=True,
            **op,
        )
        == response
    )
    summary = attendance_summary(register.pk, student.pk, through=date(2026, 10, 4))
    assert summary["sequence"][str(session.pk)] == "A" and summary["eligible"] == 1
    assert attendance_summary(register.pk, late.pk, through=date(2026, 10, 4))["eligible"] == 0
    with pytest.raises(Http404):
        save_attendance(
            other_faculty,
            register.pk,
            session_id=session.pk,
            cells=[],
            complete=True,
            **operation(register),
        )
    future = add_session(faculty, register, date(2026, 10, 5))
    with pytest.raises(DomainError):
        save_attendance(
            faculty,
            register.pk,
            session_id=future.pk,
            cells=[],
            complete=True,
            **operation(register),
        )
    assert summarise_statuses(["present", "present", "absent", "present", "absent"])[
        "sequence"
    ] == ["1", "2", "A", "3", "A"]
    with pytest.raises(DomainError):
        apply_paste(
            faculty,
            register.pk,
            table="students",
            rows=[{"usn": "001", "name": "A", "eligible_from": "2026-10-03"}],
            **operation(register),
        )


def test_schedule_preview_stable_ids_holiday_reconciliation(faculty, register):
    add_student(faculty, register)
    apply_paste(
        faculty,
        register.pk,
        table="lessons",
        rows=[{"original_number": i, "topic": f"Topic {i}"} for i in range(1, 4)],
        **operation(register),
    )
    save_slot(
        faculty,
        register.pk,
        values={
            "weekday": 0,
            "period": "1",
            "start_time": time(9),
            "end_time": time(10),
            "effective_from": date(2026, 8, 1),
        },
        **operation(register),
    )
    register.refresh_from_db()
    preview = preview_rebuild(register, effective_from=date(2026, 10, 4))
    assert [m["date"] for m in preview["moves"]] == ["2026-10-05", "2026-10-12", "2026-10-19"]
    apply_rebuild(faculty, register.pk, preview=preview, **operation(register))
    ids = set(register.sessions.values_list("pk", flat=True))
    register.refresh_from_db()
    preview = preview_rebuild(register, effective_from=date(2026, 10, 4))
    apply_rebuild(faculty, register.pk, preview=preview, **operation(register))
    assert set(register.sessions.values_list("pk", flat=True)) == ids
    historical = add_session(faculty, register)
    save_attendance(
        faculty,
        register.pk,
        session_id=historical.pk,
        cells=[],
        complete=True,
        **operation(register),
    )
    save_holiday(
        faculty,
        register.pk,
        values={
            "start_date": date(2026, 10, 1),
            "end_date": date(2026, 10, 1),
            "reason": "Retrospective closure",
        },
        **operation(register),
    )
    item = ScheduleConflict.objects.get(session=historical)
    assert historical.attendance.count() == 1
    resolve_conflict(
        faculty,
        register.pk,
        conflict_id=item.pk,
        action="cancel",
        reason="No class held",
        **operation(register),
    )
    historical.refresh_from_db()
    assert historical.status == "cancelled" and historical.attendance.count() == 1


def test_test_replacement_and_saved_marks(faculty, register):
    student = add_student(faculty, register)
    lesson = add_session(faculty, register)
    test = add_session(
        faculty, register, kind="test", test_number=1, replacement=lesson.pk, end_time=time(11)
    )
    lesson.refresh_from_db()
    assert lesson.status == "cancelled"
    save_attendance(
        faculty, register.pk, session_id=test.pk, cells=[], complete=True, **operation(register)
    )
    summary = attendance_summary(register.pk, student.pk, through=date(2026, 10, 4))
    assert summary["eligible"] == 1 and summary["percentage"] == 100
    rule = default_rule()
    save_rule(faculty, register.pk, definition=rule, **operation(register))
    values = {key: "22.5" if key.startswith("A") else "20" for key in rule["assessments"]}
    save_marks(faculty, register.pk, rows=[{"usn": "001", **values}], **operation(register))
    marks = {m.assessment_key: {"value": m.value, "status": m.status} for m in student.marks.all()}
    assert calculate_score(rule, marks)["rounded"] == Decimal("42")
    save_marks(
        faculty,
        register.pk,
        rows=[{"usn": "001", "A1": "", "A2": "AB", "A3": "CLEAR"}],
        **operation(register),
    )
    assert student.marks.get(assessment_key="A1").value == Decimal("22.5")
    assert student.marks.get(assessment_key="A2").status == "absent"
    assert student.marks.get(assessment_key="A3").status == "missing"
    rule["assessments"]["A1"] = "10"
    with pytest.raises(DomainError):
        save_rule(faculty, register.pk, definition=rule, **operation(register))
    rule = default_rule()
    rule["components"][0]["weight_percent"] = "39.99"
    assert validate_rule(rule)


def test_actual_word_snapshot_is_private_and_immutable(faculty, other_faculty, register, client):
    student = add_student(faculty, register)
    session = add_session(faculty, register)
    save_attendance(
        faculty, register.pk, session_id=session.pk, cells=[], complete=True, **operation(register)
    )
    save_rule(faculty, register.pk, definition=default_rule(), **operation(register))
    save_marks(
        faculty, register.pk, rows=[{"usn": "001", "A1": "20", "T1": "22"}], **operation(register)
    )
    snapshot = build_export_snapshot(faculty, register.pk, through=date(2026, 10, 4), draft=True)
    assert snapshot["attendance"][str(student.pk)]["cells"][str(session.pk)] == "1"
    assert snapshot["assessments"]["students"][str(student.pk)]["display"][0] == "20"
    assert (
        snapshot["assessments"]["students"][str(student.pk)]["raw_marks"]["T1"]["status"]
        == "missing"
    )
    op = operation(register)
    result = create_export(faculty, register.pk, through=date(2026, 10, 4), draft=True, **op)
    assert (
        create_export(faculty, register.pk, through=date(2026, 10, 4), draft=True, **op) == result
    )
    record = ExportRecord.objects.get(pk=result["data"]["export_id"])
    initial = bytes(record.document)
    assert b"Sample Student" in ZipFile(io.BytesIO(initial)).read("word/document.xml")
    save_marks(faculty, register.pk, rows=[{"usn": "001", "A1": "19"}], **operation(register))
    client.force_login(faculty)
    response = client.get(reverse("export-download", args=[record.pk]))
    assert response.status_code == 200 and response.content == initial
    client.force_login(other_faculty)
    assert client.get(reverse("export-download", args=[record.pk])).status_code == 404


@pytest.mark.parametrize(
    "tab",
    [
        "students",
        "lessons",
        "timetable",
        "sessions",
        "holidays",
        "attendance",
        "rules",
        "marks",
        "exports",
        "preview",
    ],
)
def test_all_workspace_pages_are_private_and_render(client, faculty, other_faculty, register, tab):
    client.force_login(faculty)
    response = client.get(reverse("register-workspace", args=[register.pk, tab]))
    assert response.status_code == 200
    client.force_login(other_faculty)
    assert client.get(reverse("register-workspace", args=[register.pk, tab])).status_code == 404


def test_export_preview_redirects_and_is_private(client, faculty, other_faculty, register):
    client.force_login(faculty)
    record = ExportRecord.objects.create(
        register=register,
        owner=faculty,
        source_revision=register.revision,
        snapshot=build_export_snapshot(faculty, register.pk, through=date(2026, 10, 4), draft=True),
        checksum="dummy",
        document=b"docx-data",
    )
    response = client.get(reverse("export-preview", args=[record.pk]))
    assert response.status_code == 302
    assert f"export={record.pk}" in response.url
    client.force_login(other_faculty)
    assert client.get(reverse("export-preview", args=[record.pk])).status_code == 404


def test_paste_preview_does_not_write_and_apply_works(client, faculty, register):
    client.force_login(faculty)
    url = reverse("register-workspace", args=[register.pk, "students"])
    op = operation(register)
    response = client.post(
        url,
        {
            "action": "preview",
            "text": "001\tStudent One\n002\tStudent Two",
            "columns": "usn,name",
            "delimiter": "tab",
            **op,
        },
    )
    assert response.status_code == 200 and register.students.count() == 0
    preview_token = response.context["preview_token"]
    response = client.post(url, {"action": "apply_paste", "preview_token": preview_token})
    assert response.status_code == 302 and register.students.count() == 2


def test_invalid_mark_batch_rolls_back(faculty, register):
    student = add_student(faculty, register)
    save_rule(faculty, register.pk, definition=default_rule(), **operation(register))
    with pytest.raises(DomainError):
        save_marks(
            faculty,
            register.pk,
            rows=[{"usn": "001", "A1": "20", "T1": "999"}],
            **operation(register),
        )
    assert not student.marks.exists()


def test_historical_import_requires_time_confirmation(faculty, register):
    add_student(faculty, register)
    apply_paste(
        faculty,
        register.pk,
        table="lessons",
        rows=[
            {
                "original_number": 1,
                "topic": "Historical topic",
                "original_date": "2026-09-01",
                "reported_execution_date": "2026-09-02",
            }
        ],
        **operation(register),
    )
    session = register.sessions.get()
    assert (
        session.status == "conducted"
        and not session.time_confirmed
        and not session.attendance.exists()
    )
    with pytest.raises(DomainError, match="Confirm"):
        save_attendance(
            faculty,
            register.pk,
            session_id=session.pk,
            cells=[],
            complete=True,
            **operation(register),
        )
    save_session(
        faculty,
        register.pk,
        values={
            "id": str(session.pk),
            "start_time": time(11),
            "end_time": time(12),
            "exception_reason": "Confirmed against original register",
        },
        **operation(register),
    )
    save_attendance(
        faculty, register.pk, session_id=session.pk, cells=[], complete=True, **operation(register)
    )
    assert session.attendance.count() == 1
    with pytest.raises(DomainError, match="future"):
        apply_paste(
            faculty,
            register.pk,
            table="lessons",
            rows=[
                {
                    "original_number": 2,
                    "topic": "Future execution",
                    "reported_execution_date": "2026-11-02",
                }
            ],
            **operation(register),
        )


def test_stale_schedule_preview_is_rejected(faculty, register):
    register.refresh_from_db()
    preview = preview_rebuild(register, effective_from=date(2026, 10, 4))
    add_student(faculty, register)
    with pytest.raises(DomainError, match="changed"):
        apply_rebuild(faculty, register.pk, preview=preview, **operation(register))
