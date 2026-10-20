import csv
from datetime import datetime, time
import io
import re

from core.dates import parse_date

FIELDS = {
    "students": ["usn", "name", "eligible_from", "eligible_to"],
    "lessons": [
        "original_number",
        "topic",
        "original_date",
        "original_period",
        "reported_execution_date",
        "remarks",
    ],
    "marks": ["usn", "A1", "A2", "A3", "T1", "T2", "T3"],
    "timetable": [
        "weekday",
        "period",
        "start_time",
        "end_time",
        "effective_from",
        "effective_to",
    ],
}

WEEKDAY_MAP = {
    "monday": 0,
    "mon": 0,
    "0": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "1": 1,
    "wednesday": 2,
    "wed": 2,
    "2": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "3": 3,
    "friday": 4,
    "fri": 4,
    "4": 4,
    "saturday": 5,
    "sat": 5,
    "5": 5,
    "sunday": 6,
    "sun": 6,
    "6": 6,
}


def parse_weekday_value(val):
    if val is None or str(val).strip() == "":
        raise ValueError("Weekday is required.")
    s = str(val).strip().lower()
    if s in WEEKDAY_MAP:
        return WEEKDAY_MAP[s]
    raise ValueError(f"Invalid weekday '{val}'. Enter Monday–Sunday or Mon–Sun.")


def parse_time_str(val):
    if isinstance(val, time):
        return val
    if not val or not str(val).strip():
        raise ValueError("Time is required.")
    cleaned = str(val).strip().upper().replace(".", ":")
    cleaned = re.sub(r"([0-9])([AP]M)", r"\1 \2", cleaned)
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p", "%I %p"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            return time(dt.hour, dt.minute)
        except ValueError:
            pass
    raise ValueError(f"Invalid time format: '{val}'. Use HH:MM or HH:MM AM/PM.")


def preview_paste(text, *, table, delimiter="tab", mapping=None):
    if table not in FIELDS or delimiter not in ("tab", "comma"):
        raise ValueError("Select a supported table and delimiter.")
    if len(text) > 500_000:
        raise ValueError("Paste at most 500,000 characters at a time.")
    mapping = mapping or {key: i for i, key in enumerate(FIELDS[table])}
    if any(key not in FIELDS[table] or type(i) is not int or i < 0 for key, i in mapping.items()):
        raise ValueError("Invalid column mapping.")
    rows, errors, seen = [], [], set()
    try:
        for number, cells in enumerate(
            csv.reader(
                io.StringIO(text), delimiter="\t" if delimiter == "tab" else ",", strict=True
            ),
            1,
        ):
            if number > 2000:
                raise ValueError("Import at most 2,000 rows at a time.")
            if not any(cell.strip() for cell in cells):
                continue
            row = {key: cells[i].strip() if i < len(cells) else "" for key, i in mapping.items()}
            if number == 1 and any(
                row.get(key, "").lower() == key
                for key in ("usn", "original_number", "weekday")
            ):
                continue
            for key, value in row.items():
                if value and (
                    key.endswith("date")
                    or key in ("eligible_from", "eligible_to", "effective_from", "effective_to")
                ):
                    try:
                        row[key] = parse_date(value).isoformat()
                    except ValueError as error:
                        errors.append({"row": number, "column": key, "message": str(error)})

            if table == "timetable":
                if not row.get("period"):
                    errors.append(
                        {"row": number, "column": "period", "message": "Period is required."}
                    )
                try:
                    row["weekday"] = parse_weekday_value(row.get("weekday"))
                except ValueError as error:
                    errors.append({"row": number, "column": "weekday", "message": str(error)})

                st_obj = None
                if row.get("start_time"):
                    try:
                        st_obj = parse_time_str(row["start_time"])
                        row["start_time"] = st_obj.strftime("%H:%M")
                    except ValueError as error:
                        errors.append(
                            {"row": number, "column": "start_time", "message": str(error)}
                        )
                else:
                    errors.append(
                        {"row": number, "column": "start_time", "message": "Start time is required."}
                    )

                et_obj = None
                if row.get("end_time"):
                    try:
                        et_obj = parse_time_str(row["end_time"])
                        row["end_time"] = et_obj.strftime("%H:%M")
                    except ValueError as error:
                        errors.append({"row": number, "column": "end_time", "message": str(error)})
                else:
                    errors.append(
                        {"row": number, "column": "end_time", "message": "End time is required."}
                    )

                if st_obj and et_obj and et_obj <= st_obj:
                    errors.append(
                        {
                            "row": number,
                            "column": "end_time",
                            "message": "End time must be after start time.",
                        }
                    )

                if row.get("effective_from") and row.get("effective_to"):
                    if row["effective_to"] < row["effective_from"]:
                        errors.append(
                            {
                                "row": number,
                                "column": "effective_to",
                                "message": "Effective to date cannot be earlier than effective from.",
                            }
                        )

                if st_obj and et_obj and "weekday" in row and isinstance(row["weekday"], int):
                    for prev_row in rows:
                        if (
                            prev_row.get("weekday") == row["weekday"]
                            and prev_row.get("start_time")
                            and prev_row.get("end_time")
                        ):
                            if (
                                prev_row["start_time"] < row["end_time"]
                                and row["start_time"] < prev_row["end_time"]
                            ):
                                r_from = row.get("effective_from") or "0001-01-01"
                                r_to = row.get("effective_to") or "9999-12-31"
                                p_from = prev_row.get("effective_from") or "0001-01-01"
                                p_to = prev_row.get("effective_to") or "9999-12-31"
                                if r_from <= p_to and p_from <= r_to:
                                    errors.append(
                                        {
                                            "row": number,
                                            "column": "start_time",
                                            "message": f"Time overlaps with row {rows.index(prev_row) + 1} on the same weekday.",
                                        }
                                    )

            if table == "timetable":
                w = str(row.get("weekday", ""))
                p = str(row.get("period", "")).strip().upper()
                s = str(row.get("start_time", "")).strip()
                identity = f"{w}-{p or s}"
                id_col = "period" if p else "start_time"
            elif table == "lessons":
                identity = row.get("original_number", "").strip().upper()
                id_col = "original_number"
            else:
                identity = row.get("usn", "").strip().upper()
                id_col = "usn"

            if not identity or identity in seen:
                errors.append(
                    {
                        "row": number,
                        "column": id_col,
                        "message": "A non-empty, unique identifier is required in each batch.",
                    }
                )
            seen.add(identity)
            rows.append(row)
    except csv.Error as error:
        errors.append({"row": number, "column": "CSV", "message": str(error)})
    return {
        "rows": rows,
        "errors": errors,
        "warnings": ["Existing rows are updated; omitted rows are kept."],
    }
