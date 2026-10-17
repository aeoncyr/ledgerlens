"""The analysis pipeline, from captured evidence to a cited credit memo.

    readers (Gemini, in parallel) -> calculator (code) -> verifier (Gemini)
        -> policy (code) -> memo writer (Gemini)

Each reader copies what its evidence shows; code turns that into dated amounts, monthly cash flow
and named figures, and runs every check that is only arithmetic. The verifier cross-checks the
sources and the memo writer explains the result, both referring to figures by name, so every
number a lender sees was computed by code or copied from a cited piece of evidence.

This module has no Firestore or HTTP in it: progress goes to a callback, and the result is
returned, so the same pipeline runs behind the API and in the sample-building script.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.agents.interview_listener import listen
from app.agents.ledger_reader import read_ledger_page
from app.agents.memo_writer import write_memo
from app.agents.photo_assessor import assess_photo
from app.agents.qris_reader import read_qris
from app.agents.receipt_reader import read_receipt
from app.agents.verifier import verify
from app.agents.writing import number_tokens, render
from app.analysis.evidence_store import EvidenceStore
from app.gemini import Gemini
from app.schemas import (
    TIER_BY_TYPE,
    Assessment,
    Citation,
    EvidenceType,
    Finding,
    LedgerLineOut,
)
from app.tools.cashflow import CashFlowSummary, Entry, summarise
from app.tools.dates import month_of
from app.tools.facts import Fact, FactTable
from app.tools.policy import LenderPolicy, PolicyResult, assess, consistency_findings
from app.tools.policy import monthly_installment as installment_for

log = logging.getLogger(__name__)

# agent, message, state, and optionally detail={"model": ..., "sample": ...} for the live trace
Progress = Callable[..., Awaitable[None]]

KUR_COLLATERAL_FREE_LIMIT = 100_000_000  # KUR loans up to this amount need no extra collateral
MAX_PARALLEL_READS = 8
LOW_CONFIDENCE = 0.6

LABELS: dict[EvidenceType, tuple[str, str, str]] = {
    # type: (label, fact-key prefix, agent name)
    EvidenceType.LEDGER_PAGE: ("Notebook page", "page", "ledger_reader"),
    EvidenceType.RECEIPT: ("Receipt", "receipt", "receipt_reader"),
    EvidenceType.QRIS_HISTORY: ("QRIS history", "qris", "qris_reader"),
    EvidenceType.SHOP_PHOTO: ("Shop photo", "photo", "photo_assessor"),
    EvidenceType.INTERVIEW_AUDIO: ("Interview", "interview", "interview_listener"),
}


@dataclass
class EvidenceItem:
    id: str
    type: EvidenceType
    storage_path: str
    captured_at: datetime
    label: str = ""
    key: str = ""
    submitted_by: str = "officer"  # or "owner": sent from the owner's phone, not taken on a visit


@dataclass
class Application:
    alias: str
    business_type: str
    city: str
    years_operating: int
    amount: int
    tenor_months: int
    # Other loan instalments a month the application declares, including online loans (pinjol).
    existing_monthly_debt: int = 0


@dataclass
class ItemResult:
    item: EvidenceItem
    extraction: dict[str, Any] | None = None
    models: list[str] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)
    checks: list[Finding] = field(default_factory=list)
    digest: dict[str, Any] = field(default_factory=dict)
    written: list[str] = field(default_factory=list)  # amounts as written, which may be quoted
    error: str | None = None
    dispute: Finding | None = None  # the check listing lines whose two readings disagree
    dispute_lines: list[int] = field(default_factory=list)


class Context(BaseModel):
    """Everything the judging stage needs, saved so a file can be re-checked without re-reading."""

    application: dict[str, Any]
    case_file: dict[str, Any]
    facts: list[Fact]
    summary: CashFlowSummary
    checks: dict[str, Finding]
    present: list[EvidenceType]
    quoted: list[str]
    evidence_ids: list[str]
    extractions: dict[str, dict[str, Any]]
    unreadable: list[str]
    reader_models: list[str]
    round: int = 0
    # For re-judging after an officer confirms a disputed reading:
    entries: list[Entry] = []
    item_keys: dict[str, list[str]] = {}  # evidence id -> [fact key prefix, label]
    disputes: dict[str, dict[str, Any]] = {}  # check id -> {evidence_id, lines}
    consistency_ids: list[str] = []  # checks that come from the cash-flow arithmetic
    confirmed: dict[str, dict[str, int]] = {}  # evidence id -> {line: amount the officer confirmed}
    pending_confirmations: bool = False
    answered: list[str] = []  # questions whose answers the last judging already weighed


class AnalysisResult(BaseModel):
    assessment: Assessment
    policy: PolicyResult
    cashflow: CashFlowSummary
    findings: list[Finding]
    confirmations: list[dict[str, Any]]
    memo: dict[str, Any]
    facts: list[dict[str, Any]]
    extractions: dict[str, dict[str, Any]]
    unreadable: list[str]
    models: list[str]
    figure_problems: list[str]
    round: int = 0
    context: Context


def _rp(value: int | None) -> str:
    return "unreadable" if value is None else "Rp " + f"{value:,}".replace(",", ".")


def _month(item: EvidenceItem) -> str:
    return item.captured_at.strftime("%Y-%m")


def _cite(item: EvidenceItem, locator: str) -> Citation:
    return Citation(evidence_id=item.id, locator=locator)


def label_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Number each kind of evidence in capture order: Notebook page 1, Receipt 2, ..."""
    ordered = sorted(items, key=lambda i: (list(LABELS).index(i.type), i.captured_at, i.id))
    counts: dict[EvidenceType, int] = {}
    for item in ordered:
        counts[item.type] = counts.get(item.type, 0) + 1
        label, prefix, _ = LABELS[item.type]
        number = counts[item.type]
        item.label = label if item.type is EvidenceType.INTERVIEW_AUDIO else f"{label} {number}"
        item.key = f"{prefix}_{number}"
    return ordered


