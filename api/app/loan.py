"""Loan arithmetic for an offer: the monthly instalment and the repayment schedule, in whole rupiah.

An offer is priced as a standard annuity (the same instalment every month) at the annual rate the
officer enters. Interest each month is charged on the balance still owed; the last month absorbs
the rounding, so the principal always adds up to the amount lent. The web app shows a live
preview with the same formula, but the figures the owner and the lender see are the ones computed
here.
"""

from __future__ import annotations

import math

from pydantic import Field

from app.schemas import CamelModel


def round_rp(value: float) -> int:
    """Round half up to whole rupiah, as JavaScript's Math.round does for the web preview."""
    return math.floor(value + 0.5)


class ScheduleRow(CamelModel):
    month: int
    instalment_rp: int
    interest_rp: int
    principal_rp: int
    balance_rp: int = Field(description="Still owed after this month's payment")


class Offer(CamelModel):
    amount_rp: int
    tenor_months: int
    annual_rate_pct: float
    instalment_rp: int
    total_rp: int = Field(description="Everything the owner repays: principal plus interest")
    within_policy: bool = Field(
        description="The instalment is no larger than the largest the lender's policy allows"
    )
    max_installment_rp: int | None = Field(
        default=None, description="The policy's largest instalment for this file, if it set one"
    )
    schedule: list[ScheduleRow]


def instalment(amount_rp: int, tenor_months: int, annual_rate_pct: float) -> int:
    """The level monthly payment that repays the amount with interest over the tenor."""
    rate = annual_rate_pct / 100 / 12
    if rate == 0:
        return round_rp(amount_rp / tenor_months)
    return round_rp(amount_rp * rate / (1 - (1 + rate) ** -tenor_months))


def schedule(amount_rp: int, tenor_months: int, annual_rate_pct: float) -> list[ScheduleRow]:
    rate = annual_rate_pct / 100 / 12
    payment = instalment(amount_rp, tenor_months, annual_rate_pct)
    balance = amount_rp
    rows: list[ScheduleRow] = []
    for month in range(1, tenor_months + 1):
        interest = round_rp(balance * rate)
        principal = balance if month == tenor_months else min(balance, payment - interest)
        balance -= principal
        rows.append(
            ScheduleRow(
                month=month,
                instalment_rp=principal + interest,
                interest_rp=interest,
                principal_rp=principal,
                balance_rp=balance,
            )
        )
    return rows


def make_offer(
    amount_rp: int,
    tenor_months: int,
    annual_rate_pct: float,
    max_installment: int | None,
) -> Offer:
    rows = schedule(amount_rp, tenor_months, annual_rate_pct)
    payment = instalment(amount_rp, tenor_months, annual_rate_pct)
    return Offer(
        amount_rp=amount_rp,
        tenor_months=tenor_months,
        annual_rate_pct=annual_rate_pct,
        instalment_rp=payment,
        total_rp=sum(row.instalment_rp for row in rows),
        # With no limit from the policy (too little evidence to judge), nothing is "within" it.
        within_policy=max_installment is not None and payment <= max_installment,
        max_installment_rp=max_installment,
        schedule=rows,
    )
