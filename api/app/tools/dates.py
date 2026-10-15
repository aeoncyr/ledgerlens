"""Work out which calendar month a written date belongs to.

Notebooks rarely write the year ("1/9", "Sep - minggu 1"), so the year comes from when the evidence
was captured: a page photographed in January that says "28/12" belongs to the previous December.
Indonesian and English month names are both understood.
"""

from __future__ import annotations

import re
from datetime import date

# Month names in Indonesian and English. A written word counts if it starts one of these names and
# is at least three letters long ("Sep", "Okt"); "agt" is a common Indonesian short form.
_MONTH_NAMES = {
    1: ("januari", "january"),
    2: ("februari", "pebruari", "february"),
    3: ("maret", "march"),
    4: ("april",),
    5: ("mei", "may"),
    6: ("juni", "june"),
    7: ("juli", "july"),
    8: ("agustus", "august", "agt"),
    9: ("september",),
    10: ("oktober", "october"),
    11: ("november", "nopember"),
    12: ("desember", "december"),
}
_ISO = re.compile(r"\b(?P<year>20\d{2})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
_NUMERIC = re.compile(
    r"\b(?P<day>\d{1,2})\s*[/.-]\s*(?P<month>\d{1,2})(?:\s*[/.-]\s*(?P<year>\d{2,4}))?\b"
)
_NAMED = re.compile(r"\b(?P<name>[a-z]{3,})\.?(?:\s+(?P<year>20\d{2}|'?\d{2})\b)?")


def _month_named(word: str) -> int | None:
    for month, names in _MONTH_NAMES.items():
        if any(name.startswith(word) for name in names):
            return month
    return None


def _year(written: str | None, month: int, reference: date) -> int:
    if written:
        year = int(written.lstrip("'"))
        return year + 2000 if year < 100 else year
    # No year written: the most recent such month on or before the capture date.
    return reference.year if month <= reference.month else reference.year - 1


def month_of(text: str | None, reference: date) -> str | None:
    """Return "YYYY-MM" for a written date, or None if the text holds no recognisable date."""
    if not text:
        return None
    lowered = text.lower()
    if match := _ISO.search(lowered):
        month = int(match.group("month"))
        if 1 <= month <= 12:
            return f"{match.group('year')}-{month:02d}"
    if match := _NUMERIC.search(lowered):
        day, month = int(match.group("day")), int(match.group("month"))
        if 1 <= day <= 31 and 1 <= month <= 12:
            return f"{_year(match.group('year'), month, reference)}-{month:02d}"
    for match in _NAMED.finditer(lowered):
        month = _month_named(match.group("name"))
        if month:
            return f"{_year(match.group('year'), month, reference)}-{month:02d}"
    return None
