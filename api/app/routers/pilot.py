"""The pilot dashboard: what LedgerLens did on one officer's files, counted by code.

A lender trying LedgerLens in a shadow pilot wants to know a few things: how many files went
through and how they came out, how long it took from the first record to a checked file and to a
decision, what the checks caught, how often the officer agreed with LedgerLens's assessment, which
records were most often missing, and whether owners or officers started the files. Every figure
here is counted or computed in Python from the officer's own files in Firestore; nothing is
estimated and no model is involved. These are one workspace's files, not a market study, and demo
copies of the sample files are counted only when asked for, and always labelled.
"""

from __future__ import annotations

import asyncio
import csv
import io
import statistics
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from google.cloud import firestore
from google.cloud.firestore import FieldFilter

from app.auth import User, current_user
from app.routers.applications import OFFICER
from app.routers.exports import _cell
from app.schemas import CamelModel, EvidenceType
from app.store import get_firestore

router = APIRouter(prefix="/api/pilot", tags=["pilot"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]
IncludeDemo = Annotated[bool, Query(alias="includeDemo")]

# Enough for a pilot's three months; more than that belongs in the lender's own reporting.
MAX_FILES = 500
FINDING_KINDS = ("fraud_signal", "discrepancy", "missing_evidence", "low_confidence")
# The officer's decision, whether it then waits for a sign-off or goes to the owner at once.
DECISION_ACTIONS = {"recommended_approve", "recommended_decline", "decision_request_more"}


class PilotFile(CamelModel):
    application_id: str
    file_number: str
    alias: str
    demo: bool
    origin: str
    status: str | None
    outcome: str | None
    evidence_count: int
    missing_evidence: list[EvidenceType]
    findings: int
    findings_by_kind: dict[str, int]
    minutes_to_analysis: float | None
    minutes_to_decision: float | None
    decision: str | None
    decision_state: str | None
    assessment_agreed: bool | None
    disagreement_reason: str | None


class MissingCount(CamelModel):
    type: EvidenceType
    files: int


class PilotReport(CamelModel):
    include_demo: bool
    files: int
    demo_files: int
    by_status: dict[str, int]
    by_outcome: dict[str, int]
    by_origin: dict[str, int]
    median_minutes_to_analysis: float | None
    timed_to_analysis: int
    median_minutes_to_decision: float | None
    timed_to_decision: int
    findings_by_kind: dict[str, int]
    files_with_fraud_signal: int
    decided: int
    agreed: int
    disagreed: int
    agreed_pct: int | None
    checked_files: int
    missing_evidence: list[MissingCount]
    rows: list[PilotFile]


def _when(value: Any) -> datetime | None:
    """A Firestore time as an aware datetime; anything else (a pending server time) is unknown."""
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _minutes(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None or end < start:
        return None
    return round((end - start).total_seconds() / 60, 1)


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


async def _file(db: firestore.AsyncClient, snapshot: Any) -> PilotFile:
    """One file's row, from the application, its evidence, runs, credit file and audit log."""
    data = snapshot.to_dict() or {}
    ref = db.collection("applications").document(snapshot.id)

    async def stream(name: str) -> list[dict[str, Any]]:
        return [(s.to_dict() or {}) async for s in ref.collection(name).stream()]

    evidence, runs, audit, memo = await asyncio.gather(
        stream("evidence"),
        stream("runs"),
        stream("audit"),
        ref.collection("memo").document("current").get(),
    )
    findings = ((memo.to_dict() or {}).get("findings") or []) if memo.exists else []
    by_kind = {kind: 0 for kind in FINDING_KINDS}
    for finding in findings:
        kind = finding.get("kind")
        if kind in by_kind:
            by_kind[kind] += 1

    outcome = data.get("assessment")
    present = {item.get("type") for item in evidence}
    # Only a checked file says what was missing when it was checked.
    missing = [kind for kind in EvidenceType if kind.value not in present] if outcome else []

    def first(times: list[datetime | None], after: datetime | None) -> datetime | None:
        known = [t for t in times if t is not None and (after is None or t >= after)]
        return min(known) if known else None

    first_record = first(
        [_when(a.get("at")) for a in audit if a.get("action") == "evidence_added"], None
    )
    checked = first(
        [_when(r.get("finishedAt")) for r in runs if r.get("state") == "done"], first_record
    )
    decided = first(
        [_when(a.get("at")) for a in audit if a.get("action") in DECISION_ACTIONS], first_record
    )

    decision = data.get("decision") or {}
    business = data.get("business") or {}
    return PilotFile(
        application_id=snapshot.id,
        file_number=f"LL-{snapshot.id[:8].upper()}",
        alias=business.get("alias") or "",
        demo=data.get("demo") is True,
        origin=data.get("origin") or OFFICER,
        status=data.get("status"),
        outcome=outcome,
        evidence_count=len(evidence),
        missing_evidence=missing,
        findings=len(findings),
        findings_by_kind=by_kind,
        minutes_to_analysis=_minutes(first_record, checked),
        minutes_to_decision=_minutes(first_record, decided),
        decision=decision.get("action"),
        decision_state=decision.get("state"),
        assessment_agreed=decision.get("assessmentAgreed"),
        disagreement_reason=decision.get("disagreementReason"),
    )


def summarise(rows: list[PilotFile], include_demo: bool) -> PilotReport:
    """Count and time the files. Kept apart from the reads so it can be tested on its own."""
    demo_files = sum(1 for r in rows if r.demo)
    counted = rows if include_demo else [r for r in rows if not r.demo]

    def tally(values: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for value in values:
            out[value] = out.get(value, 0) + 1
        return out

    to_analysis = [r.minutes_to_analysis for r in counted if r.minutes_to_analysis is not None]
    to_decision = [r.minutes_to_decision for r in counted if r.minutes_to_decision is not None]
    answered = [r for r in counted if r.decision and r.assessment_agreed is not None]
    agreed = sum(1 for r in answered if r.assessment_agreed)
    checked = [r for r in counted if r.outcome]
    missing = tally([kind.value for r in checked for kind in r.missing_evidence])
    return PilotReport(
        include_demo=include_demo,
        files=len(counted),
        demo_files=demo_files,
        by_status=tally([r.status or "draft" for r in counted]),
        by_outcome=tally([r.outcome or "not_checked" for r in counted]),
        by_origin=tally([r.origin for r in counted]),
        median_minutes_to_analysis=_median(to_analysis),
        timed_to_analysis=len(to_analysis),
        median_minutes_to_decision=_median(to_decision),
        timed_to_decision=len(to_decision),
        findings_by_kind={
            kind: sum(r.findings_by_kind.get(kind, 0) for r in counted) for kind in FINDING_KINDS
        },
        files_with_fraud_signal=sum(1 for r in counted if r.findings_by_kind.get("fraud_signal")),
        decided=sum(1 for r in counted if r.decision),
        agreed=agreed,
        disagreed=len(answered) - agreed,
        agreed_pct=round(100 * agreed / len(answered)) if answered else None,
        checked_files=len(checked),
        missing_evidence=[
            MissingCount(type=EvidenceType(kind), files=n)
            for kind, n in sorted(missing.items(), key=lambda item: (-item[1], item[0]))
        ],
        rows=counted,
    )


async def pilot_report(db: firestore.AsyncClient, user: User, include_demo: bool) -> PilotReport:
    """The report over the files this officer holds, newest first."""
    query = (
        db.collection("applications")
        .where(filter=FieldFilter("officerUid", "==", user.uid))
        .limit(MAX_FILES)
    )
    snapshots = [s async for s in query.stream()]
    snapshots.sort(
        key=lambda s: (
            _when((s.to_dict() or {}).get("createdAt")) or datetime.min.replace(tzinfo=UTC)
        ),
        reverse=True,
    )
    rows = await asyncio.gather(*(_file(db, s) for s in snapshots))
    return summarise(list(rows), include_demo)


@router.get("", response_model=PilotReport)
async def get_pilot(user: CurrentUser, db: Db, include_demo: IncludeDemo = True) -> PilotReport:
    return await pilot_report(db, user, include_demo)


AGREEMENT = {True: "agrees", False: "disagrees", None: ""}


def to_csv(report: PilotReport) -> str:
    """The dashboard's table: one row per file, with the figures behind every count."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "File number",
            "Business",
            "Demo copy",
            "Started by",
            "Status",
            "Outcome",
            "Records",
            "Records missing",
            "Findings",
            *(f"Findings: {kind.replace('_', ' ')}" for kind in FINDING_KINDS),
            "Minutes from first record to checked file",
            "Minutes from first record to decision",
            "Decision",
            "Officer and LedgerLens",
            "Why the officer disagrees",
        ]
    )
    for r in report.rows:
        writer.writerow(
            [
                _cell(v)
                for v in (
                    r.file_number,
                    r.alias,
                    r.demo,
                    "owner" if r.origin == "owner" else "officer",
                    (r.status or "").replace("_", " "),
                    (r.outcome or "not checked").replace("_", " "),
                    r.evidence_count,
                    "; ".join(kind.value.replace("_", " ") for kind in r.missing_evidence),
                    r.findings,
                    *(r.findings_by_kind.get(kind, 0) for kind in FINDING_KINDS),
                    r.minutes_to_analysis,
                    r.minutes_to_decision,
                    (r.decision or "").replace("_", " "),
                    AGREEMENT[r.assessment_agreed] if r.decision else "",
                    r.disagreement_reason,
                )
            ]
        )
    return out.getvalue()


@router.get("/export.csv")
async def export_pilot_csv(user: CurrentUser, db: Db, include_demo: IncludeDemo = True) -> Response:
    report = await pilot_report(db, user, include_demo)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    # The byte-order mark makes Excel read the file as UTF-8.
    return Response(
        "﻿" + to_csv(report),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="ledgerlens-pilot-{stamp}.csv"'},
    )
