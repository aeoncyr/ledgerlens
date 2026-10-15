"""Lender policy: turn cash flow and findings into an outcome and a safe monthly instalment.

LedgerLens never approves or rejects; it recommends, and a credit officer decides. Every
threshold is a named parameter of ``LenderPolicy``. The defaults are starting points to agree with
a pilot lender, not industry standards.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas import TIER_BY_TYPE, Assessment, EvidenceTier, EvidenceType, Finding
from app.tools.cashflow import CashFlowSummary


class LenderPolicy(BaseModel):
    max_installment_ratio: float = Field(
        default=0.30, description="Share of net monthly cash flow that may go to repayments"
    )
    monthly_rate: float = Field(
        default=0.005, description="Monthly rate used to price the request (KUR micro: 0.5%)"
    )
    haircut_verified: float = Field(
        default=0.20, description="Discount on net cash flow when the sources agree"
    )
    haircut_partial: float = Field(
        default=0.40, description="Larger discount when there is no hard evidence"
    )
    min_hard_coverage: float = Field(
        default=0.10, description="Below this share of claimed sales, QRIS proves too little"
    )
    max_sales_to_purchases: float = Field(
        default=2.5, description="Claimed sales above this multiple of purchases are implausible"
    )
    service_max_sales_to_purchases: float = Field(
        default=4.0,
        description="The same limit for service trades (tailors, repair, laundry), whose costs "
        "are mostly labour rather than goods bought for resale",
    )


SERVICE_WORDS = ("tailor", "penjahit", "jahit", "repair", "bengkel", "laundry", "salon", "jasa")


def is_service(business_type: str) -> bool:
    return any(word in business_type.lower() for word in SERVICE_WORDS)


EVIDENCE_POINTS: dict[EvidenceType, int] = {
    EvidenceType.QRIS_HISTORY: 35,
    EvidenceType.RECEIPT: 20,
    EvidenceType.LEDGER_PAGE: 15,
    EvidenceType.INTERVIEW_AUDIO: 10,
    EvidenceType.SHOP_PHOTO: 10,
}
MULTI_MONTH_BONUS = 10


class PolicyResult(BaseModel):
    assessment: Assessment
    evidence_strength: int = Field(ge=0, le=100)
    capacity_basis: int | None = Field(description="Net monthly cash flow after the haircut")
    max_installment: int | None
    requested_installment: int
    within_policy: bool
    reasons: list[str]


def consistency_findings(
    summary: CashFlowSummary, policy: LenderPolicy, business_type: str = ""
) -> list[Finding]:
    """Checks that need only arithmetic. The verifier agent adds the ones that need judgement."""
    findings: list[Finding] = []
    ratio = summary.sales_to_purchases
    limit = (
        policy.service_max_sales_to_purchases
        if is_service(business_type)
        else policy.max_sales_to_purchases
    )
    if ratio is not None and ratio > limit:
        findings.append(
            Finding(
                kind="discrepancy",
                severity="high",
                text=(
                    f"Claimed sales are {ratio:.1f}x supplier purchases, above the "
                    f"{limit:.1f}x a business like this can plausibly sell."
                ),
            )
        )
    coverage = summary.hard_coverage
    # Without any QRIS history the pipeline reports the missing evidence instead; a "0% coverage"
    # finding would only say the same thing again.
    if (
        coverage is not None
        and summary.avg_proven_inflows > 0
        and coverage < policy.min_hard_coverage
    ):
        findings.append(
            Finding(
                kind="discrepancy",
                severity="medium",
                text=f"QRIS and e-wallet history show only {coverage:.0%} of the claimed sales.",
            )
        )
    if summary.avg_claimed_sales and summary.avg_proven_inflows > summary.avg_claimed_sales * 1.1:
        findings.append(
            Finding(
                kind="low_confidence",
                severity="low",
                text="Proven inflows exceed the notebook's sales; the notebook may be incomplete.",
            )
        )
    return findings


def monthly_installment(amount: int, months: int, monthly_rate: float) -> int:
    """Standard annuity payment, rounded to whole rupiah."""
    if monthly_rate == 0:
        return round(amount / months)
    return round(amount * monthly_rate / (1 - (1 + monthly_rate) ** -months))


def evidence_strength(evidence_types: set[EvidenceType], months_covered: int) -> int:
    score = sum(EVIDENCE_POINTS[t] for t in evidence_types)
    if months_covered >= 2:
        score += MULTI_MONTH_BONUS
    return min(score, 100)


def assess(
    *,
    summary: CashFlowSummary,
    findings: list[Finding],
    evidence_types: set[EvidenceType],
    amount: int,
    tenor_months: int,
    existing_monthly_debt: int = 0,
    policy: LenderPolicy | None = None,
) -> PolicyResult:
    policy = policy or LenderPolicy()
    tiers = {TIER_BY_TYPE[t] for t in evidence_types}
    open_issues = [f for f in findings if not f.resolved and f.severity in ("medium", "high")]
    blocking = [f for f in open_issues if f.severity == "high" or f.kind == "fraud_signal"]
    has_figures = summary.revenue_high > 0
    reasons: list[str] = []

    if blocking:
        assessment = Assessment.INCONSISTENT
        reasons.append("The sources contradict each other; a person needs to investigate.")
    elif not has_figures or not tiers & {EvidenceTier.HARD, EvidenceTier.MEDIUM}:
        assessment = Assessment.INSUFFICIENT_EVIDENCE
        reasons.append("There is not enough hard or supplier evidence to judge cash flow.")
    elif EvidenceTier.HARD in tiers and not open_issues:
        assessment = Assessment.VERIFIED
        reasons.append("Hard evidence and supplier receipts support the notebook's figures.")
    else:
        assessment = Assessment.PARTIALLY_VERIFIED
        reasons.append("Some figures are supported, but hard evidence is missing or questioned.")

    haircut = {
        Assessment.VERIFIED: policy.haircut_verified,
        Assessment.PARTIALLY_VERIFIED: policy.haircut_partial,
    }.get(assessment)
    capacity_basis = (
        max(0, round(summary.net_high * (1 - haircut))) if haircut is not None else None
    )
    max_installment = (
        max(0, round(capacity_basis * policy.max_installment_ratio) - existing_monthly_debt)
        if capacity_basis is not None
        else None
    )
    requested = monthly_installment(amount, tenor_months, policy.monthly_rate)
    within_policy = max_installment is not None and requested <= max_installment
    if max_installment is None:
        reasons.append("No instalment is suggested; the lender's normal process applies.")
    elif within_policy:
        reasons.append("The requested instalment fits within the lender's policy.")
    else:
        reasons.append("The requested instalment is above what the verified cash flow supports.")

    return PolicyResult(
        assessment=assessment,
        evidence_strength=evidence_strength(evidence_types, len(summary.months)),
        capacity_basis=capacity_basis,
        max_installment=max_installment,
        requested_installment=requested,
        within_policy=within_policy,
        reasons=reasons,
    )
