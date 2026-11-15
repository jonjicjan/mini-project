"""Intelligent parser for timetable text extracted from images (OCR) and PDF files.

Extracts weekly recurring timetable slots, period numbers, time windows, and weekdays
from common college timetable layouts (grid matrices, tabular text, and list routines).
"""

from datetime import date, time
import io
import re
from typing import Any, Dict, List, Optional

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

WEEKDAY_PATTERNS = {
    0: re.compile(r"\b(?:mon(?:day)?|monday)\b", re.IGNORECASE),
    1: re.compile(r"\b(?:tue(?:s|sday)?|tuesday)\b", re.IGNORECASE),
    2: re.compile(r"\b(?:wed(?:nesday)?|wednesday)\b", re.IGNORECASE),
    3: re.compile(r"\b(?:thu(?:r|rs|rsday)?|thursday)\b", re.IGNORECASE),
    4: re.compile(r"\b(?:fri(?:day)?|friday)\b", re.IGNORECASE),
    5: re.compile(r"\b(?:sat(?:urday)?|saturday)\b", re.IGNORECASE),
    6: re.compile(r"\b(?:sun(?:day)?|sunday)\b", re.IGNORECASE),
}

# Standard time range pattern: e.g. "09:00 - 10:00", "9:25 to 10:20", "1:15-2:10"
TIME_RANGE_REGEX = re.compile(
    r"\b(\d{1,2})[:.](\d{2})\s*(AM|PM)?\s*(?:to|-|–|—|/)\s*(\d{1,2})[:.](\d{2})\s*(AM|PM)?\b",
    re.IGNORECASE,
)

PERIOD_REGEX = re.compile(
    r"\b(?:Period|P|Slot|Hour|Hr)?[.\s]*([1-9]|10)\b",
    re.IGNORECASE,
)


def extract_text_from_pdf(file_bytes_or_stream) -> str:
    """Extract all text pages from an uploaded PDF document."""
    if PdfReader is None:
        raise ValueError("pypdf is not available for PDF processing.")
    if isinstance(file_bytes_or_stream, bytes):
        stream = io.BytesIO(file_bytes_or_stream)
    else:
        stream = file_bytes_or_stream
    reader = PdfReader(stream)
    text_chunks = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_chunks.append(page_text)
    return "\n".join(text_chunks)


def normalize_time(hour: int, minute: int, am_pm: Optional[str] = None) -> time:
    """Convert parsed hour/minute to 24-hour time.
    
    If am_pm is omitted, college schedules typically run from 8:00 AM to 5:00 PM.
    Hours 1..6 without PM are treated as afternoon (13:00..18:00).
    """
    if am_pm:
        am_pm = am_pm.upper()
        if am_pm == "PM" and hour < 12:
            hour += 12
        elif am_pm == "AM" and hour == 12:
            hour = 0
    else:
        # College routine heuristics: 1..6 are afternoon classes
        if 1 <= hour <= 6:
            hour += 12
    return time(hour, minute)


def extract_time_ranges_from_line(line: str) -> List[tuple[time, time, str]]:
    """Find all time ranges in a single line or header."""
    matches = []
    for m in TIME_RANGE_REGEX.finditer(line):
        h1, m1, ap1, h2, m2, ap2 = m.groups()
        # If second has PM and first has no AM/PM, inherit PM or infer
        if ap2 and not ap1:
            ap1 = ap2
        t1 = normalize_time(int(h1), int(m1), ap1)
        t2 = normalize_time(int(h2), int(m2), ap2)
        if t2 <= t1:
            # If 12-hour wrap (e.g. 11:30 to 12:25, or 11:30 to 1:15)
            if t2.hour < t1.hour:
                t2 = time(t2.hour + 12, t2.minute)
        matches.append((t1, t2, m.group(0)))
    return matches


def match_weekday(text: str) -> Optional[int]:
    """Identify which weekday number (0=Mon .. 6=Sun) matches text."""
    for day_num, pattern in WEEKDAY_PATTERNS.items():
        if pattern.search(text):
            return day_num
    return None


