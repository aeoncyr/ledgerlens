import pytest

from app.tools.facts import FactTable, amount_phrases, stray_amounts, stray_numbers


def table() -> FactTable:
    facts = FactTable()
    facts.add("revenue_low", "Proven monthly inflows", "rupiah", 8_450_000, ["ev-qris"])
    facts.add("hard_coverage", "Share of claimed sales seen in QRIS", "percent", 0.72)
    facts.add("sales_to_purchases", "Claimed sales over purchases", "ratio", 3.04)
    facts.add("missing", "Not computed", "rupiah", None)
    return facts


def test_renders_figures_in_their_own_format():
    text = table().render(
        "QRIS proves [[revenue_low]] a month, [[hard_coverage]] of claimed sales; "
        "sales are [[sales_to_purchases]] purchases."
    )

    assert text == (
        "QRIS proves Rp 8.450.000 a month, 72% of claimed sales; sales are 3.0× purchases."
    )


def test_skips_figures_that_were_not_computed_and_reports_unknown_keys():
    facts = table()

    assert "missing" not in facts
    assert facts.unknown_keys("[[revenue_low]] and [[revenue_high]]") == ["revenue_high"]
    assert facts.render("[[revenue_high]]") == "[unknown figure]"


@pytest.mark.parametrize(
    "text",
    [
        "Sales of [[revenue_low]] on page 2, line 4, dated 12/9, across two receipts in 2026.",
        "The 5C memo covers 3 months.",
    ],
)
def test_allows_counts_dates_and_years(text):
    assert stray_numbers(text) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sales are about Rp 1.200.000 a day.", ["1.200.000"]),
        ("The notebook says 610rb.", ["610"]),
        ("Only 12% is visible in QRIS.", ["12"]),
        ("Sales are 3 x purchases.", ["3"]),
        ("Revenue of 2,5 juta.", ["2,5"]),
        ("A total of 450000 was claimed.", ["450000"]),
    ],
)
def test_catches_numbers_the_model_wrote_itself(text, expected):
    assert stray_numbers(text) == expected


WRITTEN = amount_phrases(
    ["1,5 jt", "600rb", "Rp 585.000", "Claimed sales are 5.6x purchases; QRIS 13%."]
)


@pytest.mark.parametrize(
    "text",
    [
        "The notebook writes 1,5jt on line 2.",
        "Line 4 says 1,5 juta.",
        "A sale of Rp 585.000 on line 3.",
        "Sales are 5.6× purchases and QRIS covers 13%.",
    ],
)
def test_amounts_quoted_as_written_are_allowed(text):
    assert stray_amounts(text, WRITTEN) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Daily sales of Rp 500.000 to Rp 600.", ["500.000", "600"]),  # 600rb is written, not 600
        ("About 1.500.000 a day.", ["1.500.000"]),  # written as 1,5 jt, so it must be a [[key]]
    ],
)
def test_amounts_not_written_that_way_are_caught(text, expected):
    assert stray_amounts(text, WRITTEN) == expected
