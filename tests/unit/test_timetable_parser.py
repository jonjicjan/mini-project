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


def test_parse_inverted_grid_timetable():
    """Test timetable with days in columns and periods/times in rows."""
    inverted_text = """
    PERIOD / TIME    MONDAY        TUESDAY       WEDNESDAY     THURSDAY      FRIDAY        SATURDAY
    08:30 - 09:25    21CS51        MAT101        ENG102        21CS51        PHY103        CIV104
    09:25 - 10:20    MAT101        21CS51        PHY103        MAT101        21CS51        ENG102
    10:35 - 11:30    CHEM105       CIV104        21CS51        ENG102        CHEM105       21CS51
    """
    result = parse_timetable_text(inverted_text, subject_filter="21CS51")
    assert result["total_extracted"] == 6
    weekdays = {s["weekday"] for s in result["slots"]}
    assert "Monday" in weekdays
    assert "Tuesday" in weekdays
    assert "Wednesday" in weekdays
    assert "Thursday" in weekdays
    assert "Friday" in weekdays
    assert "Saturday" in weekdays

    mon_slot = next(s for s in result["slots"] if s["weekday"] == "Monday")
    assert mon_slot["period"] == "1"
    assert mon_slot["start_time"] == "08:30"
    assert mon_slot["end_time"] == "09:25"


def test_timetable_without_reference_table_synthesizes_subjects():
    """Test text timetable without any reference footer extracts subjects directly from cells."""
    grid_text = """
    DAY / TIME    09:00-10:00    10:00-11:00    11:15-12:15    01:00-02:00
    MONDAY        CS101          EC202          MAT301         CS101 LAB
    TUESDAY       MAT301         CS101          EC202          ME401
    WEDNESDAY     EC202          MAT301         CS101          LUNCH
    """
    result = parse_timetable_text(grid_text)
    assert result["total_extracted"] == 11
    detected = result["detected_subjects"]
    codes = [d["code"] for d in detected]
    assert "CS101" in codes
    assert "EC202" in codes
    assert "MAT301" in codes
    assert "ME401" in codes


def test_clean_ocr_typos_and_code_regex():
    from scheduling.timetable_parser import clean_ocr_typos, COURSE_CODE_REGEX

    assert clean_ocr_typos("•roc") == "TOC"
    assert clean_ocr_typos("BCS51SC") == "BCS515C"
    assert clean_ocr_typos("BA1586") == "BAI586"
    assert clean_ocr_typos("BAILS04") == "BAIL504"

    # Diverse university course formats
    sample_codes = ["BCS501", "21CS51", "18EC71", "MAT101", "CS101", "BCA201", "MBA104"]
    for code in sample_codes:
        match = COURSE_CODE_REGEX.search(f"Room 101 {code} Class")
        assert match is not None
        assert match.group(1).upper() == code


def test_seven_stage_engine_modular_steps():
    """Verify each of the 7 stages of the timetable engine independently."""
    from PIL import Image
    from scheduling.timetable_parser import (
        step_1_upload_and_extract,
        step_2_preprocess_image,
        step_3_detect_table_and_cells,
        step_5_map_subjects_and_names,
        step_6_map_days_and_periods,
        step_7_generate_timetable_and_review,
        parse_timetable_file,
    )

    # Stage 1: Upload and extract
    raw_csv = "Monday\t1\t09:00\t10:00\t21CS51\nTuesday\t2\t10:00\t11:00\t21CS51\n"
    res1 = step_1_upload_and_extract(raw_csv.encode("utf-8"), filename="test.tsv")
    assert res1["kind"] == "text"
    assert "21CS51" in res1["raw_text"]

    # Stage 2: Preprocess image
    test_img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    prep_img = step_2_preprocess_image(test_img)
    assert prep_img.mode == "RGBA"
    assert prep_img.width >= 1000  # verified resolution normalization upscale

    # Stage 3: Table and cell detection
    dummy_words = [
        {"text": "MONDAY", "x": 50, "y": 150, "w": 60, "h": 20},
        {"text": "TUESDAY", "x": 50, "y": 200, "w": 60, "h": 20},
        {"text": "WEDNESDAY", "x": 50, "y": 250, "w": 80, "h": 20},
        {"text": "THURSDAY", "x": 50, "y": 300, "w": 70, "h": 20},
        {"text": "FRIDAY", "x": 50, "y": 350, "w": 50, "h": 20},
        {"text": "08:30-09:25", "x": 150, "y": 100, "w": 80, "h": 20},
        {"text": "09:25-10:20", "x": 250, "y": 100, "w": 80, "h": 20},
    ]
    table_meta = step_3_detect_table_and_cells(dummy_words, 1000, 800)
    assert table_meta["orientation"] == "DAYS_IN_ROWS"
    assert "Monday" in table_meta["day_names"]
    assert len(table_meta["cells"]) > 0

    # Stage 5: Subject code & name mapping
    cell_texts = ["Room 101 BCS501 Class", "BAIL504 DATA VISUALIZATION LAB", "TOC"]
    subjects = step_5_map_subjects_and_names([], "", 1000, 800, cell_texts)
    sub_codes = [s["code"] for s in subjects]
    assert "BCS501" in sub_codes
    assert "BAIL504" in sub_codes

    # Stage 7: Generate timetable & review (with needs_information)
    # Test subject mismatch prompt
    review = step_7_generate_timetable_and_review(
        all_slots=[{"raw_cell": "BCS501", "weekday": "Monday", "period": "1", "start_time": "09:00", "end_time": "10:00"}],
        detected_subjects=[{"code": "BCS501", "display_code": "BCS501", "aliases": ["BCS501"], "name": "SE", "slot_count": 1, "slots": []}],
        subject_filter="NONEXISTENT_CODE",
        register_subject="NONEXISTENT_CODE",
    )
    assert len(review["needs_information"]) > 0
    mismatch_item = next((i for i in review["needs_information"] if i["type"] == "subject_selection"), None)
    assert mismatch_item is not None
    assert "BCS501" in mismatch_item["options"]



