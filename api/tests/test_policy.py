from app.schemas import Assessment, Finding
from app.schemas import EvidenceType as ET
from app.tools.cashflow import Entry, summarise
from app.tools.policy import (
    LenderPolicy,
    assess,
    consistency_findings,
    evidence_strength,
    monthly_installment,
)

ALL_EVIDENCE = {ET.QRIS_HISTORY, ET.RECEIPT, ET.LEDGER_PAGE, ET.INTERVIEW_AUDIO, ET.SHOP_PHOTO}


def month(month_key, *, qris=0, claimed=0, receipts=0, claimed_purchases=0, expenses=0):
    rows = [
        ("sale", qris, ET.QRIS_HISTORY),
        ("sale", claimed, ET.LEDGER_PAGE),
        ("purchase", receipts, ET.RECEIPT),
        ("purchase", claimed_purchases, ET.LEDGER_PAGE),
        ("expense", expenses, ET.LEDGER_PAGE),
    ]
    return [
        Entry(month=month_key, kind=k, amount_rp=a, evidence_type=t, evidence_id="ev", locator="x")
        for k, a, t in rows
        if a
    ]


def grocery_stall():
    """Like Bu Sari: cash-heavy, consistent sources."""
    return summarise(
        month(
            "2026-08", qris=5_500_000, claimed=18_000_000, receipts=12_000_000, expenses=1_200_000
        )
        + month(
            "2026-09", qris=5_700_000, claimed=18_600_000, receipts=12_300_000, expenses=1_200_000
        )
    )


def test_installment_matches_a_kur_micro_loan():
    # Rp 10 million over 12 months at 0.5% a month
    assert monthly_installment(10_000_000, 12, 0.005) == 860_664
    assert monthly_installment(1_200_000, 12, 0) == 100_000


def test_consistent_business_is_verified_with_a_safe_installment():
    summary = grocery_stall()
    result = assess(
        summary=summary,
        findings=consistency_findings(summary, LenderPolicy()),
        evidence_types=ALL_EVIDENCE,
        amount=10_000_000,
        tenor_months=12,
        existing_monthly_debt=200_000,
    )

    assert result.assessment is Assessment.VERIFIED
    assert result.capacity_basis == round(summary.net_high * 0.8)
    assert result.max_installment == round(result.capacity_basis * 0.3) - 200_000
    assert result.evidence_strength == 100


def test_inflated_notebook_is_inconsistent_and_gets_no_installment():
    # Like Pak Hendra: the notebook claims far more than suppliers could have sold him.
    summary = summarise(month("2026-09", qris=14_000_000, claimed=45_000_000, receipts=9_000_000))
    findings = consistency_findings(summary, LenderPolicy())

    result = assess(
        summary=summary,
        findings=findings,
        evidence_types=ALL_EVIDENCE,
        amount=25_000_000,
        tenor_months=18,
    )

    assert findings[0].severity == "high"
    assert result.assessment is Assessment.INCONSISTENT
    assert result.max_installment is None
    assert result.within_policy is False


def test_explained_finding_no_longer_blocks():
    summary = grocery_stall()
    explained = Finding(
        kind="discrepancy",
        severity="medium",
        text="Saturday sales exceed QRIS",
        answer="Market shoppers pay cash",
        resolved=True,
    )

    result = assess(
        summary=summary,
        findings=[explained],
        evidence_types=ALL_EVIDENCE,
        amount=5_000_000,
        tenor_months=12,
    )

    assert result.assessment is Assessment.VERIFIED


def test_without_qris_the_file_is_only_partially_verified():
    # Like Pak Joko: notebook and receipts, but no hard evidence.
    summary = summarise(month("2026-09", claimed=7_000_000, receipts=4_000_000, expenses=500_000))

    result = assess(
        summary=summary,
        findings=consistency_findings(summary, LenderPolicy()),
        evidence_types={ET.LEDGER_PAGE, ET.RECEIPT, ET.INTERVIEW_AUDIO},
        amount=5_000_000,
        tenor_months=10,
    )

    assert result.assessment is Assessment.PARTIALLY_VERIFIED
    assert result.capacity_basis == round(summary.net_high * 0.6)


def test_interview_and_photo_alone_are_insufficient():
    # Like Pak Asep: there is nothing to verify cash flow against.
    result = assess(
        summary=summarise([]),
        findings=[],
        evidence_types={ET.INTERVIEW_AUDIO, ET.SHOP_PHOTO},
        amount=3_000_000,
        tenor_months=6,
    )

    assert result.assessment is Assessment.INSUFFICIENT_EVIDENCE
    assert result.max_installment is None
    assert any("normal process" in reason for reason in result.reasons)


def test_low_qris_coverage_is_flagged():
    summary = summarise(month("2026-09", qris=500_000, claimed=10_000_000, receipts=6_000_000))

    findings = consistency_findings(summary, LenderPolicy())

    assert [f.severity for f in findings] == ["medium"]


def test_evidence_strength_rewards_variety_and_history():
    assert evidence_strength({ET.INTERVIEW_AUDIO}, months_covered=1) == 10
    assert evidence_strength({ET.QRIS_HISTORY, ET.RECEIPT}, months_covered=2) == 65


def test_service_trades_get_a_higher_sales_to_purchases_limit():
    summary = summarise(month("2026-09", claimed=7_000_000, receipts=2_200_000))

    def ratio_findings(business_type):
        found = consistency_findings(summary, LenderPolicy(), business_type)
        return [f for f in found if "supplier purchases" in f.text]

    assert ratio_findings("Grocery stall")
    assert not ratio_findings("Tailor (penjahit)")