# --- Readers ---------------------------------------------------------------------------------


def reconcile(
    first: list[LedgerLineOut], second: list[LedgerLineOut], slack: int = 2
) -> tuple[list[LedgerLineOut], list[tuple[int, int | None, int | None]]]:
    """Compare two readings of the same page; amounts the second reading doesn't confirm are
    marked uncertain.

    The two readings may number lines differently (one may skip a heading), so an amount counts as
    confirmed when the second reading has the same amount within ``slack`` lines of it.
    """
    unused = [line for line in second if line.amount_rp is not None]
    by_number = {line.line: line for line in second}
    lines, disagreements = [], []
    for line in first:
        if line.amount_rp is not None:
            match = next(
                (
                    other
                    for other in unused
                    if other.amount_rp == line.amount_rp and abs(other.line - line.line) <= slack
                ),
                None,
            )
            if match is not None:
                unused.remove(match)
            else:
                other = by_number.get(line.line)
                disagreements.append(
                    (line.line, line.amount_rp, other.amount_rp if other else None)
                )
                line = line.model_copy(update={"confidence": min(line.confidence, 0.5)})
        lines.append(line)
    return lines, disagreements


async def _read_ledger(
    gemini: Gemini,
    result: ItemResult,
    data: bytes,
    mime: str,
    facts: FactTable,
    double_read: bool = True,
) -> str:
    item = result.item
    if double_read:
        (first, model_a), (second, model_b) = await asyncio.gather(
            read_ledger_page(gemini, data, mime, variant=0),
            read_ledger_page(gemini, data, mime, variant=1),
        )
        result.models += [model_a, model_b]
        lines, disagreements = reconcile(first, second)
    else:  # one reading saves calls on the free tier; low confidence still flags unclear lines
        lines, model = await read_ledger_page(gemini, data, mime, variant=0)
        result.models.append(model)
        disagreements = []
    if not any(line.amount_rp is not None for line in lines):
        raise ValueError("no amounts could be read")

    reference = item.captured_at.date()
    current: str | None = None
    for line in lines:
        written_month = month_of(line.date_text, reference)
        if written_month is None and line.amount_text is None:
            written_month = month_of(line.description, reference)  # headings like "Sep - minggu 1"
        current = written_month or current
        if line.amount_rp is not None and line.kind in (
            "sale",
            "purchase",
            "expense",
            "receivable",
        ):
            result.entries.append(
                Entry(
                    month=current or _month(item),
                    kind=line.kind,
                    amount_rp=line.amount_rp,
                    evidence_type=item.type,
                    evidence_id=item.id,
                    locator=f"line {line.line}",
                )
            )
        if line.amount_text:
            result.written.append(line.amount_text)

    if disagreements:
        detail = "; ".join(f"line {n}: {_rp(a)} or {_rp(b)}" for n, a, b in disagreements)
        result.dispute = Finding(
            kind="low_confidence",
            severity="low",
            source="code",
            text=f"The two readings of {item.label} disagree ({detail}). Confirm on the photo.",
            citations=[_cite(item, f"line {n}") for n, _, _ in disagreements],
        )
        result.dispute_lines = [n for n, _, _ in disagreements]
        result.checks.append(result.dispute)
    unclear = [
        line
        for line in lines
        if line.amount_rp is not None
        and line.confidence < LOW_CONFIDENCE
        and line.line not in {n for n, _, _ in disagreements}
    ]
    if unclear:
        result.checks.append(
            Finding(
                kind="low_confidence",
                severity="low",
                source="code",
                text=f"Some amounts on {item.label} were hard to read. Confirm them on the photo.",
                citations=[_cite(item, f"line {line.line}") for line in unclear],
            )
        )

    by_kind = {kind: 0 for kind in ("sale", "purchase", "expense")}
    for entry in result.entries:
        if entry.kind in by_kind:
            by_kind[entry.kind] += entry.amount_rp
    facts.add(f"{item.key}_sales", f"Sales written on {item.label}", "rupiah", by_kind["sale"])
    facts.add(
        f"{item.key}_purchases", f"Purchases written on {item.label}", "rupiah", by_kind["purchase"]
    )
    result.extraction = {
        "lines": [line.model_dump(by_alias=True) for line in lines],
        # Lines where the two readings disagree; an officer can confirm the right amount.
        "disagreements": [{"line": n, "first": a, "second": b} for n, a, b in disagreements],
    }
    result.digest = {
        "lines": [
            {
                "locator": f"line {line.line}",
                "date": line.date_text,
                "text": line.description,
                "amount_written": line.amount_text,
                "crossed_out": line.crossed_out_text,
                "kind": line.kind,
                "confidence": line.confidence,
            }
            for line in lines
        ],
        "figures": [f"{item.key}_sales", f"{item.key}_purchases"],
    }
    return f"Read {len(lines)} lines from {item.label}"


