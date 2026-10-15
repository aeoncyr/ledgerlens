"""Run the analysis on an application's evidence and store the credit file.

The web app calls this route on the Cloud Run URL directly, not through Firebase Hosting, because
an analysis takes a minute or two and Hosting cuts requests off at 60 seconds. The work happens
inside the request (Cloud Run bills by request, so there is no CPU after the response); every step
is written to the run's Firestore document as it happens, and the officer's screen listens to it.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.analysis.evidence_store import CloudStorageStore, EvidenceStore
from app.analysis.pipeline import Application, EvidenceItem, run_pipeline
from app.auth import User, current_user
from app.config import get_settings
from app.gemini import Gemini, get_gemini
from app.routers.applications import _audit, _owned_application
from app.schemas import AnalyzeResponse, ApplicationStatus, EvidenceType
from app.store import get_firestore

router = APIRouter(prefix="/api/applications", tags=["analysis"])

STALE_RUN_SECONDS = 15 * 60  # a run older than this is treated as dead, so it can be restarted


@lru_cache
def get_evidence_store() -> EvidenceStore:
    bucket = get_settings().storage_bucket
    if not bucket:
        raise RuntimeError("STORAGE_BUCKET is not set")
    return CloudStorageStore(bucket)


def _application(data: dict[str, Any]) -> Application:
    business, request = data["business"], data["request"]
    return Application(
        alias=business["alias"],
        business_type=business["type"],
        city=business["city"],
        years_operating=business["yearsOperating"],
        amount=request["amount"],
        tenor_months=request["tenorMonths"],
    )


def _is_running(data: dict[str, Any]) -> bool:
    started = data.get("analysisStartedAt")
    return (
        data.get("status") == ApplicationStatus.ANALYZING.value
        and isinstance(started, datetime)
        and (datetime.now(UTC) - started).total_seconds() < STALE_RUN_SECONDS
    )


@router.post("/{application_id}/analyze", response_model=AnalyzeResponse)
async def analyze(
    application_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[firestore.AsyncClient, Depends(get_firestore)],
    gemini: Annotated[Gemini, Depends(get_gemini)],
    store: Annotated[EvidenceStore, Depends(get_evidence_store)],
) -> AnalyzeResponse:
    ref, data = await _owned_application(db, application_id, user)
    if not (data.get("consent") or {}).get("given"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Record the owner's consent first")
    if _is_running(data):
        raise HTTPException(status.HTTP_409_CONFLICT, "An analysis is already running")

    items = []
    async for snapshot in ref.collection("evidence").stream():
        evidence = snapshot.to_dict()
        items.append(
            EvidenceItem(
                id=snapshot.id,
                type=EvidenceType(evidence["type"]),
                storage_path=evidence["storagePath"],
                captured_at=evidence["capturedAt"],
            )
        )
    if not items:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add some evidence first")

    started = time.monotonic()
    now = datetime.now(UTC)
    run_ref = ref.collection("runs").document()
    steps: list[dict[str, Any]] = []
    lock = asyncio.Lock()
    await run_ref.set({"state": "running", "startedAt": now, "steps": [], "by": user.uid})
    await ref.update(
        {
            "status": ApplicationStatus.ANALYZING.value,
            "currentRunId": run_ref.id,
            "analysisStartedAt": now,
        }
    )

    async def progress(agent: str, message: str, state: str) -> None:
        async with lock:
            steps.append(
                {"agent": agent, "message": message, "state": state, "at": datetime.now(UTC)}
            )
            await run_ref.update({"steps": list(steps)})

    try:
        result = await run_pipeline(
            gemini=gemini,
            store=store,
            application=_application(data),
            items=items,
            progress=progress,
        )
    except Exception as exc:
        await run_ref.update(
            {"state": "failed", "error": str(exc), "finishedAt": datetime.now(UTC)}
        )
        await ref.update({"status": ApplicationStatus.COLLECTING.value})
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The analysis failed; try again") from exc

    for evidence_id, extraction in result.extractions.items():
        await (
            ref.collection("evidence")
            .document(evidence_id)
            .update({"label": extraction.get("label"), "extraction": extraction})
        )
    needs_answers = any(
        f.follow_up_question and not f.resolved and f.severity in ("medium", "high")
        for f in result.findings
    )
    new_status = ApplicationStatus.NEEDS_FOLLOW_UP if needs_answers else ApplicationStatus.READY
    await (
        ref.collection("memo")
        .document("current")
        .set(
            {
                "runId": run_ref.id,
                **result.model_dump(mode="json", by_alias=True, exclude={"extractions"}),
                "generatedAt": firestore.SERVER_TIMESTAMP,
            }
        )
    )
    await ref.update(
        {
            "status": new_status.value,
            "assessment": result.assessment.value,
            "evidenceStrength": result.policy.evidence_strength,
            "flagCount": len(result.findings),
        }
    )
    latency_ms = round((time.monotonic() - started) * 1000)
    await run_ref.update(
        {
            "state": "done",
            "finishedAt": datetime.now(UTC),
            "latencyMs": latency_ms,
            "models": result.models,
        }
    )
    await _audit(
        ref, user, "analysis_completed", assessment=result.assessment.value, runId=run_ref.id
    )
    return AnalyzeResponse(
        run_id=run_ref.id, assessment=result.assessment, status=new_status, latency_ms=latency_ms
    )
