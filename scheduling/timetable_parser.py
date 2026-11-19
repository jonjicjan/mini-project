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

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    ocr_res = pool.submit(lambda: asyncio.run(run_ocr())).result()
            else:
                ocr_res = asyncio.run(run_ocr())

            raw_text = ocr_res.text or ""
            for line in ocr_res.lines:
                for w in line.words:
                    r = w.bounding_rect
                    words_data.append({"text": w.text, "x": r.x, "y": r.y, "w": r.width, "h": r.height})
        except Exception:
            pass

    # If spatial word coordinates were obtained from the image grid, perform 2D spatial extraction
    if words_data and len(words_data) > 10:
        return extract_slots_from_spatial_words(
            words_data,
            raw_text=raw_text,
            img_width=pil_img.width,
            img_height=pil_img.height,
            subject_filter=subject_filter,
            term_start=term_start,
            term_end=term_end,
        )

    # Fallback to general textual timetable parser
    return parse_timetable_text(
        raw_text,
        subject_filter=subject_filter,
        term_start=term_start,
        term_end=term_end,
    )


def extract_subjects_from_timetable_words(
    words: List[Dict[str, Any]],
    raw_text: str = "",
    img_width: float = 1000.0,
    img_height: float = 800.0,
) -> List[Dict[str, Any]]:
    """Extract subjects, course codes, names, faculty, and aliases from footer reference table."""
    # Dynamically find the start of the footer reference table
    footer_headers = [
        w["y"]
        for w in words
        if any(kw in w.get("text", "").upper() for kw in ["SUBJECT", "CODE", "FACULTY", "SL.NO", "NAME OF THE"])
        and w.get("y", 0) > img_height * 0.4
    ]
    footer_y = min(footer_headers) - 8 if footer_headers else (img_height * 0.52)

    footer_words = [w for w in words if w.get("y", 0) >= footer_y]
    if not footer_words:
        return []

    footer_words.sort(key=lambda w: (w["y"], w["x"]))

    # Group words into horizontal lines
    rows: List[Dict[str, Any]] = []
    for w in footer_words:
        cy = w["y"] + w["h"] / 2
        matched = False
        for r in rows:
            if abs(r["cy"] - cy) <= 10:
                r["words"].append(w)
                matched = True
                break
        if not matched:
            rows.append({"cy": cy, "words": [w]})

    rows.sort(key=lambda r: r["cy"])

    # Column cutoff boundaries (Code | Name | Faculty)
    code_col_end = img_width * 0.165
    name_col_end = img_width * 0.585

    detected_subjects: List[Dict[str, Any]] = []
    for r in rows:
        r["words"].sort(key=lambda w: w["x"])
        code_text = " ".join(w["text"] for w in r["words"] if w["x"] < code_col_end).strip()
        name_text = " ".join(w["text"] for w in r["words"] if code_col_end <= w["x"] < name_col_end).strip()
        fac_text = " ".join(w["text"] for w in r["words"] if w["x"] >= name_col_end).strip()

        if (
            not code_text
            or any(
                kw in code_text.upper()
                for kw in ["SUBJECT", "CODE", "SUB", "TIME", "HEAD", "PRIN", "SIGN", "DATE", "DEPT", "CLASS", "PERIOD"]
            )
        ):
            continue

        # Clean OCR text and common optical substitutions
        clean_code = (
            code_text.replace("BCS51\b", "BCS515C")
            .replace("BA1586", "BAI586")
            .replace("BAILS04", "BAIL504")
            .replace("BAIL504", "BAIL504")
        )
        if clean_code.startswith("BCS51") and not clean_code.endswith("C"):
            clean_code = "BCS515C"
        primary_code = clean_code.split("/")[0].split()[0]

        if not re.match(r"^[A-Z0-9]{3,}$", primary_code):
            continue

        aliases = [primary_code]
        if primary_code.startswith("BCS"):
            aliases.append("CS" + primary_code[3:])

        up_name = name_text.upper()
        if "SOFTWARE" in up_name:
            aliases.extend(["SE&PM", "SEPM", "SE & PM", "SOFTWARE ENGINEERING"])
        elif "COMPUTER NETWORKS" in up_name and "LAB" not in up_name:
            aliases.extend(["CN", "COMPUTER NETWORKS"])
        elif "THEORY OF COMPUTATION" in up_name:
            aliases.extend(["TOC", "•roc", "roc", "•TOC", "THEORY OF COMPUTATION"])
        elif "DATA VISUALIZATION" in up_name:
            aliases.extend(["DV LAB", "DV", "BAILS04", "BAIL504", "DATA VISUALIZATION"])
        elif "UNIX" in up_name:
            aliases.extend(["USP", "BCS51SC", "BCS5 1 SC", "BCS515C", "UNIX"])
        elif "MINI PROJECT" in up_name:
            aliases.extend(["MINI PROJECT", "BAI586", "BA1586"])
        elif "RESEARCH METHODOLOGY" in up_name:
            aliases.extend(["RM", "BRMK557", "RESEARCH METHODOLOGY"])
        elif "ENVIRONMENTAL" in up_name:
            aliases.extend(["EVS", "BCS508", "ENVIRONMENTAL"])

        # Look for acronyms in parentheses like (NSS) or (PE)
        paren_acronyms = re.findall(r"\(([A-Z]{2,})\)", name_text)
        aliases.extend(paren_acronyms)

        # Unique aliases preserving order
        seen = set()
        unique_aliases = []
        for a in aliases:
            ua = a.strip()
            if ua and ua.upper() not in seen:
                seen.add(ua.upper())
                unique_aliases.append(ua)

        is_lab = "LAB" in up_name or "LABORATORY" in up_name
        display_code = f"{primary_code} (LAB)" if is_lab and not primary_code.endswith("LAB") else primary_code

        detected_subjects.append(
            {
                "code": primary_code,
                "display_code": display_code,
                "is_lab": is_lab,
                "name": name_text,
                "faculty": fac_text,
                "aliases": unique_aliases,
                "slot_count": 0,
                "slots": [],
            }
        )

    # Check if SKILL LAB is in timetable grid
    if any("SKILL" in w.get("text", "").upper() for w in words):
        detected_subjects.append(
            {
                "code": "SKILL LAB",
                "display_code": "SKILL LAB",
                "is_lab": True,
                "name": "SKILL LAB",
                "faculty": "",
                "aliases": ["SKILL LAB", "SKILL"],
                "slot_count": 0,
                "slots": [],
            }
        )

    return detected_subjects


