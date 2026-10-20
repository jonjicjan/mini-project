import hashlib
import tempfile
from decimal import Decimal
from pathlib import Path

from django.db import transaction

from assessments.calculations import KEYS, calculate_score, decimal, default_rule
from attendance.services import attendance_summaries
from core.errors import DomainError, conflict
from core.models import MutationReceipt
from core.mutations import json_value
from registers.entries import mutate_register
from registers.services import owned_register

from .docx_render import render_booklet
from .models import ExportRecord


def display(value):
    return (
        ""
        if value is None
        else str(Decimal(value).quantize(Decimal("0.01"))).rstrip("0").rstrip(".")
    )


def build_export_snapshot(actor, register_id, *, through, draft):
    register = owned_register(actor, register_id)
    students = list(register.students.prefetch_related("marks"))
    sessions = sorted(
        register.sessions.exclude(status="cancelled"),
        key=lambda s: (s.date, s.start_time, str(s.pk)),
    )
    rule = register.marking_rule.definition if hasattr(register, "marking_rule") else default_rule()
    warnings = (
        [] if hasattr(register, "marking_rule") else ["Assessment rules have not been confirmed."]
    )
    attendance, assessments = {}, {}
    tests = {s.test_number: s for s in sessions if s.kind == "test"}
    summary_sets = {
        day: attendance_summaries(register.pk, through=day)
        for day in {through, *(s.date for s in tests.values() if s.date <= through)}
    }
    if any(s.status == "planned" and s.date <= through for s in sessions):
        warnings.append(
            "Past planned classes remain unconfirmed; complete or cancel them before issuing a final export."
        )
    for student in students:
        summary = summary_sets[through][str(student.pk)]
        attendance[str(student.pk)] = {
            "cells": summary["sequence"],
            "cumulative": summary,
            "tests": {},
        }
        if summary["provisional"]:
            warnings.append(
                f"{student.usn}: attendance is incomplete or has an unresolved schedule conflict."
            )
        marks = {
            m.assessment_key: {
                "status": m.status,
                "value": str(m.value) if m.value is not None else None,
            }
            for m in student.marks.all()
        }
        for number in (1, 2, 3):
            if number not in tests or tests[number].date > through:
                marks[f"T{number}"] = {"status": "missing", "value": None}
        result = calculate_score(rule, marks)
        if result["status"] == "pending":
            warnings.append(f"{student.usn}: assessment result is pending.")

        def raw(key):
            mark = marks.get(key, {})
            return "AB" if mark.get("status") == "absent" else display(mark.get("value"))

        values = [raw(k) for k in KEYS[:3]] + [display(result["contributions"].get("assignments"))]
        for number in (1, 2, 3):
            test = tests.get(number)
            percent = None
            if test and test.date <= through and test.status == "conducted":
                test_summary = summary_sets[test.date][str(student.pk)]
                attendance[str(student.pk)]["tests"][str(number)] = test_summary
                percent = test_summary["percentage"]
            values.extend([display(percent), raw(f"T{number}")])
        values.extend(
            [
                display(summary["percentage"]),
                display(result["contributions"].get("tests")),
                display(result["rounded"]),
            ]
        )
        assessments[str(student.pk)] = {
            "raw_marks": marks,
            **result,
            "display": values,
            "final_result": result["rounded"],
        }
    totals = {}
    for start in range(0, len(students), 20):
        totals[str(start)] = {}
        for session in sessions:
            if session.status != "conducted" or session.date > through:
                continue
            cells = [
                attendance[str(s.pk)]["cells"].get(str(session.pk), "")
                for s in students[start : start + 20]
            ]
            totals[str(start)][str(session.pk)] = {
                "present": sum(v.isdigit() for v in cells),
                "absent": cells.count("A"),
                "unmarked": cells.count(""),
            }
    active_entries = [
        e
        for e in register.timetable_entries.all()
        if e.effective_from <= through and (not e.effective_to or through <= e.effective_to)
    ]
    slots, entries = {}, []
    for entry in active_entries:
        key = f"{entry.period}-{entry.start_time}-{entry.end_time}"
        slots[key] = {
            "id": key,
            "label": entry.period,
            "start": entry.start_time.strftime("%H:%M"),
            "end": entry.end_time.strftime("%H:%M"),
            "break": False,
        }
        entries.append(
            {
                "day": entry.get_weekday_display(),
                "period": key,
                "subject_code": register.subject_code,
                "section": register.section,
                "activity": "Theory",
            }
        )
    if not slots:
        slots["blank"] = {
            "id": "blank",
            "label": "Unassigned",
            "start": "",
            "end": "",
            "break": False,
        }
    maxima = dict(rule["assessments"])
    assign_comp = next(
        (c for c in rule.get("components", []) if c.get("id") == "assignments"),
        rule["components"][0] if rule.get("components") else None,
    )
    test_comp = next(
        (c for c in rule.get("components", []) if c.get("id") == "tests"),
        rule["components"][1] if len(rule.get("components", [])) > 1 else None,
    )

    assign_max = (
        decimal(rule["final_maximum"]) * decimal(assign_comp["weight_percent"]) / 100
        if assign_comp and "weight_percent" in assign_comp
        else Decimal("20")
    )
    test_max = (
        decimal(rule["final_maximum"]) * decimal(test_comp["weight_percent"]) / 100
        if test_comp and "weight_percent" in test_comp
        else Decimal("30")
    )

    def format_clean_num(d):
        d_val = decimal(d)
        return str(int(d_val) if d_val == int(d_val) else d_val)

    maxima.update(
        {
            "assignment": format_clean_num(assign_max),
            "test": format_clean_num(test_max),
            "overall": format_clean_num(rule["final_maximum"]),
        }
    )

    if assign_comp:
        agg = assign_comp.get("aggregation")
        if agg == "best_n":
            n = assign_comp.get("best_n", 2)
            assign_docx = f"Assign.\nBest-{n}"
            assign_preview = f"Assign. Best-{n}"
        elif agg == "sum_ratio":
            assign_docx = "Assign.\nScore"
            assign_preview = "Assign. Score"
        elif assign_comp.get("weight_percent") and decimal(assign_comp["weight_percent"]) != 100:
            assign_docx = "Assign.\ncontrib."
            assign_preview = "Assign. contrib."
        else:
            assign_docx = "Assign.\navg."
            assign_preview = "Assign. avg."
    else:
        assign_docx = "Assign.\navg."
        assign_preview = "Assign. avg."

    if test_comp:
        agg = test_comp.get("aggregation")
        if agg == "best_n":
            n = test_comp.get("best_n", 2)
            test_docx = f"Test\nBest-{n}"
            test_preview = f"Test Best-{n}"
        elif agg == "sum_ratio":
            test_docx = "Test\nScore"
            test_preview = "Test Score"
        elif test_comp.get("weight_percent") and decimal(test_comp["weight_percent"]) != 100:
            test_docx = "Test\ncontrib."
            test_preview = "Test contrib."
        else:
            test_docx = "Final\nMarks"
            test_preview = "Final Marks"
    else:
        test_docx = "Final\nMarks"
        test_preview = "Final Marks"

    labels = [
        "A1",
        "A2",
        "A3",
        assign_docx,
        "Test I\nAtt. %",
        "Test I\nMarks",
        "Test II\nAtt. %",
        "Test II\nMarks",
        "Test III\nAtt. %",
        "Test III\nMarks",
        "Final\nAtt. %",
        test_docx,
        "Overall",
    ]

    preview_labels = [
        ("A1", f"/{maxima.get('A1', '25')}"),
        ("A2", f"/{maxima.get('A2', '25')}"),
        ("A3", f"/{maxima.get('A3', '25')}"),
        (assign_preview, f"/{maxima['assignment']}"),
        ("Test I Att. %", ""),
        ("Test I Marks", f"/{maxima.get('T1', '25')}"),
        ("Test II Att. %", ""),
        ("Test II Marks", f"/{maxima.get('T2', '25')}"),
        ("Test III Att. %", ""),
        ("Test III Marks", f"/{maxima.get('T3', '25')}"),
        ("Final Att. %", ""),
        (test_preview, f"/{maxima['test']}"),
        ("Overall", f"/{maxima['overall']}"),
    ]
    snapshot = {
        "schema_version": 1,
        "export_date": through,
        "source_revision": register.revision,
        "draft": draft,
        "warnings": list(dict.fromkeys(warnings)),
        "register": {
            "id": str(register.pk),
            "academic_year": register.academic_year,
            "branch": register.branch,
            "semester": register.semester,
            "section": register.section,
            "subject": register.subject_name,
            "subject_code": register.subject_code,
            "faculty": register.faculty_name,
        },
        "students": [
            {"id": str(s.pk), "usn": s.usn, "name": s.name, "serial": s.serial_number}
            for s in students
        ],
        "lessons": [
            {
                "id": str(lesson.pk),
                "topic": lesson.topic,
                "planned_date": lesson.original_date.strftime("%d/%m/%y")
                if lesson.original_date
                else "",
                "execution_date": next(
                    (
                        s.actual_date.strftime("%d/%m/%y")
                        for s in sessions
                        if s.lesson_id == lesson.pk
                        and s.status == "conducted"
                        and s.actual_date
                        and s.actual_date <= through
                    ),
                    "",
                ),
                "remarks": lesson.remarks,
            }
            for lesson in register.lessons.all()
        ],
        "sessions": [
            {
                "id": str(s.pk),
                "display_number": n,
                "date": s.date,
                "period": s.period,
                "kind": s.kind,
                "status": s.status,
            }
            for n, s in enumerate(sessions, 1)
        ],
        "attendance": attendance,
        "column_totals": totals,
        "assessments": {
            "maxima": maxima,
            "students": assessments,
            "weighted_contributions": True,
            "labels": labels,
            "preview_labels": preview_labels,
        },
        "timetable": {
            "effective_from": through,
            "slots": sorted(slots.values(), key=lambda s: (s["start"], s["id"])),
            "entries": entries,
        },
    }
    return json_value(snapshot)


