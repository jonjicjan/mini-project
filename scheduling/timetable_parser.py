"""Intelligent parser for timetable text extracted from images (OCR) and PDF files.

Extracts weekly recurring timetable slots, period numbers, time windows, and weekdays
from common college timetable layouts (grid matrices, tabular text, and list routines),
including VTU/engineering master timetable sheets.
"""

from datetime import date, time
import io
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import winocr
except ImportError:
    winocr = None

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

# Standard KSIT / Engineering College Period Timing Template
STANDARD_PERIOD_TIMINGS = {
    "1": ("08:30", "09:25"),
    "2": ("09:25", "10:20"),
    "3": ("10:35", "11:30"),
    "4": ("11:30", "12:25"),
    "5": ("13:15", "14:10"),
    "6": ("14:10", "15:05"),
    "7": ("15:05", "16:00"),
}

# Known college subject codes and common acronyms / aliases
COMMON_SUBJECT_ALIASES: Dict[str, List[str]] = {
    "BCS501": ["BCS501", "SE&PM", "SE & PM", "SOFTWARE ENGINEERING"],
    "BCS502": ["BCS502", "CN", "COMPUTER NETWORKS"],
    "BCS503": ["BCS503", "TOC", "THEORY OF COMPUTATION", "•ROC", "•TOC"],
    "BAIL504": ["BAIL504", "BAILS04", "DV LAB", "DATA VISUALIZATION"],
    "BCS515C": ["BCS515C", "BCS51SC", "BCS515", "USP", "UNIX SYSTEM"],
    "BRMK557": ["BRMK557", "RM", "RESEARCH METHODOLOGY"],
    "BCS508": ["BCS508", "EVS", "ENVIRONMENTAL STUDIES"],
    "BAI586": ["BAI586", "BA1586", "MINI PROJECT"],
}


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
        if 1 <= hour <= 6:
            hour += 12
    return time(hour, minute)


def extract_time_ranges_from_line(line: str) -> List[Tuple[time, time, str]]:
    """Find all time ranges in a single line or header."""
    matches = []
    for m in TIME_RANGE_REGEX.finditer(line):
        h1, m1, ap1, h2, m2, ap2 = m.groups()
        if ap2 and not ap1:
            ap1 = ap2
        t1 = normalize_time(int(h1), int(m1), ap1)
        t2 = normalize_time(int(h2), int(m2), ap2)
        if t2 <= t1:
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


def get_subject_aliases(target_code: Optional[str], raw_text: str = "") -> List[str]:
    """Get all alias variations and acronyms for a subject code."""
    if not target_code or not str(target_code).strip():
        return []
    target_clean = str(target_code).strip().upper()
    clean = target_clean.replace("-", "").replace(" ", "")
    aliases = {clean, target_clean}

    # Check known subject codes in pre-defined mapping
    if clean in COMMON_SUBJECT_ALIASES:
        aliases.update(COMMON_SUBJECT_ALIASES[clean])

    # Check if target_code itself matches an acronym in COMMON_SUBJECT_ALIASES
    for code, mapped_list in COMMON_SUBJECT_ALIASES.items():
        if any(clean == a.upper().replace("-", "").replace(" ", "") for a in mapped_list):
            aliases.add(code)
            aliases.update(mapped_list)

    # If code has year prefix like "21CS51" -> also match "CS51"
    prefix_match = re.match(r"^\d{2}([A-Z]+\d+[A-Z]*)$", clean)
    if prefix_match:
        aliases.add(prefix_match.group(1))

    return [a for a in aliases if len(a) >= 2]


