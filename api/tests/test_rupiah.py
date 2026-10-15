import pytest

from app.tools.rupiah import parse_rupiah


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("75rb", 75_000),
        ("75 rb", 75_000),
        ("610rb", 610_000),
        ("20RB", 20_000),
        ("15k", 15_000),
        ("2jt", 2_000_000),
        ("1,2jt", 1_200_000),
        ("1.2jt", 1_200_000),
        ("1,25 jt", 1_250_000),
        ("0,5jt", 500_000),
        ("1.250rb", 1_250_000),
        ("2 juta", 2_000_000),
        ("75 ribu", 75_000),
        ("75.000", 75_000),
        ("1.500.000", 1_500_000),
        ("1,500,000", 1_500_000),
        ("Rp 1.500.000,-", 1_500_000),
        ("Rp75.000", 75_000),
        ("75.000,00", 75_000),
        ("IDR 610.000", 610_000),
        ("500", 500),
    ],
)
def test_parses_notebook_shorthand(text, expected):
    assert parse_rupiah(text) == expected


@pytest.mark.parametrize("text", [None, "", "abc", "1,2", "1.2.3jt", "jt", "12/9"])
def test_returns_none_when_not_an_amount(text):
    assert parse_rupiah(text) is None
