"""Apply a lender's policy again to a file that was already checked: Python only, no Gemini.

Lenders differ in how much of a business's cash flow they let go to repayments, how hard they
discount it and what their product costs, and a SLIK check can change the other debts the policy
subtracts. None of that needs the evidence read or cross-checked again, so this recomputes the
policy section of the stored credit file from its stored cash flow and findings, with the same
``assess`` the pipeline uses. The outcome itself can't change: it rests on the evidence, and SLIK
findings never count towards it.

Gemini wrote the memo around the old figures, but every figure in it was filled in by code from a
``[[key]]``, and the memo lists the keys it used, so the new values go where the old ones were.
When the change goes beyond the figures (the request moves inside or outside the policy, or a
figure can't be placed with certainty), the file says the memo's wording is older than the policy,
and a re-check rewrites it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.analysis.pipeline import Application, Context, add_policy_facts
from app.schemas import Finding
from app.tools.camel import camelize
from app.tools.cashflow import CashFlowSummary
from app.tools.facts import Fact, FactTable
from app.tools.policy import LenderPolicy, assess, monthly_installment
from app.tools.slik import SlikCheck, slik_findings

# Keys that hold identifiers or lists of keys, never prose.
NOT_PROSE = {"evidenceId", "locator", "figures", "checkId", "timeText"}
SLIK_FACTS = ("slik_monthly_instalments", "slik_active_facilities")


def _snake(value: Any) -> Any:
    if isinstance(value, dict):
        return {re.sub(r"([A-Z])", r"_\1", k).lower(): _snake(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_snake(v) for v in value]
    return value


def _replace(text: str, swaps: dict[str, str]) -> str:
    if not swaps:
        return text
    # One pass over every old value at once, so a new value is never replaced again.
    pattern = "|".join(re.escape(old) for old in sorted(swaps, key=len, reverse=True))
    # Not part of a longer number, though a sentence may end right after it.
    edges = rf"(?<!\d)(?<!\d[.,])(?:{pattern})(?!\d|[.,]\d)"
    return re.sub(edges, lambda m: swaps[m.group()], text)


def _swaps(keys: list[str], before: dict[str, str], after: dict[str, str]) -> dict[str, str] | None:
    """Old display -> new display for the figures a text uses; None if one can't be placed."""
    swaps: dict[str, str] = {}
    for key in keys:
        old, new = before.get(key), after.get(key)
        if old is None or old == new:
            continue
        # Gone (no longer computed), or shown the same as another figure in the same text.
        if new is None or any(before.get(k) == old for k in keys if k != key):
            return None
        swaps[old] = new
    return swaps


def _walk(value: Any, swaps: dict[str, str], key: str = "") -> Any:
    if isinstance(value, str):
        return value if key in NOT_PROSE else _replace(value, swaps)
    if isinstance(value, dict):
        return {k: v if k in NOT_PROSE else _walk(v, swaps, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, swaps, key) for v in value]
    return value


def reapply_policy(
    stored: dict[str, Any],
    context: Context,
    policy: LenderPolicy,
    slik: SlikCheck | None = None,
) -> dict[str, Any]:
    """The new policy section of a stored credit file (``memo/current``), as fields to update."""
    application = Application(**context.application)
    facts = FactTable.from_facts([Fact.model_validate(f) for f in stored.get("facts", [])])
    before = {fact.key: fact.display for fact in facts.all()}
    for key in SLIK_FACTS:
        facts.discard(key)
    summary = CashFlowSummary.model_validate(_snake(stored["cashflow"]))
    kept = [f for f in stored.get("findings", []) if f.get("kind") != "credit_history"]

    requested = monthly_installment(
        application.amount, application.tenor_months, policy.monthly_rate
    )
    facts.add("requested_installment", "Monthly instalment for the request", "rupiah", requested)
    found = slik_findings(slik, application.existing_monthly_debt, facts) if slik else []
    result = assess(
        summary=summary,
        findings=[Finding.model_validate(f) for f in kept] + found,
        evidence_types=set(context.present),
        amount=application.amount,
        tenor_months=application.tenor_months,
        existing_monthly_debt=slik.monthly_instalments
        if slik
        else application.existing_monthly_debt,
        debt_source="slik" if slik else "declared",
        policy=policy,
    )
    add_policy_facts(facts, result)
    after = {fact.key: fact.display for fact in facts.all()}

    placed = True
    memo = dict(stored.get("memo") or {})
    swaps = _swaps(memo.get("figures", []), before, after)
    if swaps is None:
        placed = False
    else:
        memo = _walk(memo, swaps)
    memo["figures"] = [key for key in memo.get("figures", []) if key in after]

    def refreshed(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal placed
        out = []
        for item in items:
            item_swaps = _swaps(item.get("figures", []), before, after)
            if item_swaps is None:
                placed = False
                out.append(item)
            else:
                out.append({**item, "text": _replace(item.get("text", ""), item_swaps)})
        return out

    findings = refreshed(kept) + [camelize(f.model_dump(mode="json", by_alias=True)) for f in found]
    confirmations = refreshed(stored.get("confirmations", []))

    was_within = (stored.get("policy") or {}).get("withinPolicy")
    note = None
    if not placed or was_within != result.within_policy:
        whose = f"{policy.lender_name}'s policy" if policy.lender_name else "this policy"
        note = (
            f"The memo's wording was written before {whose} was applied"
            + (" and the SLIK check was recorded" if slik else "")
            + ". The figures and the outcome above are current; check the file again to have the "
            "memo rewritten."
        )
    return {
        "assessment": result.assessment.value,
        "policy": camelize(result.model_dump(mode="json")),
        "findings": findings,
        "confirmations": confirmations,
        "facts": [{**fact.model_dump(), "display": fact.display} for fact in facts.all()],
        "memo": memo,
        "memoNote": note,
        "policyAppliedAt": datetime.now(UTC).isoformat(),
    }
