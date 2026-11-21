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

COURSE_CODE_REGEX = re.compile(
    r"\b([A-Z]{2,5}\d{2,4}[A-Z]?|\d{2}[A-Z]{2,5}\d{2,4}[A-Z]?)\b",
    re.IGNORECASE,
)

ACRONYM_REGEX = re.compile(
    r"\b([A-Z]{2,6}(?:&[A-Z]{2,6})?)\b"
)

IGNORE_CELL_WORDS = {
    "MON", "MONDAY", "TUE", "TUESDAY", "WED", "WEDNESDAY", "THU", "THUR", "THURSDAY", "FRI", "FRIDAY",
    "SAT", "SATURDAY", "SUN", "SUNDAY", "PERIOD", "TIME", "DAY", "HOUR", "SLOT", "AM", "PM", "ROOM",
    "CLASS", "SEC", "SECTION", "DEPT", "BREAK", "TEA", "LUNCH", "RECESS", "FREE", "W.E.F", "WEF",
    "HEAD", "HOD", "PRIN", "PRINCIPAL", "SIGN", "SIGNATURE", "SUBJECT", "CODE", "FACULTY", "NAME",
    "SL.NO", "NO", "TOTAL", "KSIT", "OB", "CR", "LH", "BATCH", "B1", "B2", "B3", "406A", "406B"
}


def clean_ocr_typos(text: str) -> str:
    """Normalize common OCR misrecognitions and substitutions in timetable text."""
    if not text:
        return ""
    res = text
    # TOC misreads
    res = re.sub(r"[•·*]\s*(?:roc|TOC|roc)\b", "TOC", res, flags=re.IGNORECASE)
    res = re.sub(r"\b•roc\b", "TOC", res, flags=re.IGNORECASE)
    # BCS51SC / BCS5 1 SC -> BCS515C
    res = re.sub(r"\bBCS51S([A-Z])\b", r"BCS515\1", res, flags=re.IGNORECASE)
    res = re.sub(r"\bBCS51\s+([A-Z0-9])\s*([A-Z])\b", r"BCS515\2", res, flags=re.IGNORECASE)
    # BA1586 -> BAI586
    res = re.sub(r"\bBA1(\d{3})\b", r"BAI\1", res, flags=re.IGNORECASE)
    # BAILS04 -> BAIL504
    res = re.sub(r"\bBAILS(\d{2})\b", r"BAIL5\1", res, flags=re.IGNORECASE)
    return res


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


