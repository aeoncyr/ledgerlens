"""Parse rupiah amounts the way Indonesian micro businesses write them in notebooks.

Examples: "75rb" (75 thousand), "1,2jt" (1.2 million), "Rp 1.500.000,-", "15k", "610.000".
The model copies the amount exactly as written; this module turns it into an integer, so the
conversion is deterministic and testable.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_MULTIPLIERS = {
    "juta": 1_000_000,
    "jt": 1_000_000,
    "ribu": 1_000,
    "rb": 1_000,
    "k": 1_000,
}
_SUFFIX = re.compile(r"^(?P<number>[\d.,]+)(?P<unit>juta|jt|ribu|rb|k)?$")
_GROUPED = re.compile(r"^\d{1,3}([.,]\d{3})+$")
_GROUPED_WITH_CENTS = re.compile(r"^(?P<whole>\d{1,3}([.,]\d{3})+)[.,]\d{2}$")


def _clean(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"^(rp\.?|idr)", "", cleaned)
    # A space before a group of three digits is a thousands separator: "3 300 000", "3.250 000".
    cleaned = re.sub(r"(?<=\d) +(?=\d{3}(?!\d))", ".", cleaned)
    cleaned = cleaned.replace(" ", "")
    return re.sub(r"[,.]?-+$", "", cleaned)  # "1.500.000,-" -> "1.500.000"


def _to_decimal(number: str, has_unit: bool) -> Decimal | None:
    separators = re.findall(r"[.,]", number)
    if not separators:
        return Decimal(number)
    if has_unit and len(separators) == 1:
        whole, fraction = re.split(r"[.,]", number)
        if 1 <= len(fraction) <= 2:  # "1,2jt" or "1.25jt" is a decimal
            return Decimal(f"{whole}.{fraction}")
    if _GROUPED.match(number):  # "1.500.000" or "1,500,000"
        return Decimal(re.sub(r"[.,]", "", number))
    cents = _GROUPED_WITH_CENTS.match(number)
    if cents and not has_unit:  # "75.000,00" -> drop the cents
        return Decimal(re.sub(r"[.,]", "", cents.group("whole")))
    return None


def parse_rupiah(text: str | None) -> int | None:
    """Return the amount in whole rupiah, or None when the text isn't a recognisable amount."""
    if not text:
        return None
    match = _SUFFIX.match(_clean(text))
    if not match:
        return None
    unit = match.group("unit")
    try:
        value = _to_decimal(match.group("number"), has_unit=unit is not None)
    except InvalidOperation:
        return None
    if value is None:
        return None
    value *= _MULTIPLIERS.get(unit, 1)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