async def _read_receipt(
    gemini: Gemini, result: ItemResult, data: bytes, mime: str, facts: FactTable
) -> str:
    item = result.item
    receipt, model = await read_receipt(gemini, data, mime)
    result.models.append(model)
    if not receipt.legible:
        raise ValueError("the receipt is not legible")
    amount = receipt.total_rp if receipt.total_rp is not None else receipt.items_sum_rp
    if amount is None:
        result.checks.append(
            Finding(
                kind="missing_evidence",
                severity="low",
                source="code",
                text=f"The total on {item.label} could not be read.",
                citations=[_cite(item, "total")],
            )
        )
    else:
        result.entries.append(
            Entry(
                month=month_of(receipt.date_text, item.captured_at.date()) or _month(item),
                kind="purchase",
                amount_rp=amount,
                evidence_type=item.type,
                evidence_id=item.id,
                locator="total",
            )
        )
        facts.add(f"{item.key}_total", f"Total of {item.label}", "rupiah", amount, [item.id])
    reference = receipt.subtotal_rp or (receipt.total_rp if not receipt.discount_rp else None)
    if (
        receipt.items_sum_rp is not None
        and reference
        and abs(receipt.items_sum_rp - reference) > 0.01 * reference
        and not receipt.tax_rp
    ):
        result.checks.append(
            Finding(
                kind="low_confidence",
                severity="low",
                source="code",
                text=(
                    f"The items on {item.label} add up to {_rp(receipt.items_sum_rp)}, "
                    f"not the printed {_rp(reference)}."
                ),
                citations=[_cite(item, "items"), _cite(item, "total")],
            )
        )
    result.written += [i.amount_text for i in receipt.items if i.amount_text]
    result.written += [receipt.total_text] if receipt.total_text else []
    result.extraction = receipt.model_dump(by_alias=True)
    result.digest = {
        "merchant": receipt.merchant,
        "date": receipt.date_text,
        "handwritten": receipt.handwritten,
        "items": [
            {"name": i.name, "quantity": i.quantity_text, "amount_written": i.amount_text}
            for i in receipt.items
        ],
        "total_written": receipt.total_text,
        "figures": [f"{item.key}_total"] if amount is not None else [],
    }
    return f"Read {item.label}: {len(receipt.items)} items, total {_rp(amount)}"


