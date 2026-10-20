"""Logical printed sides, not a printer's imposed sheet/feed order.

All ranges are zero-based and end-exclusive. Unused capacity remains blank.
"""

from dataclasses import dataclass
from decimal import Decimal

from .geometry import (
    FULL_WIDTH_MM,
    HALF_WIDTH_MM,
    PAGE_HEIGHT_MM,
    SESSIONS_PER_BATCH,
    STUDENTS_PER_BLOCK,
)


@dataclass(frozen=True)
class Leaf:
    kind: str
    width_mm: Decimal
    height_mm: Decimal
    student_start: int
    student_end: int
    session_start: int | None
    session_end: int | None
    side: str


def plan_leaves(student_count: int, session_count: int) -> list[Leaf]:
    if any(type(count) is not int or count < 0 for count in (student_count, session_count)):
        raise ValueError("Student and session counts must be non-negative integers.")
    leaves = []
    for student_start in range(0, max(1, student_count), STUDENTS_PER_BLOCK):
        for batch in range(0, max(1, session_count), SESSIONS_PER_BATCH):
            for panel in range(8):
                kind = "roster" if panel == 0 else "assessment" if panel == 7 else "continuation"
                start = batch + panel * 10
                leaves.append(
                    Leaf(
                        kind,
                        HALF_WIDTH_MM if kind == "continuation" else FULL_WIDTH_MM,
                        PAGE_HEIGHT_MM,
                        student_start,
                        student_start + STUDENTS_PER_BLOCK,
                        start,
                        min(start + 10, batch + SESSIONS_PER_BATCH),
                        "full" if panel in (0, 7) else "recto" if panel % 2 else "verso",
                    )
                )
    return leaves
