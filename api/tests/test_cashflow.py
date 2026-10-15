from app.schemas import EvidenceType as ET
from app.tools.cashflow import Entry, summarise


def entry(month, kind, amount, evidence_type, evidence_id="ev", locator="line 1"):
    return Entry(
        month=month,
        kind=kind,
        amount_rp=amount,
        evidence_type=evidence_type,
        evidence_id=evidence_id,
        locator=locator,
    )


def test_keeps_proven_claimed_and_purchase_views_apart():
    summary = summarise(
        [
            entry("2026-08", "sale", 5_000_000, ET.QRIS_HISTORY),
            entry("2026-08", "sale", 16_000_000, ET.LEDGER_PAGE),
            entry("2026-08", "purchase", 11_000_000, ET.RECEIPT),
            entry("2026-08", "purchase", 11_500_000, ET.LEDGER_PAGE),
            entry("2026-08", "expense", 1_000_000, ET.LEDGER_PAGE),
            entry("2026-08", "receivable", 20_000, ET.LEDGER_PAGE),
        ]
    )

    month = summary.months[0]
    assert month.proven_inflows == 5_000_000
    assert month.claimed_sales == 16_000_000
    assert month.costs == 12_500_000  # the higher purchase view plus expenses
    assert summary.revenue_low == 5_000_000
    assert summary.revenue_high == 16_000_000
    assert summary.net_high == 3_500_000
    assert summary.hard_coverage == 0.312
    assert summary.sales_to_purchases == 1.455


def test_averages_over_months():
    summary = summarise(
        [
            entry("2026-08", "sale", 10_000_000, ET.LEDGER_PAGE),
            entry("2026-09", "sale", 14_000_000, ET.LEDGER_PAGE),
        ]
    )

    assert [m.month for m in summary.months] == ["2026-08", "2026-09"]
    assert summary.avg_claimed_sales == 12_000_000


def test_proven_inflows_win_when_the_notebook_is_lower():
    summary = summarise(
        [
            entry("2026-09", "sale", 6_000_000, ET.QRIS_HISTORY),
            entry("2026-09", "sale", 4_000_000, ET.LEDGER_PAGE),
        ]
    )

    assert summary.revenue_high == 6_000_000


def test_no_entries_gives_zero_figures():
    summary = summarise([])

    assert summary.revenue_high == 0
    assert summary.hard_coverage is None
    assert summary.sales_to_purchases is None
