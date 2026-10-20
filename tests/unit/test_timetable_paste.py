import pytest
from datetime import time

from registers.paste import parse_time_str, parse_weekday_value, preview_paste


def test_parse_weekday_value():
    assert parse_weekday_value("Monday") == 0
    assert parse_weekday_value("mon") == 0
    assert parse_weekday_value("0") == 0
    assert parse_weekday_value("Friday") == 4
    assert parse_weekday_value("fri") == 4
    assert parse_weekday_value("Sunday") == 6
    assert parse_weekday_value("sun") == 6

    with pytest.raises(ValueError, match="Invalid weekday"):
        parse_weekday_value("Funday")
    with pytest.raises(ValueError, match="Weekday is required"):
        parse_weekday_value("")


def test_parse_time_str():
    assert parse_time_str("09:00") == time(9, 0)
    assert parse_time_str("9:00") == time(9, 0)
    assert parse_time_str("9:00 AM") == time(9, 0)
    assert parse_time_str("9:00AM") == time(9, 0)
    assert parse_time_str("09.00 AM") == time(9, 0)
    assert parse_time_str("14:30") == time(14, 30)
    assert parse_time_str("2:30 PM") == time(14, 30)
    assert parse_time_str("2:30pm") == time(14, 30)

    with pytest.raises(ValueError, match="Invalid time format"):
        parse_time_str("invalid-time")
    with pytest.raises(ValueError, match="Time is required"):
        parse_time_str("")


def test_preview_paste_timetable_valid():
    text = (
        "weekday\tperiod\tstart_time\tend_time\teffective_from\teffective_to\n"
        "Monday\t1\t09:00\t10:00\t2026-08-01\t2026-12-31\n"
        "Monday\t2\t10:00\t11:00\t2026-08-01\t2026-12-31\n"
        "Wednesday\t3\t11:15\t12:15\t2026-08-01\t2026-12-31\n"
    )
    result = preview_paste(text, table="timetable", delimiter="tab")
    assert not result["errors"]
    assert len(result["rows"]) == 3
    assert result["rows"][0]["weekday"] == 0
    assert result["rows"][0]["period"] == "1"
    assert result["rows"][0]["start_time"] == "09:00"
    assert result["rows"][0]["end_time"] == "10:00"
    assert result["rows"][2]["weekday"] == 2


def test_preview_paste_timetable_end_before_start_error():
    text = "Monday\t1\t10:00\t09:00\t2026-08-01\t2026-12-31\n"
    result = preview_paste(text, table="timetable", delimiter="tab")
    assert any("End time must be after start time" in e["message"] for e in result["errors"])


def test_preview_paste_timetable_batch_overlap_error():
    # Two slots on Monday that overlap in time
    text = (
        "Monday\t1\t09:00\t10:30\t2026-08-01\t2026-12-31\n"
        "Monday\t2\t10:00\t11:00\t2026-08-01\t2026-12-31\n"
    )
    result = preview_paste(text, table="timetable", delimiter="tab")
    assert any("Time overlaps" in e["message"] for e in result["errors"])


def test_preview_paste_timetable_duplicate_period_error():
    text = (
        "Monday\t1\t09:00\t10:00\t2026-08-01\t2026-12-31\n"
        "Monday\t1\t11:00\t12:00\t2026-08-01\t2026-12-31\n"
    )
    result = preview_paste(text, table="timetable", delimiter="tab")
    assert any("unique identifier is required" in e["message"] for e in result["errors"])