def create_export(actor, register_id, *, through, draft, expected_revision, request_id):
    # Retry an acknowledged or lost response through the same ownership/digest checks.
    try:
        import uuid

        operation_id = uuid.UUID(str(request_id))
    except (ValueError, TypeError):
        raise DomainError("A valid operation ID is required.") from None
    if MutationReceipt.objects.filter(actor=actor, request_id=operation_id).exists():
        return mutate_register(
            actor,
            register_id,
            action="create_word_export",
            values={"through": through, "draft": draft},
            change=lambda register: None,
            expected_revision=expected_revision,
            request_id=request_id,
        )
    # Capture one database revision; expensive Word rendering happens after release.
    with transaction.atomic():
        snapshot = build_export_snapshot(actor, register_id, through=through, draft=draft)
        if snapshot["source_revision"] != expected_revision:
            raise conflict("Register changed. Reload before exporting.")
    with tempfile.TemporaryDirectory(prefix="faculty-export-") as directory:
        target = Path(directory) / "register.docx"
        warnings = render_booklet(snapshot, target)
        content = target.read_bytes()
    snapshot["warnings"] = warnings
    if warnings and not draft:
        raise DomainError("Resolve these issues or create a draft: " + " · ".join(warnings[:8]))

    def change(register):
        record = ExportRecord.objects.create(
            register=register,
            owner=actor,
            source_revision=snapshot["source_revision"],
            snapshot=snapshot,
            checksum=hashlib.sha256(content).hexdigest(),
            document=content,
        )
        try:
            from django.conf import settings
            downloads_dir = settings.BASE_DIR / "downloads"
            downloads_dir.mkdir(exist_ok=True)
            (downloads_dir / f"register-{record.pk}.docx").write_bytes(content)
        except Exception:
            pass
        return {"export_id": str(record.pk), "checksum": record.checksum, "warnings": warnings}

    return mutate_register(
        actor,
        register_id,
        action="create_word_export",
        values={"through": through, "draft": draft},
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )
