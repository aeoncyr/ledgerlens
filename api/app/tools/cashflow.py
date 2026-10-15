"""Monthly cash flow from the entries the reader agents extracted.

Each entry keeps the evidence it came from, so every figure here can be traced back to a photo, a
QRIS screenshot or a moment in the interview. The three views of revenue are kept apart on purpose:

- proven inflows: money we can see arriving (QRIS, e-wallet, bank history), the hard evidence;
- claimed sales: what the owner's notebook says was sold, the soft evidence;
- supplier purchases: what receipts say was bought, which shows whether the claims are plausible.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import TIER_BY_TYPE, EvidenceTier, EvidenceType

EntryKind = Literal["sale", "purchase", "expense", "receivable", "other"]


class Entry(BaseModel):
    """One amount taken from one piece of evidence."""

    month: str = Field(pattern=r"^\d{4}-\d{2}$", description="Calendar month, e.g. 2026-09")
    kind: EntryKind
    amount_rp: int = Field(ge=0)
    evidence_type: EvidenceType
    evidence_id: str
    locator: str


class MonthFigures(BaseModel):
    month: str
    proven_inflows: int = 0
    claimed_sales: int = 0
    receipt_purchases: int = 0
    claimed_purchases: int = 0
    claimed_expenses: int = 0

    @property
    def costs(self) -> int:
        # Take the higher of the two views of purchases, so costs are never understated.
        return max(self.receipt_purchases, self.claimed_purchases) + self.claimed_expenses


class CashFlowSummary(BaseModel):
    months: list[MonthFigures]
    avg_proven_inflows: int
    avg_claimed_sales: int
    avg_costs: int
    avg_receipt_purchases: int
    revenue_low: int = Field(description="Proven inflows only")
    revenue_high: int = Field(description="The larger of claimed sales and proven inflows")
    net_high: int = Field(description="revenue_high minus costs")
    hard_coverage: float | None = Field(
        description="Share of claimed sales visible in hard evidence; None without claimed sales"
    )
    sales_to_purchases: float | None = Field(
        description="Claimed sales divided by receipt purchases; None without receipts"
    )


def _add(figures: MonthFigures, entry: Entry) -> None:
    tier = TIER_BY_TYPE[entry.evidence_type]
    if entry.kind == "sale" and tier is EvidenceTier.HARD:
        figures.proven_inflows += entry.amount_rp
    elif entry.kind == "sale" and tier is EvidenceTier.SOFT:
        figures.claimed_sales += entry.amount_rp
    elif entry.kind == "purchase" and entry.evidence_type is EvidenceType.RECEIPT:
        figures.receipt_purchases += entry.amount_rp
    elif entry.kind == "purchase":
        figures.claimed_purchases += entry.amount_rp
    elif entry.kind == "expense":
        figures.claimed_expenses += entry.amount_rp
    # Receivables (kasbon) and other lines are kept as evidence but don't move cash flow.


def summarise(entries: list[Entry]) -> CashFlowSummary:
    """Group entries by month and compute the monthly averages the policy works from."""
    by_month: dict[str, MonthFigures] = defaultdict(lambda: MonthFigures(month=""))
    for entry in entries:
        figures = by_month[entry.month]
        figures.month = entry.month
        _add(figures, entry)
    months = [by_month[key] for key in sorted(by_month)]
    if not months:
        months = [MonthFigures(month="none")]

    avg_inflows = round(mean(m.proven_inflows for m in months))
    avg_claimed = round(mean(m.claimed_sales for m in months))
    avg_costs = round(mean(m.costs for m in months))
    avg_receipts = round(mean(m.receipt_purchases for m in months))
    revenue_high = max(avg_claimed, avg_inflows)

    return CashFlowSummary(
        months=months,
        avg_proven_inflows=avg_inflows,
        avg_claimed_sales=avg_claimed,
        avg_costs=avg_costs,
        avg_receipt_purchases=avg_receipts,
        revenue_low=avg_inflows,
        revenue_high=revenue_high,
        net_high=revenue_high - avg_costs,
        hard_coverage=round(avg_inflows / avg_claimed, 3) if avg_claimed else None,
        sales_to_purchases=round(avg_claimed / avg_receipts, 3) if avg_receipts else None,
    )
