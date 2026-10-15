from datetime import date

import pytest

from app.tools.dates import month_of

CAPTURED = date(2026, 10, 15)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1/9", "2026-09"),
        ("12/09/26", "2026-09"),
        ("3-8-2026", "2026-08"),
        ("2026-09-14", "2026-09"),
        ("Sep - minggu 1", "2026-09"),
        ("12 Agustus 2026", "2026-08"),
        ("Okt", "2026-10"),
        ("28/12", "2025-12"),  # December, photographed in October: last year's
        ("jual sembako", None),
        ("jual martabak desa", None),
        ("", None),
        (None, None),
        ("45/13", None),
    ],
)
def test_month_of(text, expected):
    assert month_of(text, CAPTURED) == expected