async def _read_qris(
    gemini: Gemini, result: ItemResult, data: bytes, mime: str, facts: FactTable
) -> str:
    item = result.item
    qris, model = await read_qris(gemini, data, mime)
    result.models.append(model)
    if not qris.legible:
        raise ValueError("the screenshot is not legible")
    reference = item.captured_at.date()
    covered: set[str] = set()
    for total in qris.totals:
        month = month_of(total.period_text, reference)
        if total.amount_rp is not None and month and month not in covered:
            covered.add(month)
            result.entries.append(
                Entry(
                    month=month,
                    kind="sale",
                    amount_rp=total.amount_rp,
                    evidence_type=item.type,
                    evidence_id=item.id,
                    locator=f"total for {total.period_text}",
                )
            )
    for row in qris.rows:
        month = month_of(row.date_text, reference) or _month(item)
        if row.direction == "in" and row.amount_rp is not None and month not in covered:
            result.entries.append(
                Entry(
                    month=month,
                    kind="sale",
                    amount_rp=row.amount_rp,
                    evidence_type=item.type,
                    evidence_id=item.id,
                    locator=f"row {row.row}",
                )
            )
    inflows = sum(entry.amount_rp for entry in result.entries)
    facts.add(
        f"{item.key}_inflows", f"Money received in {item.label}", "rupiah", inflows, [item.id]
    )

    for problem in qris.arithmetic_problems:
        result.checks.append(
            Finding(
                kind="fraud_signal",
                severity="high",
                source="code",
                text=f"{item.label}: {problem} The screenshot may have been edited.",
                citations=[_cite(item, "rows"), _cite(item, "total")],
            )
        )
    if qris.editing_signs:
        result.checks.append(
            Finding(
                kind="low_confidence",
                severity="medium",
                source="code",
                text=(
                    f"{item.label} shows possible signs of editing: "
                    f"{'; '.join(qris.editing_signs)}. Check the history in the app itself."
                ),
                citations=[_cite(item, "whole screenshot")],
            )
        )
    if not qris.is_screenshot:
        result.checks.append(
            Finding(
                kind="low_confidence",
                severity="low",
                source="code",
                text=f"{item.label} is a photo of a screen or paper, not a screenshot.",
                citations=[_cite(item, "whole screenshot")],
            )
        )
    result.written += [row.amount_text for row in qris.rows]
    result.written += [total.amount_text for total in qris.totals]
    result.extraction = qris.model_dump()
    result.digest = {
        "app": qris.app_name,
        "merchant": qris.merchant_name,
        "rows": [
            {
                "locator": f"row {row.row}",
                "date": row.date_text,
                "time": row.time_text,
                "amount_written": row.amount_text,
                "direction": row.direction,
                "label": row.label,
            }
            for row in qris.rows
        ],
        "totals": [
            {"period": t.period_text, "amount_written": t.amount_text, "count": t.count}
            for t in qris.totals
        ],
        "editing_signs": qris.editing_signs,
        "figures": [f"{item.key}_inflows"],
    }
    return f"Read {item.label}: {len(qris.rows)} transactions, {len(qris.totals)} totals"


async def _assess_photo(
    gemini: Gemini, result: ItemResult, data: bytes, mime: str, business_type: str
) -> str:
    assessment, model = await assess_photo(gemini, data, mime, business_type=business_type)
    result.models.append(model)
    result.extraction = assessment.model_dump()
    result.digest = assessment.model_dump()
    return (
        f"Looked at {result.item.label}: {assessment.business_seen}, stock {assessment.stock_level}"
    )


async def _listen(
    gemini: Gemini, result: ItemResult, data: bytes, mime: str, facts: FactTable
) -> str:
    item = result.item
    interview, model = await listen(gemini, data, mime)
    result.models.append(model)
    if not interview.audible:
        raise ValueError("the recording is not audible")
    claims = []
    for number, claim in enumerate(interview.claims, start=1):
        key = f"{item.key}_claim_{number}"
        figures = []
        if claim.amount_rp is not None:
            facts.add(
                key, f"Owner said: {claim.statement_en}", "rupiah", claim.amount_rp, [item.id]
            )
            figures.append(key)
        if claim.monthly_rp is not None and claim.period != "month":
            facts.add(
                f"{key}_monthly",
                f"Owner's figure as a monthly amount (code's estimate, 26 trading days a month): "
                f"{claim.statement_en}",
                "rupiah",
                claim.monthly_rp,
                [item.id],
            )
            figures.append(f"{key}_monthly")
        claims.append(
            {
                "locator": claim.time_text or "recording",
                "topic": claim.topic,
                "statement": claim.statement_en,
                "quote": claim.quote,
                "amount_said": claim.amount_text,
                "period": claim.period,
                "figures": figures,
            }
        )
        if claim.amount_text:
            result.written.append(claim.amount_text)
    result.extraction = interview.model_dump()
    result.digest = {"summary": interview.summary_en, "claims": claims}
    return f"Listened to the interview: {len(claims)} claims"