def parse_timetable_from_image(
    file_bytes_or_stream,
    *,
    subject_filter: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Extract and parse timetable slots directly from an uploaded image using native OCR."""
    if Image is None:
        raise ValueError("Pillow is required for image processing.")

    if isinstance(file_bytes_or_stream, bytes):
        pil_img = Image.open(io.BytesIO(file_bytes_or_stream)).convert("RGBA")
    else:
        pil_img = Image.open(file_bytes_or_stream).convert("RGBA")

    raw_text = ""
    words_data = []

    # Attempt native Windows OCR with spatial word coordinates
    if winocr is not None:
        try:
            import asyncio
            from winrt.windows.media.ocr import OcrEngine
            from winrt.windows.globalization import Language
            from winrt.windows.storage.streams import DataWriter
            from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat

            writer = DataWriter()
            writer.write_bytes(pil_img.tobytes())
            sb = SoftwareBitmap.create_copy_from_buffer(
                writer.detach_buffer(), BitmapPixelFormat.RGBA8, pil_img.width, pil_img.height
            )
            engine = OcrEngine.try_create_from_language(Language("en"))

            async def run_ocr():
                return await engine.recognize_async(sb)

            ocr_res = asyncio.run(run_ocr())
            raw_text = ocr_res.text or ""
            for line in ocr_res.lines:
                for w in line.words:
                    r = w.bounding_rect
                    words_data.append({"text": w.text, "x": r.x, "y": r.y, "w": r.width, "h": r.height})
        except Exception:
            pass

    # If spatial word coordinates were obtained from the image grid, perform 2D spatial extraction
    if words_data and len(words_data) > 20:
        spatial_result = extract_slots_from_spatial_words(
            words_data,
            raw_text=raw_text,
            subject_filter=subject_filter,
            term_start=term_start,
            term_end=term_end,
        )
        if spatial_result["slots"]:
            return spatial_result

    # Fallback to general textual timetable parser
    return parse_timetable_text(
        raw_text,
        subject_filter=subject_filter,
        term_start=term_start,
        term_end=term_end,
    )


def extract_slots_from_spatial_words(
    words: List[Dict[str, Any]],
    *,
    raw_text: str = "",
    subject_filter: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Parse slots from 2D OCR word coordinates (Day rows × Period columns)."""
    eff_from_str = term_start.isoformat() if term_start else ""
    eff_to_str = term_end.isoformat() if term_end else ""

    # 1. Locate Period column X positions
    p_headers: Dict[str, float] = {}
    for w in words:
        if w["y"] < 250 and w["text"] in ["1", "2", "3", "4", "5", "6", "7"]:
            p_headers[w["text"]] = w["x"] + w["w"] / 2

    # Standard default X centers if any header missing
    default_x = {"1": 130, "2": 240, "3": 446, "4": 559, "5": 764, "6": 872, "7": 978}
    for p in ["1", "2", "3", "4", "5", "6", "7"]:
        if p not in p_headers:
            p_headers[p] = default_x[p]

    period_cols = []
    p_keys = sorted(p_headers.keys(), key=lambda k: int(k))
    for i, p in enumerate(p_keys):
        center = p_headers[p]
        left = center - 55 if i == 0 else (p_headers[p_keys[i - 1]] + center) / 2
        right = center + 55 if i == len(p_keys) - 1 else (center + p_headers[p_keys[i + 1]]) / 2
        period_cols.append((p, left, right))

    # 2. Locate Day row Y positions
    day_y: Dict[str, float] = {}
    for w in words:
        t = w["text"].upper()
        if w["x"] < 100:  # Left margin
            if "MON" in t and "Monday" not in day_y:
                day_y["Monday"] = w["y"] + w["h"] / 2
            elif ("TUE" in t or "TUES" in t) and "Tuesday" not in day_y:
                day_y["Tuesday"] = w["y"] + w["h"] / 2
            elif "WED" in t and "Wednesday" not in day_y:
                day_y["Wednesday"] = w["y"] + w["h"] / 2
            elif ("THU" in t or "THUR" in t) and "Thursday" not in day_y:
                day_y["Thursday"] = w["y"] + w["h"] / 2
            elif "FRI" in t and "Friday" not in day_y:
                day_y["Friday"] = w["y"] + w["h"] / 2

    # Standard vertical centers if OCR grouped words
    default_y = {"Monday": 251, "Tuesday": 305, "Wednesday": 355, "Thursday": 405, "Friday": 450}
    for d, dy in default_y.items():
        if d not in day_y:
            day_y[d] = dy

    day_rows = []
    d_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for i, d in enumerate(d_names):
        cy = day_y[d]
        top = cy - 25 if i == 0 else (day_y[d_names[i - 1]] + cy) / 2
        bottom = cy + 25 if i == len(d_names) - 1 else (cy + day_y[d_names[i + 1]]) / 2
        day_rows.append((d, top, bottom))

    # 3. Match cells to subject filter
    target_aliases = get_subject_aliases(subject_filter, raw_text) if subject_filter else []
    clean_target = subject_filter.strip().upper() if subject_filter else ""

    matched_slots = []
    for day_name, y_min, y_max in day_rows:
        for p_num, x_min, x_max in period_cols:
            cell_words = [
                w["text"]
                for w in words
                if x_min <= (w["x"] + w["w"] / 2) < x_max and y_min <= (w["y"] + w["h"] / 2) < y_max
            ]
            cell_text = " ".join(cell_words).upper().replace("(", " ").replace(")", " ")
            if not cell_text.strip():
                continue

            is_match = False
            if clean_target:
                if any(re.search(r"\b" + re.escape(a) + r"\b", cell_text) for a in target_aliases):
                    is_match = True
                elif any(a in cell_text for a in target_aliases):
                    is_match = True
            else:
                # If no filter specified, include any class cell (skip breaks/free)
                if not any(ign in cell_text for ign in ["TEA BREAK", "LUNCH BREAK", "FREE"]):
                    is_match = True

            if is_match:
                st, et = STANDARD_PERIOD_TIMINGS.get(p_num, ("09:00", "10:00"))
                matched_slots.append(
                    {
                        "weekday": day_name,
                        "period": p_num,
                        "start_time": st,
                        "end_time": et,
                        "effective_from": eff_from_str,
                        "effective_to": eff_to_str,
                        "raw_cell": " ".join(cell_words),
                    }
                )

    return {
        "slots": matched_slots,
        "total_extracted": len(matched_slots),
        "raw_text": raw_text,
    }


def parse_timetable_text(
    raw_text: str,
    *,
    subject_filter: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Parse raw OCR or PDF timetable text into structured timetable slots."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    slots: List[Dict[str, Any]] = []

    clean_filter = subject_filter.strip().upper() if subject_filter and subject_filter.strip() else None
    aliases = get_subject_aliases(subject_filter, raw_text) if subject_filter else []
    eff_from_str = term_start.isoformat() if term_start else ""
    eff_to_str = term_end.isoformat() if term_end else ""

    # Strategy 1: Grid Header Detection (Times/Periods in header, Days in rows)
    time_headers: List[Tuple[time, time, str]] = []
    header_line_idx = -1
    for idx, line in enumerate(lines[:10]):
        extracted = extract_time_ranges_from_line(line)
        if len(extracted) >= 2:
            time_headers = extracted
            header_line_idx = idx
            break

    if time_headers:
        for idx in range(header_line_idx + 1, len(lines)):
            line = lines[idx]
            day_num = match_weekday(line)
            if day_num is None:
                continue

            delimiters = ["\t", "|", "  "]
            cells = []
            for d in delimiters:
                if d in line:
                    cells = [c.strip() for c in line.split(d) if c.strip()]
                    break
            if not cells:
                cells = line.split()

            content_cells = [c for c in cells if match_weekday(c) is None]

            for slot_idx, (st, et, time_str) in enumerate(time_headers):
                cell_text = content_cells[slot_idx] if slot_idx < len(content_cells) else ""
                if clean_filter:
                    if not any(a in cell_text.upper() for a in aliases):
                        continue
                elif not cell_text or any(
                    ign in cell_text.upper() for ign in ["LUNCH", "BREAK", "TEA", "RECESS"]
                ):
                    continue

                slots.append(
                    {
                        "weekday": WEEKDAY_NAMES[day_num],
                        "period": str(slot_idx + 1),
                        "start_time": st.strftime("%H:%M"),
                        "end_time": et.strftime("%H:%M"),
                        "effective_from": eff_from_str,
                        "effective_to": eff_to_str,
                        "raw_cell": cell_text or f"Slot {slot_idx + 1}",
                    }
                )

    # Strategy 2: Line-by-Line / Tabular extraction
    if not slots:
        for line_num, line in enumerate(lines, 1):
            day_num = match_weekday(line)
            time_ranges = extract_time_ranges_from_line(line)
            period_match = PERIOD_REGEX.search(line)
            period_val = period_match.group(1) if period_match else "1"

            if day_num is not None and time_ranges:
                st, et, _ = time_ranges[0]
                if clean_filter and not any(a in line.upper() for a in aliases):
                    continue
                slots.append(
                    {
                        "weekday": WEEKDAY_NAMES[day_num],
                        "period": period_val,
                        "start_time": st.strftime("%H:%M"),
                        "end_time": et.strftime("%H:%M"),
                        "effective_from": eff_from_str,
                        "effective_to": eff_to_str,
                        "raw_cell": line,
                    }
                )
            elif "\t" in line or "," in line:
                parts = [
                    p.strip()
                    for p in (line.split("\t") if "\t" in line else line.split(","))
                    if p.strip()
                ]
                if len(parts) >= 4:
                    row_day = match_weekday(parts[0])
                    if row_day is not None:
                        try:
                            st_match = extract_time_ranges_from_line(f"{parts[2]} - {parts[3]}")
                            if st_match:
                                st, et, _ = st_match[0]
                                slots.append(
                                    {
                                        "weekday": WEEKDAY_NAMES[row_day],
                                        "period": parts[1],
                                        "start_time": st.strftime("%H:%M"),
                                        "end_time": et.strftime("%H:%M"),
                                        "effective_from": eff_from_str,
                                        "effective_to": eff_to_str,
                                        "raw_cell": " ".join(parts[4:]) if len(parts) > 4 else parts[1],
                                    }
                                )
                        except Exception:
                            pass

    # Deduplicate slots by (weekday, period, start_time)
    seen_keys = set()
    unique_slots = []
    for s in slots:
        k = (s["weekday"], s["period"], s["start_time"])
        if k not in seen_keys:
            seen_keys.add(k)
            unique_slots.append(s)

    day_order = {name: i for i, name in enumerate(WEEKDAY_NAMES)}
    unique_slots.sort(key=lambda s: (day_order.get(s["weekday"], 9), s["start_time"]))

    return {
        "slots": unique_slots,
        "total_extracted": len(unique_slots),
        "raw_text": raw_text,
    }
