from datetime import date
from scheduling.timetable_parser import parse_timetable_text, extract_time_ranges_from_line


def test_parse_grid_timetable_with_subject_filter():
    grid_text = """
    DAY / TIME    08:30-09:25    09:25-10:20    10:35-11:30    11:30-12:25    01:15-02:10
    MONDAY        MATH           21CS51         CHEM           ENGLISH        LUNCH
    TUESDAY       21CS51         PHY            CIV            MATH           SPORTS
    WEDNESDAY     ELECTIVE       MATH           21CS51         CIV            FREE
    THURSDAY      PHY            CHEM           MATH           21CS51         CLUB
    FRIDAY        21CS51         MATH           CHEM           ENGLISH        FREE
    """
    result = parse_timetable_text(
        grid_text,
        subject_filter="21CS51",
        term_start=date(2026, 9, 8),
        term_end=date(2026, 12, 30),
    )
    assert result["total_extracted"] == 5
    # Monday period 2
    mon_slot = next(s for s in result["slots"] if s["weekday"] == "Monday")
    assert mon_slot["period"] == "2"
    assert mon_slot["start_time"] == "09:25"
    assert mon_slot["end_time"] == "10:20"
    assert mon_slot["effective_from"] == "2026-09-08"
    assert mon_slot["effective_to"] == "2026-12-30"


def test_parse_line_by_line_timetable():
    list_text = """
    Monday Period 1 09:00 - 10:00 (21CS51 Class)
    Wednesday Period 3 11:15 AM - 12:15 PM (21CS51 Lab)
    Friday Period 4 02:10 PM - 03:05 PM (21CS51 Tutorial)
    """
    result = parse_timetable_text(list_text, subject_filter="21CS51")
    assert result["total_extracted"] == 3
    assert result["slots"][0]["weekday"] == "Monday"
    assert result["slots"][0]["start_time"] == "09:00"
    assert result["slots"][0]["end_time"] == "10:00"

    assert result["slots"][1]["weekday"] == "Wednesday"
    assert result["slots"][1]["start_time"] == "11:15"
    assert result["slots"][1]["end_time"] == "12:15"

    assert result["slots"][2]["weekday"] == "Friday"
    assert result["slots"][2]["start_time"] == "14:10"
    assert result["slots"][2]["end_time"] == "15:05"


def test_parse_tab_separated_timetable():
    tsv_text = """
    Monday\t1\t09:00\t10:00
    Tuesday\t2\t10:00\t11:00
    Thursday\t3\t11:15\t12:15
    """
    result = parse_timetable_text(tsv_text)
    assert result["total_extracted"] == 3
    assert [s["weekday"] for s in result["slots"]] == ["Monday", "Tuesday", "Thursday"]


def test_parse_ksit_master_timetable_image_bcs501():
    from pathlib import Path
    from scheduling.timetable_parser import parse_timetable_from_image

    img_path = Path(
        r"C:\Users\Jamal Khan\.gemini\antigravity\brain\4a63b49a-bd63-42e5-8dcd-e7a8d22631ff\.user_uploaded\media_1794761005759_3acb7d71.jpg"
    )
    if not img_path.is_file():
        return

    with img_path.open("rb") as f:
        result = parse_timetable_from_image(f, subject_filter="BCS501")

    assert result["total_extracted"] >= 3
    slots = result["slots"]
    weekdays = [s["weekday"] for s in slots]
    # BCS501 (SE&PM) has Monday Period 2, Friday Period 1, Wednesday Period 7, etc.
    assert "Monday" in weekdays
    mon = next(s for s in slots if s["weekday"] == "Monday")
    assert mon["period"] == "2"
    assert mon["start_time"] == "09:25"
    assert mon["end_time"] == "10:20"

    assert "Friday" in weekdays
    fri = next(s for s in slots if s["weekday"] == "Friday")
    assert fri["period"] == "1"
    assert fri["start_time"] == "08:30"
    assert fri["end_time"] == "09:25"


def test_parse_ksit_master_timetable_image_bail504_lab():
    from pathlib import Path
    from scheduling.timetable_parser import parse_timetable_from_image

    img_path = Path(
        r"C:\Users\Jamal Khan\.gemini\antigravity\brain\4a63b49a-bd63-42e5-8dcd-e7a8d22631ff\.user_uploaded\media_1794761005759_3acb7d71.jpg"
    )
    if not img_path.is_file():
        return

    with img_path.open("rb") as f:
        result = parse_timetable_from_image(f, subject_filter="BAIL504")

    assert result["total_extracted"] == 4
    # Spans Wednesday P3, P4 and Thursday P3, P4
    days = {s["weekday"] for s in result["slots"]}
    assert "Wednesday" in days
    assert "Thursday" in days
    periods = {s["period"] for s in result["slots"]}
    assert periods == {"3", "4"}


def test_parse_ksit_master_timetable_detected_subjects():
    from pathlib import Path
    from scheduling.timetable_parser import parse_timetable_from_image

    img_path = Path(
        r"C:\Users\Jamal Khan\.gemini\antigravity\brain\4a63b49a-bd63-42e5-8dcd-e7a8d22631ff\.user_uploaded\media_1794761005759_3acb7d71.jpg"
    )
    if not img_path.is_file():
        return

    with img_path.open("rb") as f:
        result = parse_timetable_from_image(f)

    detected = result["detected_subjects"]
    codes = [d["code"] for d in detected]
    assert "BCS501" in codes
    assert "BCS502" in codes
    assert "BCS503" in codes
    assert "BAIL504" in codes
    assert "BCS515C" in codes
    assert "BRMK557" in codes
    assert "BAI586" in codes
    assert len(result["all_slots"]) >= 30