async def read_item(
    gemini: Gemini,
    store: EvidenceStore,
    item: EvidenceItem,
    application: Application,
    facts: FactTable,
    limit: asyncio.Semaphore,
    progress: Progress,
    double_read: bool = True,
) -> ItemResult:
    result = ItemResult(item=item)
    agent = LABELS[item.type][2]
    async with limit:
        await progress(agent, f"Reading {item.label}", "running")
        try:
            data, mime = await store.read(item.storage_path)
            if item.type is EvidenceType.LEDGER_PAGE:
                message = await _read_ledger(gemini, result, data, mime, facts, double_read)
            elif item.type is EvidenceType.RECEIPT:
                message = await _read_receipt(gemini, result, data, mime, facts)
            elif item.type is EvidenceType.QRIS_HISTORY:
                message = await _read_qris(gemini, result, data, mime, facts)
            elif item.type is EvidenceType.SHOP_PHOTO:
                message = await _assess_photo(gemini, result, data, mime, application.business_type)
            else:
                message = await _listen(gemini, result, data, mime, facts)
        except Exception as exc:  # one unreadable item must not stop the analysis
            log.warning("Could not read %s (%s): %s", item.label, item.id, exc)
            result.error = str(exc)
            result.entries, result.checks = [], []
            result.checks.append(
                Finding(
                    kind="missing_evidence",
                    severity="medium",
                    source="code",
                    text=f"{item.label} could not be read ({exc}). Retake it if it matters.",
                    citations=[_cite(item, "whole item")],
                )
            )
            await progress(agent, f"Could not read {item.label}", "failed")
            return result
    await progress(agent, message, "done", detail=_detail(result))
    return result


def apply_confirmations(
    context: Context, facts: FactTable, application: Application, policy: LenderPolicy
) -> tuple[CashFlowSummary, dict[str, Finding]]:
    """Rebuild the cash flow and the arithmetic checks with the amounts an officer confirmed."""
    entries = []
    for entry in context.entries:
        line = entry.locator.removeprefix("line ")
        confirmed = context.confirmed.get(entry.evidence_id, {}).get(line)
        entries.append(
            entry if confirmed is None else entry.model_copy(update={"amount_rp": confirmed})
        )
    summary = summarise(_analysis_window(entries))
    add_summary_facts(facts, summary, application)
    for evidence_id, (key, label) in context.item_keys.items():
        page = [e for e in entries if e.evidence_id == evidence_id]
        if page and page[0].evidence_type is EvidenceType.LEDGER_PAGE:
            sales = sum(e.amount_rp for e in page if e.kind == "sale")
            buys = sum(e.amount_rp for e in page if e.kind == "purchase")
            facts.add(f"{key}_sales", f"Sales written on {label}", "rupiah", sales)
            facts.add(f"{key}_purchases", f"Purchases written on {label}", "rupiah", buys)

    checks = {
        i: c
        for i, c in context.checks.items()
        if i not in context.consistency_ids
        and not _settled(context.disputes.get(i), context.confirmed)
    }
    for finding in consistency_findings(summary, policy, application.business_type):
        checks[f"check-{len(context.checks) + len(checks) + 1}"] = finding
    return summary, checks


def _settled(dispute: dict[str, Any] | None, confirmed: dict[str, dict[str, int]]) -> bool:
    """A disagreement is settled once the officer has confirmed every disputed line."""
    if not dispute:
        return False
    done = confirmed.get(dispute["evidence_id"], {})
    return all(str(line) in done for line in dispute["lines"])


def _detail(result: ItemResult) -> dict[str, Any]:
    """What the live trace shows about a finished reader: its model, and for a notebook page a few
    of the lines it extracted, so a viewer can see the structured output itself."""
    detail: dict[str, Any] = {"model": result.models[0] if result.models else None}
    lines = (result.extraction or {}).get("lines")
    if result.item.type is EvidenceType.LEDGER_PAGE and lines:
        keep = ("dateText", "description", "amountText", "amountRp", "kind", "confidence")
        detail["sample"] = [
            {k: line.get(k) for k in keep} for line in lines if line.get("amountText")
        ][:3]
        detail["sampleLabel"] = f"{result.item.label} · first lines"
    return detail


# --- Pipeline --------------------------------------------------------------------------------


def _analysis_window(entries: list[Entry]) -> list[Entry]:
    """Compare like with like: if the notebook covers some months, judge those months."""
    notebook_months = {
        e.month for e in entries if e.evidence_type is EvidenceType.LEDGER_PAGE and e.kind == "sale"
    }
    return [e for e in entries if e.month in notebook_months] if notebook_months else entries


