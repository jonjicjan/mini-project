"""Authoritative outer sizes; interior measurements await a physical print check."""

from decimal import ROUND_HALF_UP, Decimal

FULL_WIDTH_MM = Decimal("210")
HALF_WIDTH_MM = Decimal("105")
PAGE_HEIGHT_MM = Decimal("307")
STUDENTS_PER_BLOCK = 20
SESSIONS_PER_BATCH = 75
STUDENT_ROW_MM = Decimal("8.3")
BODY_TOP_MM = Decimal("80")


def mm_to_twips(value: Decimal | int | str) -> int:
    return int((Decimal(value) * 1440 / Decimal("25.4")).quantize(1, ROUND_HALF_UP))
