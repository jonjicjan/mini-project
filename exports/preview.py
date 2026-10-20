"""Data preparation for in-browser HTML print preview matching Word booklet geometry."""

import math
from .leaves import plan_leaves


def prepare_booklet_preview(snapshot: dict) -> dict:
    if snapshot.get("schema_version") != 1:
        raise ValueError("Unsupported snapshot schema version.")

    register = snapshot["register"]
    lessons = snapshot["lessons"]
    students = snapshot["students"]
    sessions = snapshot["sessions"]
    attendance_data = snapshot["attendance"]
    totals_data = snapshot["column_totals"]
    assessments_data = snapshot["assessments"]
    timetable_data = snapshot["timetable"]

    pages = []
    page_num = 1

    # --- 1. Lesson Plan Pages ---
    capacities = [20, 25, 25]
    if len(lessons) > 70:
        capacities.extend([25] * math.ceil((len(lessons) - 70) / 25))

    start_idx = 0
    for page_idx, capacity in enumerate(capacities):
        is_first = (page_idx == 0)
        is_last = (page_idx == len(capacities) - 1)
        page_rows = []
        for i in range(start_idx, start_idx + capacity):
            lesson = lessons[i] if i < len(lessons) else {}
            page_rows.append({
                "number": i + 1,
                "topic": lesson.get("topic", ""),
                "planned_date": lesson.get("planned_date", ""),
                "execution_date": lesson.get("execution_date", ""),
                "remarks": lesson.get("remarks", ""),
            })

        pages.append({
            "type": "lesson",
            "page_number": page_num,
            "width_mm": 210,
            "height_mm": 307,
            "is_half": False,
            "title": "Lesson Plan & Execution",
            "is_first": is_first,
            "is_last": is_last,
            "rows": page_rows,
            "start_class": start_idx + 1,
            "end_class": start_idx + capacity,
        })
        page_num += 1
        start_idx += capacity

    # --- 2. Attendance & Assessment Pages (Leaves) ---
    leaves = plan_leaves(len(students), len(sessions))
    for leaf in leaves:
        is_half = (leaf.kind == "continuation")
        width_mm = 105 if is_half else 210

        # Sessions for this panel
        selected_sessions = [
            sessions[i] if i < len(sessions) else {}
            for i in range(leaf.session_start, leaf.session_end)
        ]

        # Column totals
        block_totals = totals_data.get(str(leaf.student_start), {})
        col_present = [block_totals.get(s.get("id", ""), {}).get("present", "") for s in selected_sessions]
        col_absent = [block_totals.get(s.get("id", ""), {}).get("absent", "") for s in selected_sessions]

        # Student rows
        student_rows = []
        final_batch = (leaf.session_end >= len(sessions))

        for idx in range(leaf.student_start, leaf.student_end):
            if idx < len(students):
                st = students[idx]
                st_id = st["id"]
                st_cells = attendance_data.get(st_id, {}).get("cells", {})
                row_cells = [st_cells.get(s.get("id", ""), "") for s in selected_sessions]

                # Assessment summary cells
                if leaf.kind == "assessment":
                    st_assess = assessments_data["students"].get(st_id, {})
                    display_vals = st_assess.get("display", [""] * 13) if final_batch else [""] * 13
                else:
                    display_vals = []

                student_rows.append({
                    "serial": st["serial"],
                    "usn": st["usn"],
                    "name": st["name"],
                    "cells": row_cells,
                    "assessments": display_vals,
                })
            else:
                # Blank filler row to maintain fixed capacity
                student_rows.append({
                    "serial": "",
                    "usn": "",
                    "name": "",
                    "cells": ["" for _ in selected_sessions],
                    "assessments": ["" for _ in range(13)] if leaf.kind == "assessment" else [],
                })

        # Assessment headers & maxima
        assessment_headers = []
        if leaf.kind == "assessment":
            if "preview_labels" in assessments_data:
                assessment_headers = assessments_data["preview_labels"]
            else:
                maxima = assessments_data.get("maxima", {})
                weighted = assessments_data.get("weighted_contributions", False)
                labels = [
                    ("A1", f"/{maxima.get('A1', '25')}"),
                    ("A2", f"/{maxima.get('A2', '25')}"),
                    ("A3", f"/{maxima.get('A3', '25')}"),
                    ("Assign. contrib." if weighted else "Assign. avg.", f"/{maxima.get('assignment', '20')}"),
                    ("Test I Att. %", ""),
                    ("Test I Marks", f"/{maxima.get('T1', '25')}"),
                    ("Test II Att. %", ""),
                    ("Test II Marks", f"/{maxima.get('T2', '25')}"),
                    ("Test III Att. %", ""),
                    ("Test III Marks", f"/{maxima.get('T3', '25')}"),
                    ("Final Att. %", ""),
                    ("Test contrib." if weighted else "Final Marks", f"/{maxima.get('test', '30')}"),
                    ("Overall", f"/{maxima.get('overall', '50')}"),
                ]
                assessment_headers = labels

        pages.append({
            "type": "attendance",
            "page_number": page_num,
            "width_mm": width_mm,
            "height_mm": 307,
            "is_half": is_half,
            "kind": leaf.kind,
            "student_start": leaf.student_start + 1,
            "student_end": min(leaf.student_end, len(students)),
            "session_start": leaf.session_start + 1,
            "session_end": leaf.session_end,
            "sessions": selected_sessions,
            "student_rows": student_rows,
            "col_present": col_present,
            "col_absent": col_absent,
            "assessment_headers": assessment_headers,
        })
        page_num += 1

    # --- 3. Timetable Pages ---
    tt_entries = timetable_data.get("entries", [])
    tt_slots = timetable_data.get("slots", [])
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if not any(e.get("day") == "Sunday" for e in tt_entries):
        days.remove("Sunday")

    for start_slot in range(0, max(1, len(tt_slots)), 9):
        selected_slots = tt_slots[start_slot : start_slot + 9]
        if not selected_slots:
            break

        day_rows = []
        for d in days:
            cell_vals = []
            for slot in selected_slots:
                matches = [
                    e for e in tt_entries
                    if e.get("day") == d and e.get("period") == slot.get("id")
                ]
                text = " / ".join(f"{m.get('subject_code', '')} ({m.get('section', '')})" for m in matches)
                cell_vals.append(text)
            day_rows.append({"day": d, "cells": cell_vals})

        pages.append({
            "type": "timetable",
            "page_number": page_num,
            "width_mm": 210,
            "height_mm": 307,
            "is_half": False,
            "title": f"Faculty Timetable{' continued' if start_slot else ''}",
            "effective_from": timetable_data.get("effective_from", ""),
            "slots": selected_slots,
            "day_rows": day_rows,
        })
        page_num += 1

    return {
        "register": register,
        "export_date": snapshot.get("export_date"),
        "source_revision": snapshot.get("source_revision"),
        "draft": snapshot.get("draft", True),
        "warnings": snapshot.get("warnings", []),
        "pages": pages,
        "total_pages": len(pages),
    }