def add_summary_facts(facts: FactTable, summary: CashFlowSummary, application: Application) -> None:
    facts.add("months_covered", "Months of evidence analysed", "count", len(summary.months))
    facts.add(
        "avg_claimed_sales",
        "Monthly sales the notebook claims",
        "rupiah",
        summary.avg_claimed_sales,
    )
    facts.add(
        "avg_proven_inflows",
        "Monthly money received via QRIS (hard evidence)",
        "rupiah",
        summary.avg_proven_inflows,
    )
    facts.add(
        "avg_receipt_purchases",
        "Monthly supplier purchases on receipts",
        "rupiah",
        summary.avg_receipt_purchases,
    )
    facts.add("avg_costs", "Monthly costs (purchases and expenses)", "rupiah", summary.avg_costs)
    facts.add(
        "revenue_low",
        "Monthly revenue, low end (hard evidence only)",
        "rupiah",
        summary.revenue_low,
    )
    facts.add(
        "revenue_high", "Monthly revenue, high end (all evidence)", "rupiah", summary.revenue_high
    )
    facts.add("net_high", "Monthly net cash flow, high end", "rupiah", summary.net_high)
    facts.add(
        "hard_coverage", "Share of claimed sales seen in QRIS", "percent", summary.hard_coverage
    )
    facts.add(
        "sales_to_purchases",
        "Claimed sales as a multiple of receipt purchases",
        "ratio",
        summary.sales_to_purchases,
    )
    facts.add("requested_amount", "Loan amount requested", "rupiah", application.amount)
    facts.add("tenor_months", "Loan term in months", "count", application.tenor_months)
    facts.add(
        "existing_monthly_debt",
        "Other loan instalments a month, including online loans, as the application declares",
        "rupiah",
        application.existing_monthly_debt,
    )
    facts.add(
        "kur_collateral_free_limit",
        "KUR loans up to this amount need no extra collateral",
        "rupiah",
        KUR_COLLATERAL_FREE_LIMIT,
    )


def merge_findings(
    checks: dict[str, Finding],
    drafts: list[Any],
    facts: FactTable,
    evidence_ids: set[str],
    answers: list[dict[str, str]] | None = None,
) -> list[Finding]:
    """Combine the verifier's findings with code's checks; code keeps the final say.

    Code decides severity for its own checks, and an owner's answer may never resolve a material
    contradiction that code found in the figures: that needs evidence, not an explanation.
    """
    answers = answers or []
    merged: list[Finding] = []
    explained: set[str] = set()
    for draft in drafts:
        check = checks.get(draft.check_id or "")
        if check is not None:
            if draft.check_id in explained:
                continue
            explained.add(draft.check_id)
        citations = [
            Citation(evidence_id=c.evidence_id, locator=c.locator)
            for c in draft.citations
            if c.evidence_id in evidence_ids
        ]
        severity = check.severity if check else _verifier_severity(draft)
        material_check = check is not None and severity == "high"
        answered = (
            answers[draft.answered_by - 1] if 0 < (draft.answered_by or 0) <= len(answers) else None
        )
        merged.append(
            Finding(
                kind=check.kind if check else draft.kind,
                severity=severity,
                resolved=bool(draft.resolved and answered and not material_check),
                answer=answered["answer"] if answered else None,
                source="code" if check else "verifier",
                text=facts.render(draft.text),
                citations=citations or (check.citations if check else []),
                follow_up_question=facts.render(draft.follow_up_question or "") or None,
                follow_up_question_en=facts.render(draft.follow_up_question_en or "") or None,
                figures=[key for key in facts_in(draft.text) if key in facts],
            )
        )
    merged += [check for check_id, check in checks.items() if check_id not in explained]
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(merged, key=lambda f: order[f.severity])


def _verifier_severity(draft: Any) -> str:
    # Missing evidence that matters (QRIS, receipts) is handled by code and the policy; what the
    # verifier adds (no photo, no interview) must not on its own stop a file being verified.
    return "low" if draft.kind == "missing_evidence" else draft.severity


def facts_in(text: str) -> list[str]:
    import re

    return re.findall(r"\[\[([a-z0-9_]+)\]\]", text)