def parse_timetable_text(
    raw_text: str,
    *,
    subject_filter: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Parse raw OCR or PDF timetable text into structured timetable slots.
    
    Args:
        raw_text: Text extracted from PDF or OCR image.
        subject_filter: Optional subject code or keyword (e.g. '21CS51', 'AI') to match slots.
                        If None/empty, extracts all recognized timetable entries.
        term_start: Default start date for effective_from (defaults to today or term_start).
        term_end: Default end date for effective_to.
    
    Returns:
        dict with:
            'slots': list of slot dictionaries
            'warnings': list of parsing notes or skipped lines
            'total_extracted': count of extracted slots
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    slots: List[Dict[str, Any]] = []
    warnings: List[str] = []
    
    clean_filter = subject_filter.strip().upper() if subject_filter and subject_filter.strip() else None
    eff_from_str = term_start.isoformat() if term_start else ""
    eff_to_str = term_end.isoformat() if term_end else ""

    # Strategy 1: Grid Header Detection (Times/Periods in header, Days in rows)
    time_headers: List[tuple[time, time, str]] = []
    header_line_idx = -1
    for idx, line in enumerate(lines[:10]):
        extracted = extract_time_ranges_from_line(line)
        if len(extracted) >= 2:
            time_headers = extracted
            header_line_idx = idx
            break

    # If time headers were found in top lines, parse subsequent lines as day rows
    if time_headers:
        for idx in range(header_line_idx + 1, len(lines)):
            line = lines[idx]
            day_num = match_weekday(line)
            if day_num is None:
                continue
            
            # Split line into tokens or cells (tabs, pipes, multiple spaces)
            delimiters = ["\t", "|", "  "]
            cells = []
            for d in delimiters:
                if d in line:
                    cells = [c.strip() for c in line.split(d) if c.strip()]
                    break
            if not cells:
                cells = line.split()

            # Remove the weekday token from cells
            content_cells = [c for c in cells if match_weekday(c) is None]

            # Match cells to time headers
            for slot_idx, (st, et, time_str) in enumerate(time_headers):
                cell_text = content_cells[slot_idx] if slot_idx < len(content_cells) else ""
                
                # Check filter
                if clean_filter:
                    if clean_filter not in cell_text.upper():
                        continue
                elif not cell_text or any(ign in cell_text.upper() for ign in ["LUNCH", "BREAK", "TEA", "RECESS"]):
                    continue

                slots.append({
                    "weekday": WEEKDAY_NAMES[day_num],
                    "period": str(slot_idx + 1),
                    "start_time": st.strftime("%H:%M"),
                    "end_time": et.strftime("%H:%M"),
                    "effective_from": eff_from_str,
                    "effective_to": eff_to_str,
                    "raw_cell": cell_text or f"Slot {slot_idx + 1}",
                })

    # Strategy 2: Line-by-Line / Tabular extraction
    # If strategy 1 yielded no slots, inspect each line individually
    if not slots:
        for line_num, line in enumerate(lines, 1):
            day_num = match_weekday(line)
            time_ranges = extract_time_ranges_from_line(line)
            
            # Look for Period label (e.g. Period 1, P2, Slot 3)
            period_match = PERIOD_REGEX.search(line)
            period_val = period_match.group(1) if period_match else "1"

            if day_num is not None and time_ranges:
                st, et, _ = time_ranges[0]
                if clean_filter and clean_filter not in line.upper():
                    continue
                slots.append({
                    "weekday": WEEKDAY_NAMES[day_num],
                    "period": period_val,
                    "start_time": st.strftime("%H:%M"),
                    "end_time": et.strftime("%H:%M"),
                    "effective_from": eff_from_str,
                    "effective_to": eff_to_str,
                    "raw_cell": line,
                })
            elif "\t" in line or "," in line:
                # Tab or CSV formatted row: weekday, period, start, end
                parts = [p.strip() for p in (line.split("\t") if "\t" in line else line.split(",")) if p.strip()]
                if len(parts) >= 4:
                    row_day = match_weekday(parts[0])
                    if row_day is not None:
                        try:
                            # Try parsing start and end
                            st_match = extract_time_ranges_from_line(f"{parts[2]} - {parts[3]}")
                            if st_match:
                                st, et, _ = st_match[0]
                                slots.append({
                                    "weekday": WEEKDAY_NAMES[row_day],
                                    "period": parts[1],
                                    "start_time": st.strftime("%H:%M"),
                                    "end_time": et.strftime("%H:%M"),
                                    "effective_from": eff_from_str,
                                    "effective_to": eff_to_str,
                                    "raw_cell": " ".join(parts[4:]) if len(parts) > 4 else parts[1],
                                })
                        except Exception:
                            pass

    # Strategy 3: Loose block detection (Day on one line, followed by period / time blocks)
    if not slots:
        current_day: Optional[int] = None
        for line in lines:
            d = match_weekday(line)
            if d is not None and len(line.split()) <= 3:
                current_day = d
                continue
            if current_day is not None:
                tr = extract_time_ranges_from_line(line)
                if tr:
                    if clean_filter and clean_filter not in line.upper():
                        continue
                    pm = PERIOD_REGEX.search(line)
                    pval = pm.group(1) if pm else "1"
                    st, et, _ = tr[0]
                    slots.append({
                        "weekday": WEEKDAY_NAMES[current_day],
                        "period": pval,
                        "start_time": st.strftime("%H:%M"),
                        "end_time": et.strftime("%H:%M"),
                        "effective_from": eff_from_str,
                        "effective_to": eff_to_str,
                        "raw_cell": line,
                    })

    # Deduplicate slots by (weekday, period, start_time)
    seen_keys = set()
    unique_slots = []
    for s in slots:
        k = (s["weekday"], s["period"], s["start_time"])
        if k not in seen_keys:
            seen_keys.add(k)
            unique_slots.append(s)

    # Sort slots by weekday (Mon=0..Sun=6) and start_time
    day_order = {name: i for i, name in enumerate(WEEKDAY_NAMES)}
    unique_slots.sort(key=lambda s: (day_order.get(s["weekday"], 9), s["start_time"]))

    return {
        "slots": unique_slots,
        "total_extracted": len(unique_slots),
        "raw_text_length": len(raw_text),
    }
