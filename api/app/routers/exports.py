"""Exports of a credit file for the lender's own systems: structured JSON and a CSV for Excel.

Only the lender's side may export: the officer on the file, or a second reviewer who signed it
off. The owner has their own summary and never receives the officer's findings this way.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from google.cloud import firestore

from app.auth import User, current_user
from app.config import get_settings
from app.schemas import TIER_BY_TYPE, EvidenceType
from app.store import get_firestore

router = APIRouter(prefix="/api/applications", tags=["exports"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

FORMAT = "ledgerlens.credit-file/v1"
LENDER_ROLES = ("officerUid", "reviewerUid")


def _plain(value: Any) -> Any:
    """Firestore values as JSON: timestamps become ISO strings, server sentinels disappear."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return None


async def _get(ref) -> dict[str, Any] | None:
    snapshot = await ref.get()
    return snapshot.to_dict() if snapshot.exists else None


async def credit_file(db: firestore.AsyncClient, application_id: str, user: User) -> dict:
    """Gather the file for the lender who may see it, or 404 for anyone else."""
    ref = db.collection("applications").document(application_id)
    data = await _get(ref)
    if not data or user.uid not in {data.get(role) for role in LENDER_ROLES}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    memo = await _get(ref.collection("memo").document("current"))
    if not memo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Run the analysis first")
    owner_decision = await _get(ref.collection("owner").document("decision"))

    evidence = {}
    async for snapshot in ref.collection("evidence").stream():
        item = snapshot.to_dict() or {}
        kind = item.get("type")
        evidence[snapshot.id] = {
            "id": snapshot.id,
            "type": kind,
            "tier": item.get("tier")
            or (TIER_BY_TYPE[EvidenceType(kind)].value if kind in EvidenceType else None),
            "label": item.get("label"),
            "submittedBy": item.get("submittedBy"),
        }

    def cite(citations: list[dict]) -> list[dict]:
        return [
            {
                "evidenceId": c.get("evidenceId"),
                "evidenceLabel": (evidence.get(c.get("evidenceId")) or {}).get("label"),
                "locator": c.get("locator"),
            }
            for c in citations or []
        ]

    memo_text = memo.get("memo") or {}
    business = data.get("business") or {}
    request = data.get("request") or {}
    return _plain(
        {
            "format": FORMAT,
            "exportedAt": datetime.now().astimezone().isoformat(),
            "applicationId": application_id,
            "fileNumber": f"LL-{application_id[:8].upper()}",
            "link": f"{get_settings().public_app_url.rstrip('/')}/app/{application_id}",
            "business": {
                "alias": business.get("alias"),
                "type": business.get("type"),
                "city": business.get("city"),
                "yearsOperating": business.get("yearsOperating"),
            },
            "request": {
                "amountRp": request.get("amount"),
                "tenorMonths": request.get("tenorMonths"),
            },
            "status": data.get("status"),
            "assessment": memo.get("assessment"),
            "cashflow": memo.get("cashflow"),
            "policy": memo.get("policy"),
            "findings": [
                {
                    "kind": f.get("kind"),
                    "severity": f.get("severity"),
                    "text": f.get("text"),
                    "source": f.get("source"),
                    "resolved": f.get("resolved", False),
                    "followUpQuestion": f.get("followUpQuestion"),
                    "answer": f.get("answer"),
                    "citations": cite(f.get("citations")),
                }
                for f in memo.get("findings") or []
            ],
            "confirmations": [
                {"text": c.get("text"), "citations": cite(c.get("citations"))}
                for c in memo.get("confirmations") or []
            ],
            "memo": {
                "headline": memo_text.get("headline"),
                **{
                    key: {
                        "text": (memo_text.get(key) or {}).get("text"),
                        "citations": cite((memo_text.get(key) or {}).get("citations")),
                    }
                    for key in ("character", "capacity", "capital", "collateral", "conditions")
                },
                "officerNextSteps": memo_text.get("officerNextSteps", []),
            },
            "figures": [
                {k: fact.get(k) for k in ("key", "label", "kind", "value", "display", "sources")}
                for fact in memo.get("facts") or []
            ],
            "evidence": list(evidence.values()),
            "decision": data.get("decision"),
            "ownerDecision": owner_decision,
            "models": memo.get("models", []),
        }
    )


@router.get("/{application_id}/export.json")
async def export_json(application_id: str, user: CurrentUser, db: Db) -> Response:
    exported = await credit_file(db, application_id, user)
    return Response(
        json.dumps(exported, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{exported["fileNumber"]}.json"'},
    )


def _cell(value: Any) -> Any:
    """Quote text that starts like a formula, so Excel and Sheets show it rather than run it."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    if isinstance(value, bool):
        return "yes" if value else "no"
    return "" if value is None else value


def to_csv(f: dict[str, Any]) -> str:
    """One summary row, a blank line, then one row per finding with its citations."""
    policy = f.get("policy") or {}
    cashflow = f.get("cashflow") or {}
    decision = f.get("decision") or {}
    offer = (f.get("ownerDecision") or {}).get("offer") or (decision.get("offer") or {})
    summary = {
        "File number": f["fileNumber"],
        "Business": f["business"]["alias"],
        "Type": f["business"]["type"],
        "City": f["business"]["city"],
        "Years trading": f["business"]["yearsOperating"],
        "Amount requested (Rp)": f["request"]["amountRp"],
        "Tenor requested (months)": f["request"]["tenorMonths"],
        "Outcome": (f.get("assessment") or "").replace("_", " "),
        "Evidence strength (of 100)": policy.get("evidenceStrength"),
        "Monthly revenue proven by QRIS (Rp)": cashflow.get("revenueLow"),
        "Monthly revenue claimed in notebook (Rp)": cashflow.get("revenueHigh"),
        "Largest instalment the policy allows (Rp)": policy.get("maxInstallment"),
        "Instalment requested (Rp)": policy.get("requestedInstallment"),
        "Within policy": policy.get("withinPolicy"),
        "Findings": len(f["findings"]),
        "Decision": (decision.get("action") or "").replace("_", " "),
        "Decision reason": decision.get("reason"),
        "Offer amount (Rp)": offer.get("amountRp"),
        "Offer tenor (months)": offer.get("tenorMonths"),
        "Offer instalment (Rp)": offer.get("instalmentRp"),
        "Exported at": f["exportedAt"],
        "Link": f["link"],
    }
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(summary.keys())
    writer.writerow([_cell(v) for v in summary.values()])
    writer.writerow([])
    writer.writerow(["#", "Severity", "Kind", "Finding", "Evidence cited", "Explained", "Answer"])
    for index, finding in enumerate(f["findings"], start=1):
        cited = "; ".join(
            f"{c.get('evidenceLabel') or c.get('evidenceId')}, {c.get('locator')}"
            for c in finding["citations"]
        )
        writer.writerow(
            [
                _cell(v)
                for v in (
                    index,
                    finding["severity"],
                    (finding["kind"] or "").replace("_", " "),
                    finding["text"],
                    cited,
                    finding["resolved"],
                    finding["answer"],
                )
            ]
        )
    return out.getvalue()


@router.get("/{application_id}/export.csv")
async def export_csv(application_id: str, user: CurrentUser, db: Db) -> Response:
    exported = await credit_file(db, application_id, user)
    # The byte-order mark makes Excel read the file as UTF-8.
    return Response(
        "﻿" + to_csv(exported),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{exported["fileNumber"]}.csv"'},
    )