async def run_pipeline(
    *,
    gemini: Gemini,
    store: EvidenceStore,
    application: Application,
    items: list[EvidenceItem],
    progress: Progress,
    policy: LenderPolicy | None = None,
    max_parallel: int = MAX_PARALLEL_READS,
    double_read: bool = True,
) -> AnalysisResult:
    policy = policy or LenderPolicy()
    items = label_items(items)
    facts = FactTable()
    limit = asyncio.Semaphore(max_parallel)

    await progress("intake", f"Reading {len(items)} pieces of evidence in parallel", "running")
    results = await asyncio.gather(
        *(
            read_item(gemini, store, i, application, facts, limit, progress, double_read)
            for i in items
        )
    )
    readable = [r for r in results if r.error is None]
    await progress("intake", f"Read {len(readable)} of {len(items)} pieces of evidence", "done")

    await progress("calculator", "Computing monthly cash flow", "running")
    entries = _analysis_window([e for r in results for e in r.entries])
    summary = summarise(entries)
    add_summary_facts(facts, summary, application)
    requested = installment_for(application.amount, application.tenor_months, policy.monthly_rate)
    facts.add("requested_installment", "Monthly instalment for the request", "rupiah", requested)
    await progress(
        "calculator",
        f"Cash flow over {len(summary.months)} month(s) from {len(entries)} amounts",
        "done",
    )

    checks: dict[str, Finding] = {}
    disputes: dict[str, dict[str, Any]] = {}
    for r in results:
        for finding in r.checks:
            check_id = f"check-{len(checks) + 1}"
            checks[check_id] = finding
            if finding is r.dispute:
                disputes[check_id] = {"evidence_id": r.item.id, "lines": r.dispute_lines}
    consistency_ids = []
    for finding in consistency_findings(summary, policy, application.business_type):
        check_id = f"check-{len(checks) + 1}"
        checks[check_id] = finding
        consistency_ids.append(check_id)
    present = {r.item.type for r in readable}
    qris = [r for r in readable if r.item.type is EvidenceType.QRIS_HISTORY]
    if qris and all(r.item.submitted_by == "owner" for r in qris):
        checks[f"check-{len(checks) + 1}"] = Finding(
            kind="low_confidence",
            severity="medium",
            source="code",
            text="The QRIS history was sent by the owner, not captured on a visit. Confirm it in "
            "the merchant app before relying on it as hard evidence.",
            citations=[_cite(r.item, "whole screenshot") for r in qris],
        )
    if EvidenceType.QRIS_HISTORY not in present:
        checks[f"check-{len(checks) + 1}"] = Finding(
            kind="missing_evidence",
            severity="medium",
            source="code",
            text="There is no QRIS or e-wallet history, so no sales are confirmed by a payment "
            "provider and the low end of cash flow rests on receipts alone.",
        )

    case_file = {
        "business": {
            "alias": application.alias,
            "type": application.business_type,
            "city": application.city,
            "years_operating": application.years_operating,
        },
        "request": {
            "amount": "[[requested_amount]]",
            "term_months": application.tenor_months,
            # What the application says; the verifier compares it with what the owner says.
            "other_monthly_loan_instalments": "[[existing_monthly_debt]]",
        },
        "facts": facts.for_prompt(),
        "evidence": [
            {
                "evidence_id": r.item.id,
                "label": r.item.label,
                "type": r.item.type.value,
                "tier": TIER_BY_TYPE[r.item.type].value,
                "captured": r.item.captured_at.date().isoformat(),
                "submitted_by": r.item.submitted_by,
                "reading": r.digest,
            }
            for r in readable
        ],
        "unreadable": [r.item.label for r in results if r.error],
        "evidence_types_missing": [t.value for t in EvidenceType if t not in present],
        "checks": [
            {
                "check_id": check_id,
                "kind": c.kind,
                "severity": c.severity,
                "text": c.text,
                "citations": [x.model_dump() for x in c.citations],
            }
            for check_id, c in checks.items()
        ],
    }
    context = Context(
        application=asdict(application),
        case_file=case_file,
        facts=facts.all(),
        summary=summary,
        checks=checks,
        present=sorted(present),
        quoted=sorted(
            number_tokens([w for r in results for w in r.written])
            | number_tokens([c.text for c in checks.values()])
        ),
        evidence_ids=[r.item.id for r in results],
        extractions={r.item.id: {"label": r.item.label, **(r.extraction or {})} for r in results},
        unreadable=[r.item.label for r in results if r.error],
        reader_models=sorted({m for r in results for m in r.models}),
        entries=[e for r in results for e in r.entries],
        item_keys={r.item.id: [r.item.key, r.item.label] for r in results},
        disputes=disputes,
        consistency_ids=consistency_ids,
    )
    return await judge(gemini=gemini, context=context, progress=progress, policy=policy)


