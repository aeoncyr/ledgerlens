"""The SLIK check, as the lender records it.

SLIK (Sistem Layanan Informasi Keuangan) is OJK's credit information system. Only a lender that
reports to it can query it, with the borrower's consent, and LedgerLens never does: the officer runs
the check in the lender's own system and types four figures into the file. Code then uses the
monthly instalments SLIK shows as the owner's other debt, in place of what the application
declares, and lists what the officer should weigh: a material gap between the two figures, and a
facility in arrears (collectibility 3 to 5). Neither changes how well the evidence is verified.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from app.schemas import CamelModel, Finding
from app.tools.facts import FactTable

# OJK's five grades of collectibility (kolektibilitas), from current to loss.
COLLECTIBILITY = {
    1: "current (lancar)",
    2: "special mention (dalam perhatian khusus)",
    3: "substandard (kurang lancar)",
    4: "doubtful (diragukan)",
    5: "loss (macet)",
}
# The two figures differ materially when the gap is above both of these.
MATERIAL_GAP_RP = 100_000
MATERIAL_GAP_SHARE = 0.10
MAX_AGE_DAYS = 365
DECLARED_LABEL = (
    "Other loan instalments a month, including online loans, as the application declares"
)


class SlikCheck(CamelModel):
    checked_on: date = Field(description="The day the lender ran the check")
    active_facilities: int = Field(description="Credit facilities still open")
    monthly_instalments: int = Field(description="Their instalments a month, in rupiah")
    worst_collectibility: int = Field(description="The worst grade among them, 1 (current) to 5")


def problems(check: SlikCheck, today: date) -> str | None:
    """What is wrong with a recorded check, in plain words, or None."""
    if check.checked_on > today:
        return "The date of the SLIK check can't be in the future."
    if (today - check.checked_on).days > MAX_AGE_DAYS:
        return "That SLIK check is more than a year old. Run a new one before relying on it."
    if not 0 <= check.active_facilities <= 50:
        return "The number of active facilities should be between 0 and 50."
    if not 0 <= check.monthly_instalments <= 1_000_000_000:
        return "The monthly instalments should be between Rp 0 and Rp 1.000.000.000."
    if check.active_facilities == 0 and check.monthly_instalments > 0:
        return "With no active facilities there are no instalments to pay. Check the two figures."
    if check.worst_collectibility not in COLLECTIBILITY:
        return "Collectibility is a grade from 1 (current) to 5 (loss)."
    return None


def slik_findings(check: SlikCheck, declared: int, facts: FactTable) -> list[Finding]:
    """Add the check's figures to the fact table and return what the officer should weigh."""
    facts.add(
        "slik_monthly_instalments",
        "Other loan instalments a month on the SLIK check the lender recorded",
        "rupiah",
        check.monthly_instalments,
    )
    facts.add(
        "slik_active_facilities",
        "Active credit facilities on the SLIK check",
        "count",
        check.active_facilities,
    )
    if "existing_monthly_debt" not in facts:  # files checked before the declared figure was kept
        facts.add("existing_monthly_debt", DECLARED_LABEL, "rupiah", declared)
    when = f"{check.checked_on.day} {check.checked_on:%b %Y}"
    findings: list[Finding] = []
    gap = abs(check.monthly_instalments - declared)
    if gap > max(MATERIAL_GAP_RP, MATERIAL_GAP_SHARE * max(check.monthly_instalments, declared)):
        more = check.monthly_instalments > declared
        findings.append(
            Finding(
                kind="credit_history",
                # Debts the owner didn't mention matter more than ones already paid off.
                severity="medium" if more else "low",
                source="code",
                text=facts.render(
                    f"The SLIK check recorded on {when} shows [[slik_monthly_instalments]] a "
                    f"month in other loan instalments, {'more' if more else 'less'} than the "
                    "[[existing_monthly_debt]] the application declares. The policy uses the "
                    "SLIK figure."
                ),
                figures=["slik_monthly_instalments", "existing_monthly_debt"],
            )
        )
    if check.worst_collectibility >= 3:
        grade = check.worst_collectibility
        findings.append(
            Finding(
                kind="credit_history",
                severity="high" if grade >= 4 else "medium",
                source="code",
                text=(
                    f"The SLIK check recorded on {when} shows a facility at collectibility "
                    f"{grade}, {COLLECTIBILITY[grade]}. Ask the owner about it; this is for the "
                    "officer to weigh and does not change how well the evidence is verified."
                ),
            )
        )
    return findings