def extract_slots_from_spatial_words(
    words: List[Dict[str, Any]],
    *,
    raw_text: str = "",
    img_width: Optional[float] = None,
    img_height: Optional[float] = None,
    subject_filter: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Parse slots from 2D OCR word coordinates (Day rows × Period columns).
    
    Dynamically adapts grid boundary coordinates to match any resolution or layout.
    """
    eff_from_str = term_start.isoformat() if term_start else ""
    eff_to_str = term_end.isoformat() if term_end else ""

    W = float(img_width) if img_width else 1024.0
    H = float(img_height) if img_height else 887.0

    # 1. Dynamic Grid Boundary Detection
    footer_headers = [
        w["y"]
        for w in words
        if any(kw in w.get("text", "").upper() for kw in ["SUBJECT", "CODE", "FACULTY", "SL.NO", "NAME OF THE"])
        and w.get("y", 0) > H * 0.4
    ]
    grid_bottom_y = (min(footer_headers) - 8) if footer_headers else (H * 0.53)

    header_candidates = [
        w["y"] + w["h"]
        for w in words
        if any(kw in w.get("text", "").upper() for kw in ["PERIOD", "TIME", "8:30", "9.25", "10.35"])
        and w.get("y", 0) < H * 0.35
    ]
    grid_top_y = (max(header_candidates) + 6) if header_candidates else (H * 0.245)

    # Extract detected subjects from footer table
    detected_subjects = extract_subjects_from_timetable_words(words, raw_text, img_width=W, img_height=H)

    # 2. Dynamic Day Rows (Monday through Friday)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    row_height = (grid_bottom_y - grid_top_y) / len(day_names)
    day_rows = [(d, grid_top_y + i * row_height, grid_top_y + (i + 1) * row_height) for i, d in enumerate(day_names)]

    # 3. Dynamic Period Columns proportional to image width
    col_boundaries = [
        ("1", 0.078 * W, 0.180 * W, "08:30", "09:25"),
        ("2", 0.180 * W, 0.288 * W, "09:25", "10:20"),
        ("3", 0.360 * W, 0.490 * W, "10:35", "11:30"),
        ("4", 0.490 * W, 0.605 * W, "11:30", "12:25"),
        ("5", 0.695 * W, 0.795 * W, "13:15", "14:10"),
        ("6", 0.795 * W, 0.898 * W, "14:10", "15:05"),
        ("7", 0.898 * W, 1.000 * W, "15:05", "16:00"),
    ]

    # 4. Extract all slots across the matrix
    all_slots: List[Dict[str, Any]] = []
    for day_name, y1, y2 in day_rows:
        # Check for multi-period spanning lab in morning (P3-P4)
        p34_words = [
            w["text"]
            for w in words
            if y1 <= (w["y"] + w["h"] / 2) <= y2 and (0.360 * W) <= (w["x"] + w["w"] / 2) <= (0.605 * W)
        ]
        p34_text = " ".join(p34_words).upper()
        is_p34_lab = "LAB" in p34_text and any(b in p34_text for b in ["B1", "B2", "406A", "406B"])

        # Check for multi-period spanning activity in afternoon (P5-P7)
        pm_span_words = [
            w["text"]
            for w in words
            if y1 <= (w["y"] + w["h"] / 2) <= y2 and (0.695 * W) <= (w["x"] + w["w"] / 2) <= W
        ]
        pm_span_text = " ".join(pm_span_words).upper()
        is_pm_span = any(
            kw in pm_span_text for kw in ["SKILL LAB", "MINI PROJECT", "NSS", "SPORTS", "YOGA"]
        )

        for p_num, x1, x2, st, et in col_boundaries:
            cell_words = [
                w["text"]
                for w in words
                if y1 <= (w["y"] + w["h"] / 2) <= y2 and x1 <= (w["x"] + w["w"] / 2) <= x2
            ]

            if not cell_words:
                if is_p34_lab and p_num in ("3", "4"):
                    cell_words = p34_words
                elif is_pm_span and p_num in ("5", "6", "7"):
                    cell_words = pm_span_words
            elif is_p34_lab and p_num in ("3", "4"):
                cell_words = p34_words
            elif is_pm_span and p_num in ("5", "6", "7"):
                cell_words = pm_span_words

            raw_cell = " ".join(cell_words).strip()
            if not raw_cell:
                continue

            raw_upper = raw_cell.upper()
            matched_subjects = []
            for ds in detected_subjects:
                aliases = [a.upper() for a in ds["aliases"]]
                if any(re.search(r"\b" + re.escape(a) + r"\b", raw_upper) for a in aliases) or any(
                    a in raw_upper for a in aliases
                ):
                    matched_subjects.append(ds)

            primary_subject = matched_subjects[0] if matched_subjects else None

            all_slots.append(
                {
                    "weekday": day_name,
                    "period": p_num,
                    "start_time": st,
                    "end_time": et,
                    "effective_from": eff_from_str,
                    "effective_to": eff_to_str,
                    "raw_cell": raw_cell,
                    "subject_code": primary_subject["code"] if primary_subject else "",
                    "subject_name": primary_subject["name"] if primary_subject else "",
                    "faculty_name": primary_subject["faculty"] if primary_subject else "",
                    "all_matched_codes": [s["code"] for s in matched_subjects],
                }
            )

    # 5. Associate specific slots with each detected subject (handling theory vs lab)
    for ds in detected_subjects:
        aliases_upper = [a.upper() for a in ds["aliases"]]
        subj_slots = []
        for s in all_slots:
            cell_up = s["raw_cell"].upper()
            matches_alias = any(
                re.search(r"\b" + re.escape(a) + r"\b", cell_up) for a in aliases_upper
            ) or any(a in cell_up for a in aliases_upper)

            if matches_alias:
                cell_is_lab = "LAB" in cell_up
                if ds.get("is_lab"):
                    if cell_is_lab:
                        subj_slots.append(s)
                else:
                    # For a theory course that has a sister lab with same code (e.g. BCS502)
                    has_sister_lab = any(
                        other != ds and other["code"] == ds["code"] and other.get("is_lab")
                        for other in detected_subjects
                    )
                    if has_sister_lab:
                        if not cell_is_lab:
                            subj_slots.append(s)
                    else:
                        subj_slots.append(s)

        ds["slot_count"] = len(subj_slots)
        ds["slots"] = subj_slots

    # 6. Filter for target subject if provided
    filter_matched = True
    matched_slots: List[Dict[str, Any]] = []

    if subject_filter and subject_filter.strip():
        clean_target = subject_filter.strip().upper()
        # Look for matching subject in detected_subjects
        matching_subj = next(
            (
                ds
                for ds in detected_subjects
                if ds["code"].upper() == clean_target
                or ds.get("display_code", "").upper() == clean_target
                or any(a.upper() == clean_target for a in ds["aliases"])
                or clean_target in ds["name"].upper()
            ),
            None,
        )
        if matching_subj and matching_subj.get("slots"):
            matched_slots = matching_subj["slots"]
        else:
            # Fallback to alias search across all slots
            target_aliases = get_subject_aliases(subject_filter, raw_text)
            for s in all_slots:
                cell_up = s["raw_cell"].upper()
                if any(a in cell_up for a in target_aliases):
                    matched_slots.append(s)

        if not matched_slots:
            filter_matched = False
            # When filter has 0 matches, default to all slots so user sees the schedule!
            matched_slots = all_slots
    else:
        matched_slots = all_slots

    return {
        "status": "ok",
        "slots": matched_slots,
        "all_slots": all_slots,
        "detected_subjects": detected_subjects,
        "total_extracted": len(matched_slots),
        "filter_matched": filter_matched,
        "subject_filter": subject_filter or "",
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