def extract_images_from_pdf(file_bytes_or_stream) -> List[Any]:
    """Extract embedded images from PDF pages for scanned timetables."""
    if PdfReader is None or Image is None:
        return []
    if isinstance(file_bytes_or_stream, bytes):
        stream = io.BytesIO(file_bytes_or_stream)
    else:
        stream = file_bytes_or_stream
    try:
        reader = PdfReader(stream)
        images = []
        for page in reader.pages:
            for img_file in page.images:
                try:
                    pil_img = Image.open(io.BytesIO(img_file.data))
                    if pil_img.width >= 300 and pil_img.height >= 300:
                        images.append(pil_img)
                except Exception:
                    continue
        return images
    except Exception:
        return []



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
    # Support formats: "08:30-09:25", "9.25 AM to 10.20 AM", "1:15-2:10", "14:00 - 15:00"
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
    register_subject: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Extract and parse timetable slots directly from an uploaded image using native OCR."""
    return parse_timetable_file(
        file_bytes_or_stream,
        filename="timetable.png",
        subject_filter=subject_filter,
        register_subject=register_subject,
        term_start=term_start,
        term_end=term_end,
    )


def step_1_upload_and_extract(
    file_bytes_or_stream,
    filename: str = "",
) -> Dict[str, Any]:
    """Stage 1: Ingest image or PDF file stream and determine extraction path."""
    is_pdf = filename.lower().endswith(".pdf")
    if not is_pdf and hasattr(file_bytes_or_stream, "name"):
        is_pdf = file_bytes_or_stream.name.lower().endswith(".pdf")

    if is_pdf and PdfReader is not None:
        raw_text = extract_text_from_pdf(file_bytes_or_stream)
        if len(raw_text.strip()) >= 50:
            return {"kind": "text", "raw_text": raw_text, "source": "pdf_text"}
        # Fallback to embedded image if PDF is a scanned document
        pdf_images = extract_images_from_pdf(file_bytes_or_stream)
        if pdf_images:
            return {"kind": "image", "image": pdf_images[0], "source": "pdf_scan"}
        return {"kind": "text", "raw_text": raw_text, "source": "pdf_text"}

    if Image is not None:
        try:
            if isinstance(file_bytes_or_stream, bytes):
                img = Image.open(io.BytesIO(file_bytes_or_stream))
            else:
                img = Image.open(file_bytes_or_stream)
            return {"kind": "image", "image": img, "source": "image_upload"}
        except Exception:
            pass

    # Fallback to text decoding
    if isinstance(file_bytes_or_stream, bytes):
        text = file_bytes_or_stream.decode("utf-8", errors="ignore")
    elif hasattr(file_bytes_or_stream, "read"):
        text = file_bytes_or_stream.read().decode("utf-8", errors="ignore")
    else:
        text = str(file_bytes_or_stream)
    return {"kind": "text", "raw_text": text, "source": "text_upload"}


def step_2_preprocess_image(pil_img: Any) -> Any:
    """Stage 2: Image preprocessing for high-accuracy OCR and cell grid detection.

    Enhancements:
    - Auto-orient using EXIF orientation tags.
    - Low-resolution upscaling (if width < 700px).
    - Preserves color chroma channels for Windows Media OCR neural network.
    - Contrast and sharpness enhancement.
    - Return RGBA format for native OCR engine.
    """
    if Image is None or pil_img is None:
        return pil_img

    img = pil_img.convert("RGBA")
    try:
        from PIL import ImageOps, ImageEnhance

        img = ImageOps.exif_transpose(img)
        if img.width < 700:
            scale = 1000.0 / float(max(img.width, 1))
            new_w = 1000
            new_h = int(img.height * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        img_rgb = img.convert("RGB")
        enh = ImageEnhance.Contrast(img_rgb).enhance(1.05)
        enh = ImageEnhance.Sharpness(enh).enhance(1.1)
        return enh.convert("RGBA")
    except Exception:
        return img


def step_3_detect_table_and_cells(
    words: List[Dict[str, Any]],
    img_width: float,
    img_height: float,
) -> Dict[str, Any]:
    """Stage 3: Table and cell detection.

    Identifies:
    - Table bounding box [grid_top_y, grid_bottom_y].
    - Orientation (DAYS_IN_ROWS standard vs DAYS_IN_COLUMNS inverted).
    - Active weekdays (5-day week vs 6-day week with Saturday).
    - Grid cell matrix: bounding boxes for each (day, period) coordinate.
    - Footer reference table area.
    """
    W = float(img_width)
    H = float(img_height)

    orientation, day_names = detect_layout_orientation_and_days(words, W, H)

    footer_headers = [
        w["y"]
        for w in words
        if any(kw in w.get("text", "").upper() for kw in ["SUBJECT", "CODE", "FACULTY", "SL.NO", "NAME OF THE", "STAFF"])
        and w.get("y", 0) > H * 0.4
    ]
    grid_bottom_y = (min(footer_headers) - 8) if footer_headers else (H * 0.53)

    header_candidates = [
        w["y"] + w["h"]
        for w in words
        if any(kw in w.get("text", "").upper() for kw in ["PERIOD", "TIME", "8:30", "9.25", "10.35", "DAY"])
        and w.get("y", 0) < H * 0.35
    ]
    grid_top_y = (max(header_candidates) + 6) if header_candidates else (H * 0.245)

    cells = []
    if orientation == "DAYS_IN_ROWS":
        num_days = len(day_names)
        row_h = (grid_bottom_y - grid_top_y) / max(num_days, 1)
        day_rows = [(d, grid_top_y + i * row_h, grid_top_y + (i + 1) * row_h) for i, d in enumerate(day_names)]

        is_ksit = any("KSIT" in w.get("text", "").upper() or "OB-403" in w.get("text", "").upper() for w in words)
        has_830 = any("8:30" in w.get("text", "") or "08:30" in w.get("text", "") for w in words)

        if is_ksit or has_830:
            col_bounds = [
                ("1", 0.078 * W, 0.180 * W, "08:30", "09:25"),
                ("2", 0.180 * W, 0.288 * W, "09:25", "10:20"),
                ("3", 0.360 * W, 0.490 * W, "10:35", "11:30"),
                ("4", 0.490 * W, 0.605 * W, "11:30", "12:25"),
                ("5", 0.695 * W, 0.795 * W, "13:15", "14:10"),
                ("6", 0.795 * W, 0.898 * W, "14:10", "15:05"),
                ("7", 0.898 * W, 1.000 * W, "15:05", "16:00"),
            ]
        else:
            col_bounds = [
                ("1", 0.12 * W, 0.26 * W, "09:00", "10:00"),
                ("2", 0.26 * W, 0.40 * W, "10:00", "11:00"),
                ("3", 0.40 * W, 0.55 * W, "11:15", "12:15"),
                ("4", 0.55 * W, 0.70 * W, "13:15", "14:15"),
                ("5", 0.70 * W, 0.85 * W, "14:15", "15:15"),
                ("6", 0.85 * W, 1.00 * W, "15:15", "16:15"),
            ]

        for day_name, y1, y2 in day_rows:
            for p_num, x1, x2, st, et in col_bounds:
                cells.append({
                    "day": day_name,
                    "period": p_num,
                    "bbox": (x1, y1, x2, y2),
                    "start_time": st,
                    "end_time": et,
                })
    else:
        num_days = len(day_names)
        col_w = (W * 0.85) / max(num_days, 1)
        day_cols = [(d, 0.15 * W + i * col_w, 0.15 * W + (i + 1) * col_w) for i, d in enumerate(day_names)]
        row_bounds = [
            ("1", grid_top_y + 0 * 50, grid_top_y + 1 * 50, "09:00", "10:00"),
            ("2", grid_top_y + 1 * 50, grid_top_y + 2 * 50, "10:00", "11:00"),
            ("3", grid_top_y + 2 * 50, grid_top_y + 3 * 50, "11:15", "12:15"),
            ("4", grid_top_y + 3 * 50, grid_top_y + 4 * 50, "13:15", "14:15"),
            ("5", grid_top_y + 4 * 50, grid_top_y + 5 * 50, "14:15", "15:15"),
            ("6", grid_top_y + 5 * 50, grid_top_y + 6 * 50, "15:15", "16:15"),
        ]
        for p_num, y1, y2, st, et in row_bounds:
            for day_name, x1, x2 in day_cols:
                cells.append({
                    "day": day_name,
                    "period": p_num,
                    "bbox": (x1, y1, x2, y2),
                    "start_time": st,
                    "end_time": et,
                })

    return {
        "orientation": orientation,
        "day_names": day_names,
        "grid_top_y": grid_top_y,
        "grid_bottom_y": grid_bottom_y,
        "footer_y": grid_bottom_y + 8,
        "cells": cells,
        "W": W,
        "H": H,
    }


def step_4_ocr_text_extraction(
    preprocessed_img: Any,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Stage 4: OCR text extraction with spatial bounding boxes and typo normalization."""
    raw_text = ""
    words_data: List[Dict[str, Any]] = []

    if winocr is not None and preprocessed_img is not None:
        try:
            import asyncio
            from winrt.windows.media.ocr import OcrEngine
            from winrt.windows.globalization import Language
            from winrt.windows.storage.streams import DataWriter
            from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat

            writer = DataWriter()
            writer.write_bytes(preprocessed_img.tobytes())
            sb = SoftwareBitmap.create_copy_from_buffer(
                writer.detach_buffer(), BitmapPixelFormat.RGBA8, preprocessed_img.width, preprocessed_img.height
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
                    clean_w = clean_ocr_typos(w.text)
                    words_data.append({
                        "text": clean_w,
                        "raw_text": w.text,
                        "x": r.x,
                        "y": r.y,
                        "w": r.width,
                        "h": r.height,
                    })
        except Exception:
            pass

    return raw_text, words_data


def step_5_map_subjects_and_names(
    words: List[Dict[str, Any]],
    raw_text: str,
    img_width: float,
    img_height: float,
    all_raw_cells: List[str],
) -> List[Dict[str, Any]]:
    """Stage 5: Subject code, title, faculty, lab vs theory, and acronym mapping."""
    detected = extract_subjects_from_timetable_words(words, raw_text, img_width=img_width, img_height=img_height)

    # In-cell discovery for subjects not present in the footer table
    for cell_text in all_raw_cells:
        codes = COURSE_CODE_REGEX.findall(cell_text)
        for code in codes:
            ucode = code.upper()
            if ucode not in IGNORE_CELL_WORDS and not any(ds["code"].upper() == ucode for ds in detected):
                is_lab = "LAB" in cell_text.upper()
                detected.append({
                    "code": ucode,
                    "display_code": f"{ucode} (LAB)" if is_lab and not ucode.endswith("LAB") else ucode,
                    "is_lab": is_lab,
                    "name": ucode,
                    "faculty": "",
                    "aliases": [ucode],
                    "slot_count": 0,
                    "slots": [],
                })
        if not codes:
            lab_match = re.search(r"\b([A-Z0-9\s&]+LAB(?:ORATORY)?)\b", cell_text, flags=re.IGNORECASE)
            if lab_match:
                lname = lab_match.group(1).strip().upper()
                if lname not in IGNORE_CELL_WORDS and not any(ds["code"].upper() == lname for ds in detected):
                    detected.append({
                        "code": lname,
                        "display_code": lname,
                        "is_lab": True,
                        "name": lname,
                        "faculty": "",
                        "aliases": [lname],
                        "slot_count": 0,
                        "slots": [],
                    })
            else:
                acronyms = ACRONYM_REGEX.findall(cell_text)
                for a in acronyms:
                    ua = a.strip().upper()
                    if ua not in IGNORE_CELL_WORDS and len(ua) >= 2 and not ua.isdigit():
                        if not any(ds["code"].upper() == ua or ua in [al.upper() for al in ds["aliases"]] for ds in detected):
                            detected.append({
                                "code": ua,
                                "display_code": ua,
                                "is_lab": False,
                                "name": ua,
                                "faculty": "",
                                "aliases": [ua],
                                "slot_count": 0,
                                "slots": [],
                            })
    return detected


def step_6_map_days_and_periods(
    cell_matrix: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    detected_subjects: List[Dict[str, Any]],
    W: float,
    H: float,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Stage 6: Map segmented cells to weekdays, periods, time windows, and multi-period spans."""
    eff_from_str = term_start.isoformat() if term_start else ""
    eff_to_str = term_end.isoformat() if term_end else ""
    all_slots = []

    for cell in cell_matrix:
        x1, y1, x2, y2 = cell["bbox"]
        c_words = [
            w["text"]
            for w in words
            if y1 <= (w["y"] + w["h"] / 2) <= y2 and x1 <= (w["x"] + w["w"] / 2) <= x2
        ]
        day_name = cell["day"]
        p_num = cell["period"]

        if not c_words:
            p34_words = [
                w["text"] for w in words
                if y1 <= (w["y"] + w["h"] / 2) <= y2 and (0.360 * W) <= (w["x"] + w["w"] / 2) <= (0.605 * W)
            ]
            p34_text = " ".join(p34_words).upper()
            if "LAB" in p34_text and p_num in ("3", "4"):
                c_words = p34_words
            else:
                pm_words = [
                    w["text"] for w in words
                    if y1 <= (w["y"] + w["h"] / 2) <= y2 and (0.695 * W) <= (w["x"] + w["w"] / 2) <= W
                ]
                pm_text = " ".join(pm_words).upper()
                if any(kw in pm_text for kw in ["SKILL LAB", "MINI PROJECT", "NSS", "SPORTS", "YOGA"]) and p_num in ("5", "6", "7"):
                    c_words = pm_words
        elif p_num in ("3", "4"):
            p34_words = [
                w["text"] for w in words
                if y1 <= (w["y"] + w["h"] / 2) <= y2 and (0.360 * W) <= (w["x"] + w["w"] / 2) <= (0.605 * W)
            ]
            if "LAB" in " ".join(p34_words).upper():
                c_words = p34_words

        raw_cell = clean_ocr_typos(" ".join(c_words).strip())
        if not raw_cell or any(ign in raw_cell.upper() for ign in ["LUNCH", "TEA BREAK", "RECESS"]):
            continue

        all_slots.append({
            "weekday": day_name,
            "period": p_num,
            "start_time": cell["start_time"],
            "end_time": cell["end_time"],
            "effective_from": eff_from_str,
            "effective_to": eff_to_str,
            "raw_cell": raw_cell,
            "subject_code": "",
            "subject_name": "",
            "faculty_name": "",
            "all_matched_codes": [],
        })

    for s in all_slots:
        raw_upper = s["raw_cell"].upper()
        matched = []
        for ds in detected_subjects:
            aliases = [a.upper() for a in ds["aliases"]]
            if any(re.search(r"\b" + re.escape(a) + r"\b", raw_upper) for a in aliases) or any(
                a in raw_upper for a in aliases
            ):
                matched.append(ds)
        primary = matched[0] if matched else None
        s["subject_code"] = primary["code"] if primary else ""
        s["subject_name"] = primary["name"] if primary else ""
        s["faculty_name"] = primary["faculty"] if primary else ""
        s["all_matched_codes"] = [m["code"] for m in matched]

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

    return all_slots, detected_subjects


def step_7_generate_timetable_and_review(
    all_slots: List[Dict[str, Any]],
    detected_subjects: List[Dict[str, Any]],
    *,
    subject_filter: Optional[str] = None,
    register_subject: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
    metadata: Optional[Dict[str, Any]] = None,
    raw_text: str = "",
) -> Dict[str, Any]:
    """Stage 7: Package final timetable and compile 'needs_information' review items."""
    filter_matched = True
    matched_slots: List[Dict[str, Any]] = []
    effective_target = (subject_filter or register_subject or "").strip().upper()

    if effective_target:
        matching_subj = next(
            (
                ds
                for ds in detected_subjects
                if ds["code"].upper() == effective_target
                or ds.get("display_code", "").upper() == effective_target
                or any(a.upper() == effective_target for a in ds["aliases"])
                or effective_target in ds["name"].upper()
            ),
            None,
        )
        if matching_subj and matching_subj.get("slots"):
            matched_slots = matching_subj["slots"]
        else:
            target_aliases = get_subject_aliases(effective_target, raw_text)
            for s in all_slots:
                cell_up = s["raw_cell"].upper()
                if any(a in cell_up for a in target_aliases):
                    matched_slots.append(s)
        if not matched_slots:
            filter_matched = False
            matched_slots = all_slots
    else:
        matched_slots = all_slots

    needs_info: List[Dict[str, Any]] = []

    # 1. Subject Mismatch / Selection question
    if effective_target and not filter_matched and detected_subjects:
        valid_options = [ds["display_code"] for ds in detected_subjects if ds.get("slot_count", 0) > 0]
        if not valid_options:
            valid_options = [ds["display_code"] for ds in detected_subjects]
        needs_info.append({
            "type": "subject_selection",
            "title": "Select Course Subject",
            "message": f"Register course code '{effective_target}' was not found in the timetable. Please select which detected subject belongs to this register.",
            "options": valid_options[:8],
            "default": valid_options[0] if valid_options else "",
        })

    # 2. Missing Term Dates question
    if not term_start or not term_end:
        needs_info.append({
            "type": "missing_term_dates",
            "title": "Set Academic Semester Dates",
            "message": "Academic term dates are not configured on this register. Please verify effective start and end dates for class slots.",
            "action": "set_dates",
        })

    # 3. Timing Confirmation question
    if metadata and metadata.get("uses_fallback_timings"):
        needs_info.append({
            "type": "timing_confirmation",
            "title": "Confirm Period Timings",
            "message": "Clock timings were not explicitly specified in the timetable headers. Standard default hours (08:30–16:00) were assigned.",
            "options": ["Confirm standard timings", "Edit slot timings"],
            "default": "Confirm standard timings",
        })

    # 4. Unknown or Unconfirmed Subjects (e.g. acronym without full name)
    for ds in detected_subjects:
        if ds.get("slot_count", 0) > 0 and not ds.get("faculty") and ds["name"] == ds["code"]:
            needs_info.append({
                "type": "unconfirmed_subject",
                "title": f"Course Details for {ds['code']}",
                "message": f"Subject code '{ds['code']}' has {ds['slot_count']} slots, but full title or instructor was not listed.",
                "subject_code": ds["code"],
            })
            break

    return {
        "status": "ok",
        "slots": matched_slots,
        "all_slots": all_slots,
        "detected_subjects": detected_subjects,
        "needs_information": needs_info,
        "metadata": metadata or {},
        "total_extracted": len(matched_slots),
        "filter_matched": filter_matched,
        "subject_filter": subject_filter or "",
        "register_subject": register_subject or "",
        "raw_text": raw_text,
    }


def parse_timetable_file(
    file_bytes_or_stream,
    filename: str = "",
    *,
    subject_filter: Optional[str] = None,
    register_subject: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Execute the complete 7-stage timetable recognition pipeline across any format."""
    # Stage 1: Ingest upload
    ingest = step_1_upload_and_extract(file_bytes_or_stream, filename=filename)

    if ingest["kind"] == "image":
        # Stage 2: Preprocess image
        preprocessed = step_2_preprocess_image(ingest["image"])
        # Stage 4: OCR extraction
        raw_text, words = step_4_ocr_text_extraction(preprocessed)
        if words and len(words) > 10:
            # Stages 3, 5, 6, 7: Spatial grid extraction and synthesis
            return extract_slots_from_spatial_words(
                words,
                raw_text=raw_text,
                img_width=preprocessed.width,
                img_height=preprocessed.height,
                subject_filter=subject_filter,
                register_subject=register_subject,
                term_start=term_start,
                term_end=term_end,
            )
        # Fallback to textual parse if OCR words were few
        return parse_timetable_text(
            raw_text,
            subject_filter=subject_filter,
            register_subject=register_subject,
            term_start=term_start,
            term_end=term_end,
        )

    # Ingest was text or digital PDF text
    return parse_timetable_text(
        ingest.get("raw_text", ""),
        subject_filter=subject_filter,
        register_subject=register_subject,
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
        if any(kw in w.get("text", "").upper() for kw in ["SUBJECT", "CODE", "FACULTY", "SL.NO", "NAME OF THE", "STAFF"])
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
        clean_code = clean_ocr_typos(code_text)
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


def detect_layout_orientation_and_days(
    words: List[Dict[str, Any]], W: float, H: float
) -> Tuple[str, List[str]]:
    """Detect whether days are in rows (standard) or in columns (inverted), and whether Saturday is included."""
    detected_days = []
    has_saturday = False

    for w in words:
        clean = re.sub(r"[^A-Z]", "", w.get("text", "").upper())
        if clean in ("SAT", "SATURDAY"):
            has_saturday = True
        for day_num, pattern in WEEKDAY_PATTERNS.items():
            if pattern.search(w.get("text", "")):
                detected_days.append(
                    {
                        "day": WEEKDAY_NAMES[day_num],
                        "cx": w["x"] + w["w"] / 2,
                        "cy": w["y"] + w["h"] / 2,
                    }
                )
                break

    # Determine working days list
    base_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if has_saturday:
        base_days.append("Saturday")

    # If weekdays are spread horizontally across the top (X span > 0.35 * W, Y < 0.35 * H)
    top_days = [d for d in detected_days if d["cy"] < H * 0.35]
    if len(top_days) >= 3:
        xs = [d["cx"] for d in top_days]
        if (max(xs) - min(xs)) > 0.35 * W:
            return "DAYS_IN_COLUMNS", base_days

    return "DAYS_IN_ROWS", base_days


def extract_slots_from_spatial_words(
    words: List[Dict[str, Any]],
    *,
    raw_text: str = "",
    img_width: Optional[float] = None,
    img_height: Optional[float] = None,
    subject_filter: Optional[str] = None,
    register_subject: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Parse slots from 2D OCR word coordinates across any timetable format, orientation, or resolution."""
    eff_from_str = term_start.isoformat() if term_start else ""
    eff_to_str = term_end.isoformat() if term_end else ""

    W = float(img_width) if img_width else 1024.0
    H = float(img_height) if img_height else 887.0

    # 1. Orientation & Days Detection
    orientation, day_names = detect_layout_orientation_and_days(words, W, H)

    # 2. Grid Boundary Detection
    footer_headers = [
        w["y"]
        for w in words
        if any(kw in w.get("text", "").upper() for kw in ["SUBJECT", "CODE", "FACULTY", "SL.NO", "NAME OF THE", "STAFF"])
        and w.get("y", 0) > H * 0.4
    ]
    grid_bottom_y = (min(footer_headers) - 8) if footer_headers else (H * 0.53)

    header_candidates = [
        w["y"] + w["h"]
        for w in words
        if any(kw in w.get("text", "").upper() for kw in ["PERIOD", "TIME", "8:30", "9.25", "10.35", "DAY"])
        and w.get("y", 0) < H * 0.35
    ]
    grid_top_y = (max(header_candidates) + 6) if header_candidates else (H * 0.245)

    # Extract detected subjects from reference table (if present)
    detected_subjects = extract_subjects_from_timetable_words(words, raw_text, img_width=W, img_height=H)

    all_slots: List[Dict[str, Any]] = []

    if orientation == "DAYS_IN_ROWS":
        # Standard Layout: Rows = Weekdays, Columns = Periods
        num_days = len(day_names)
        row_height = (grid_bottom_y - grid_top_y) / max(num_days, 1)
        day_rows = [(d, grid_top_y + i * row_height, grid_top_y + (i + 1) * row_height) for i, d in enumerate(day_names)]

        # Determine period columns
        is_ksit = any("KSIT" in w.get("text", "").upper() or "OB-403" in w.get("text", "").upper() for w in words)
        if is_ksit or any("8:30" in w.get("text", "") for w in words):
            col_boundaries = [
                ("1", 0.078 * W, 0.180 * W, "08:30", "09:25"),
                ("2", 0.180 * W, 0.288 * W, "09:25", "10:20"),
                ("3", 0.360 * W, 0.490 * W, "10:35", "11:30"),
                ("4", 0.490 * W, 0.605 * W, "11:30", "12:25"),
                ("5", 0.695 * W, 0.795 * W, "13:15", "14:10"),
                ("6", 0.795 * W, 0.898 * W, "14:10", "15:05"),
                ("7", 0.898 * W, 1.000 * W, "15:05", "16:00"),
            ]
        else:
            # Universal column proportional subdivision (standard 6-period default)
            col_boundaries = [
                ("1", 0.12 * W, 0.26 * W, "09:00", "10:00"),
                ("2", 0.26 * W, 0.40 * W, "10:00", "11:00"),
                ("3", 0.40 * W, 0.55 * W, "11:15", "12:15"),
                ("4", 0.55 * W, 0.70 * W, "13:15", "14:15"),
                ("5", 0.70 * W, 0.85 * W, "14:15", "15:15"),
                ("6", 0.85 * W, 1.00 * W, "15:15", "16:15"),
            ]

        for day_name, y1, y2 in day_rows:
            # Check multi-period spans
            p34_words = [
                w["text"]
                for w in words
                if y1 <= (w["y"] + w["h"] / 2) <= y2 and (0.360 * W) <= (w["x"] + w["w"] / 2) <= (0.605 * W)
            ]
            p34_text = " ".join(p34_words).upper()
            is_p34_lab = "LAB" in p34_text and any(b in p34_text for b in ["B1", "B2", "406A", "406B"])

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

                raw_cell = clean_ocr_typos(" ".join(cell_words).strip())
                if not raw_cell:
                    continue

                all_slots.append(
                    {
                        "weekday": day_name,
                        "period": p_num,
                        "start_time": st,
                        "end_time": et,
                        "effective_from": eff_from_str,
                        "effective_to": eff_to_str,
                        "raw_cell": raw_cell,
                        "subject_code": "",
                        "subject_name": "",
                        "faculty_name": "",
                        "all_matched_codes": [],
                    }
                )
    else:
        # Inverted Layout: Columns = Weekdays, Rows = Periods
        num_days = len(day_names)
        col_w = (W * 0.85) / max(num_days, 1)
        day_cols = [(d, 0.15 * W + i * col_w, 0.15 * W + (i + 1) * col_w) for i, d in enumerate(day_names)]

        # Row periods (typically 4 to 8 periods down the Y-axis)
        period_rows = [
            ("1", grid_top_y + 0 * 50, grid_top_y + 1 * 50, "09:00", "10:00"),
            ("2", grid_top_y + 1 * 50, grid_top_y + 2 * 50, "10:00", "11:00"),
            ("3", grid_top_y + 2 * 50, grid_top_y + 3 * 50, "11:15", "12:15"),
            ("4", grid_top_y + 3 * 50, grid_top_y + 4 * 50, "13:15", "14:15"),
            ("5", grid_top_y + 4 * 50, grid_top_y + 5 * 50, "14:15", "15:15"),
            ("6", grid_top_y + 5 * 50, grid_top_y + 6 * 50, "15:15", "16:15"),
        ]

        for p_num, y1, y2, st, et in period_rows:
            for day_name, x1, x2 in day_cols:
                cell_words = [
                    w["text"]
                    for w in words
                    if y1 <= (w["y"] + w["h"] / 2) <= y2 and x1 <= (w["x"] + w["w"] / 2) <= x2
                ]
                raw_cell = clean_ocr_typos(" ".join(cell_words).strip())
                if not raw_cell:
                    continue

                all_slots.append(
                    {
                        "weekday": day_name,
                        "period": p_num,
                        "start_time": st,
                        "end_time": et,
                        "effective_from": eff_from_str,
                        "effective_to": eff_to_str,
                        "raw_cell": raw_cell,
                        "subject_code": "",
                        "subject_name": "",
                        "faculty_name": "",
                        "all_matched_codes": [],
                    }
                )

    # 3. Universal In-Cell Subject Discovery
    # If timetable has no footer table or omitted some subjects, discover them from cells!
    for s in all_slots:
        raw_cell = s.get("raw_cell", "")
        # Look for course codes
        codes = COURSE_CODE_REGEX.findall(raw_cell)
        for code in codes:
            ucode = code.upper()
            if ucode not in IGNORE_CELL_WORDS and not any(ds["code"].upper() == ucode for ds in detected_subjects):
                is_lab = "LAB" in raw_cell.upper()
                disp = f"{ucode} (LAB)" if is_lab and not ucode.endswith("LAB") else ucode
                detected_subjects.append(
                    {
                        "code": ucode,
                        "display_code": disp,
                        "is_lab": is_lab,
                        "name": ucode,
                        "faculty": "",
                        "aliases": [ucode],
                        "slot_count": 0,
                        "slots": [],
                    }
                )

        # If no standard course code found in cell, check uppercase subject acronym or lab
        if not codes:
            lab_match = re.search(r"\b([A-Z0-9\s&]+LAB(?:ORATORY)?)\b", raw_cell, flags=re.IGNORECASE)
            if lab_match:
                lname = lab_match.group(1).strip().upper()
                if lname not in IGNORE_CELL_WORDS and not any(ds["code"].upper() == lname for ds in detected_subjects):
                    detected_subjects.append(
                        {
                            "code": lname,
                            "display_code": lname,
                            "is_lab": True,
                            "name": lname,
                            "faculty": "",
                            "aliases": [lname],
                            "slot_count": 0,
                            "slots": [],
                        }
                    )
            else:
                acronyms = ACRONYM_REGEX.findall(raw_cell)
                for a in acronyms:
                    ua = a.strip().upper()
                    if ua not in IGNORE_CELL_WORDS and len(ua) >= 2 and not ua.isdigit():
                        if not any(ds["code"].upper() == ua or ua in [al.upper() for al in ds["aliases"]] for ds in detected_subjects):
                            detected_subjects.append(
                                {
                                    "code": ua,
                                    "display_code": ua,
                                    "is_lab": False,
                                    "name": ua,
                                    "faculty": "",
                                    "aliases": [ua],
                                    "slot_count": 0,
                                    "slots": [],
                                }
                            )

    # 4. Tag every slot with matched subjects
    for s in all_slots:
        raw_upper = s["raw_cell"].upper()
        matched = []
        for ds in detected_subjects:
            aliases = [a.upper() for a in ds["aliases"]]
            if any(re.search(r"\b" + re.escape(a) + r"\b", raw_upper) for a in aliases) or any(
                a in raw_upper for a in aliases
            ):
                matched.append(ds)

        primary = matched[0] if matched else None
        s["subject_code"] = primary["code"] if primary else ""
        s["subject_name"] = primary["name"] if primary else ""
        s["faculty_name"] = primary["faculty"] if primary else ""
        s["all_matched_codes"] = [m["code"] for m in matched]

    # 5. Populate specific slots for each detected subject
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

    # 6. Apply subject filter
    filter_matched = True
    matched_slots: List[Dict[str, Any]] = []

    if subject_filter and subject_filter.strip():
        clean_target = subject_filter.strip().upper()
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
            target_aliases = get_subject_aliases(subject_filter, raw_text)
            for s in all_slots:
                cell_up = s["raw_cell"].upper()
                if any(a in cell_up for a in target_aliases):
                    matched_slots.append(s)

        if not matched_slots:
            filter_matched = False
            matched_slots = all_slots
    else:
        matched_slots = all_slots

    needs_info: List[Dict[str, Any]] = []
    effective_target = (subject_filter or register_subject or "").strip().upper()

    # 1. Subject Mismatch / Selection question
    if effective_target and not filter_matched and detected_subjects:
        valid_options = [ds["display_code"] for ds in detected_subjects if ds.get("slot_count", 0) > 0]
        if not valid_options:
            valid_options = [ds["display_code"] for ds in detected_subjects]
        needs_info.append({
            "type": "subject_selection",
            "title": "Select Course Subject",
            "message": f"Register course code '{effective_target}' was not found in the timetable. Please select which detected subject belongs to this register.",
            "options": valid_options[:8],
            "default": valid_options[0] if valid_options else "",
        })

    # 2. Missing Term Dates question
    if not term_start or not term_end:
        needs_info.append({
            "type": "missing_term_dates",
            "title": "Set Academic Semester Dates",
            "message": "Academic term dates are not configured on this register. Please verify effective start and end dates for class slots.",
            "action": "set_dates",
        })

    return {
        "status": "ok",
        "slots": matched_slots,
        "all_slots": all_slots,
        "detected_subjects": detected_subjects,
        "needs_information": needs_info,
        "total_extracted": len(matched_slots),
        "filter_matched": filter_matched,
        "subject_filter": subject_filter or "",
        "register_subject": register_subject or "",
        "raw_text": raw_text,
    }


def parse_timetable_text(
    raw_text: str,
    *,
    subject_filter: Optional[str] = None,
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
) -> Dict[str, Any]:
    """Parse raw OCR or PDF timetable text into structured timetable slots across any layout."""
    lines = [clean_ocr_typos(line.strip()) for line in raw_text.splitlines() if line.strip()]
    slots: List[Dict[str, Any]] = []

    clean_filter = subject_filter.strip().upper() if subject_filter and subject_filter.strip() else None
    aliases = get_subject_aliases(subject_filter, raw_text) if subject_filter else []
    eff_from_str = term_start.isoformat() if term_start else ""
    eff_to_str = term_end.isoformat() if term_end else ""

    # Strategy 1A: Times in Header, Days in Rows (Standard Grid)
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

    # Strategy 1B: Days in Header, Times/Periods in Rows (Inverted Grid)
    if not slots:
        day_headers: List[Tuple[int, str]] = []
        header_row_idx = -1
        for idx, line in enumerate(lines[:6]):
            tokens = [t.strip() for t in (line.split("\t") if "\t" in line else line.split("|") if "|" in line else line.split()) if t.strip()]
            detected_day_cols = []
            for c_idx, token in enumerate(tokens):
                d_num = match_weekday(token)
                if d_num is not None:
                    detected_day_cols.append((c_idx, WEEKDAY_NAMES[d_num]))
            if len(detected_day_cols) >= 3:
                header_row_idx = idx
                day_headers = detected_day_cols
                break

        if day_headers:
            period_counter = 1
            for idx in range(header_row_idx + 1, len(lines)):
                line = lines[idx]
                tokens = [t.strip() for t in (line.split("\t") if "\t" in line else line.split("|") if "|" in line else line.split()) if t.strip()]
                time_ranges = extract_time_ranges_from_line(line)
                st = time_ranges[0][0].strftime("%H:%M") if time_ranges else f"{8 + period_counter:02d}:00"
                et = time_ranges[0][1].strftime("%H:%M") if time_ranges else f"{9 + period_counter:02d}:00"

                p_match = PERIOD_REGEX.search(line)
                p_val = p_match.group(1) if p_match else str(period_counter)

                for col_idx, d_name in day_headers:
                    if col_idx < len(tokens):
                        cell_val = tokens[col_idx]
                        if cell_val and match_weekday(cell_val) is None and not any(ign in cell_val.upper() for ign in ["LUNCH", "BREAK", "TEA", "RECESS", "FREE"]):
                            if clean_filter and not any(a in cell_val.upper() for a in aliases):
                                continue
                            slots.append(
                                {
                                    "weekday": d_name,
                                    "period": p_val,
                                    "start_time": st,
                                    "end_time": et,
                                    "effective_from": eff_from_str,
                                    "effective_to": eff_to_str,
                                    "raw_cell": cell_val,
                                }
                            )
                period_counter += 1

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

    # Synthesize detected subjects from parsed slots
    detected_subjects: List[Dict[str, Any]] = []
    found_codes = set()
    for s in unique_slots:
        cell_text = s.get("raw_cell", "")
        codes = COURSE_CODE_REGEX.findall(cell_text)
        for code in codes:
            ucode = code.upper()
            if ucode not in IGNORE_CELL_WORDS and ucode not in found_codes:
                found_codes.add(ucode)
                is_lab = "LAB" in cell_text.upper()
                detected_subjects.append(
                    {
                        "code": ucode,
                        "display_code": f"{ucode} (LAB)" if is_lab and not ucode.endswith("LAB") else ucode,
                        "is_lab": is_lab,
                        "name": ucode,
                        "faculty": "",
                        "aliases": [ucode],
                        "slot_count": 0,
                        "slots": [],
                    }
                )

    for ds in detected_subjects:
        ds_slots = [s for s in unique_slots if ds["code"].upper() in s["raw_cell"].upper()]
        ds["slot_count"] = len(ds_slots)
        ds["slots"] = ds_slots

    return {
        "status": "ok",
        "slots": unique_slots,
        "all_slots": unique_slots,
        "detected_subjects": detected_subjects,
        "needs_information": [],
        "total_extracted": len(unique_slots),
        "raw_text": raw_text,
    }
