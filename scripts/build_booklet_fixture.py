"""Regenerate only the synthetic print fixture; never touches the application DB."""

import json
from datetime import date, timedelta
from pathlib import Path


def build_fixture():
    students = [
        {"id": f"student-{i}", "serial": i, "usn": f"DEMO{i:03}", "name": f"Sample Student {i:02}"}
        for i in range(1, 21)
    ]
    sessions = [
        {
            "id": f"session-{i}",
            "display_number": i,
            "date": str(date(2026, 8, 3) + timedelta(days=i - 1)),
            "period": "1",
            "kind": "lesson",
            "status": "conducted" if i <= 5 else "planned",
        }
        for i in range(1, 76)
    ]
    attendance = {}
    for student in students:
        # Explicit illustration of running present totals, absence and non-membership.
        attendance[student["id"]] = {
            "cells": {
                "session-1": "1",
                "session-2": "2",
                "session-3": "A",
                "session-4": "3",
                "session-5": "A",
            },
            "cumulative": {"present": 3, "eligible": 5, "percentage": "60"},
            "tests": {},
        }
    attendance["student-20"]["cells"] = {
        "session-1": "-",
        "session-2": "-",
        "session-3": "1",
        "session-4": "2",
        "session-5": "A",
    }
    attendance["student-20"]["cumulative"] = {"present": 2, "eligible": 3, "percentage": "66.67"}
    return {
        "schema_version": 1,
        "export_date": "2026-08-07",
        "source_revision": 1,
        "draft": True,
        "warnings": [],
        "register": {
            "id": "synthetic-register",
            "academic_year": "2026-27",
            "branch": "CSE",
            "semester": "5",
            "section": "A",
            "subject": "Sample Computing Course",
            "subject_code": "DEMO501",
            "faculty": "Sample Faculty",
        },
        "students": students,
        "sessions": sessions,
        "lessons": [
            {
                "id": f"lesson-{i}",
                "topic": topic,
                "planned_date": f"0{i}/08/26",
                "execution_date": f"0{i}/08/26",
                "remarks": "",
            }
            for i, topic in enumerate(
                [
                    "Introduction and course outcomes",
                    "Problem solving methods",
                    "Worked examples and discussion",
                ],
                1,
            )
        ],
        "attendance": attendance,
        "column_totals": {
            "0": {
                f"session-{i}": {"present": present, "absent": absent}
                for i, present, absent in [
                    (1, 19, 0),
                    (2, 19, 0),
                    (3, 1, 19),
                    (4, 20, 0),
                    (5, 0, 20),
                ]
            }
        },
        "assessments": {
            "maxima": {
                key: "25" for key in ["A1", "A2", "A3", "assignment", "T1", "T2", "T3", "test"]
            }
            | {"overall": "50"},
            "students": {
                s["id"]: {
                    "raw_marks": {"A1": "20"},
                    "pending_keys": ["A2", "A3", "T1", "T2", "T3"],
                    "status": "pending",
                    "contributions": {},
                    "final_result": None,
                    "display": [
                        "20",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "66.67" if s["serial"] == 20 else "60",
                        "",
                        "",
                    ],
                }
                for s in students
            },
        },
        "timetable": {
            "effective_from": "2026-08-03",
            "slots": [
                {
                    "id": str(index),
                    "label": label,
                    "start": start,
                    "end": end,
                    "break": label in ("Tea break", "Lunch"),
                }
                for index, label, start, end in [
                    (1, "1", "08:30", "09:25"),
                    (2, "2", "09:25", "10:20"),
                    (8, "Tea break", "10:20", "10:35"),
                    (3, "3", "10:35", "11:30"),
                    (4, "4", "11:30", "12:25"),
                    (9, "Lunch", "12:25", "13:15"),
                    (5, "5", "13:15", "14:10"),
                    (6, "6", "14:10", "15:05"),
                    (7, "7", "15:05", "16:00"),
                ]
            ],
            "entries": [
                {
                    "day": day,
                    "period": "1",
                    "time": "08:30 - 09:25",
                    "subject_code": "DEMO501",
                    "section": "5 A",
                    "activity": "Theory",
                }
                for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            ],
        },
    }


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "tests/fixtures/booklet_synthetic.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_fixture(), indent=2) + "\n", encoding="utf-8")