async def judge(
    *,
    gemini: Gemini,
    context: Context,
    progress: Progress,
    policy: LenderPolicy | None = None,
    answers: list[dict[str, str]] | None = None,
) -> AnalysisResult:
    """Cross-check, apply the policy and write the memo, from readings already made.

    ``answers`` are the owner's replies to earlier follow-up questions; the verifier weighs them,
    and code decides which findings an answer may resolve.
    """
    policy = policy or LenderPolicy()
    application = Application(**context.application)
    facts = FactTable.from_facts(context.facts)
    summary, checks = context.summary, context.checks
    present = set(context.present)
    quoted = set(context.quoted)
    evidence_ids = set(context.evidence_ids)
    case_file = dict(context.case_file)
    if context.confirmed:
        summary, checks = apply_confirmations(context, facts, application, policy)
        case_file["facts"] = facts.for_prompt()
        case_file["checks"] = [
            {"check_id": i, "kind": c.kind, "severity": c.severity, "text": c.text}
            for i, c in checks.items()
        ]
        case_file["officer_confirmed"] = [
            {"evidence_id": ev, "locator": f"line {line}", "amount": _rp(amount)}
            for ev, lines in context.confirmed.items()
            for line, amount in lines.items()
        ]
        quoted |= number_tokens([c.text for c in checks.values()])
        quoted |= number_tokens([x["amount"] for x in case_file["officer_confirmed"]])
    if answers:
        case_file["owner_answers"] = [
            {"number": n, **answer} for n, answer in enumerate(answers, start=1)
        ]
        quoted |= number_tokens([a["answer"] for a in answers])

    await progress("verifier", "Cross-checking the sources against each other", "running")
    verification, verifier_model, verifier_problems = await verify(gemini, case_file, facts, quoted)
    findings = merge_findings(checks, verification.findings, facts, evidence_ids, answers or [])
    confirmations = [
        {
            "text": facts.render(c.text),
            "figures": [k for k in facts_in(c.text) if k in facts],
            "citations": [x.model_dump() for x in c.citations if x.evidence_id in evidence_ids],
        }
        for c in verification.confirmations
    ]
    resolved = sum(f.resolved for f in findings)
    await progress(
        "verifier",
        f"{len(findings)} finding(s), {resolved} explained by the owner, "
        f"{len(confirmations)} point(s) where the sources agree"
        if answers
        else f"{len(findings)} finding(s), {len(confirmations)} point(s) where the sources agree",
        "done",
        detail={"model": verifier_model},
    )

    await progress("policy", "Applying the lender's policy", "running")
    result = assess(
        summary=summary,
        findings=findings,
        evidence_types=present,
        amount=application.amount,
        tenor_months=application.tenor_months,
        existing_monthly_debt=application.existing_monthly_debt,
        policy=policy,
    )
    facts.add(
        "capacity_basis",
        "Net monthly cash flow after the policy's haircut",
        "rupiah",
        result.capacity_basis,
    )
    facts.add(
        "max_installment",
        "Largest monthly instalment the policy allows",
        "rupiah",
        result.max_installment,
    )
    # Only a request within the policy has room to stress; above it, the figure would say nothing.
    stress_tested = result.within_policy and result.stress_drop_pct is not None
    facts.add(
        "stress_drop_pct",
        "Fall in sales the requested instalment can take and stay within policy (code's stress "
        "test: costs move with sales)",
        "percent",
        result.stress_drop_pct / 100 if stress_tested else None,
    )
    facts.add(
        "evidence_strength", "Evidence strength, out of 100", "count", result.evidence_strength
    )
    outcome_label = result.assessment.value.replace("_", " ")
    await progress("policy", f"Outcome: {outcome_label}", "done")

    await progress("memo_writer", "Writing the credit memo", "running")
    case_file["facts"] = facts.for_prompt()
    memo, memo_model, memo_problems = await write_memo(
        gemini,
        case_file,
        [
            f.model_dump(include={"kind", "severity", "text", "citations", "resolved", "answer"})
            for f in findings
        ],
        {
            "assessment": result.assessment.value,
            "within_policy": result.within_policy,
            "reasons": result.reasons,
            "figures": [
                "capacity_basis",
                "max_installment",
                "requested_installment",
                # Files checked before these figures existed don't have them.
                *(["existing_monthly_debt"] if "existing_monthly_debt" in facts else []),
                *(["stress_drop_pct"] if stress_tested else []),
            ],
        },
        facts,
        quoted,
    )
    rendered_memo = render(memo.model_dump(), facts)
    rendered_memo["figures"] = sorted(
        {key for text in _all_text(memo.model_dump()) for key in facts_in(text) if key in facts}
    )
    await progress("memo_writer", "Credit memo ready", "done", detail={"model": memo_model})

    return AnalysisResult(
        assessment=result.assessment,
        policy=result,
        cashflow=summary,
        findings=findings,
        confirmations=confirmations,
        memo=rendered_memo,
        facts=[_fact_out(f) for f in facts.all()],
        extractions=context.extractions,
        unreadable=context.unreadable,
        models=sorted(set(context.reader_models) | {verifier_model, memo_model}),
        figure_problems=verifier_problems + memo_problems,
        round=context.round,
        context=context,
    )


def _fact_out(fact: Fact) -> dict[str, Any]:
    return {**fact.model_dump(), "display": fact.display}


def _all_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [t for v in value.values() for t in _all_text(v)]
    if isinstance(value, list):
        return [t for v in value for t in _all_text(v)]
    return []
