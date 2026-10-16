"""Run the analysis on an application's evidence and store the credit file.

The web app calls this route on the Cloud Run URL directly, not through Firebase Hosting, because
an analysis takes a minute or two and Hosting cuts requests off at 60 seconds. The work happens
inside the request (Cloud Run bills by request, so there is no CPU after the response); every step
is written to the run's Firestore document as it happens, and the officer's screen listens to it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.analysis.evidence_store import CloudStorageStore, EvidenceStore
from app.analysis.pipeline import (
    AnalysisResult,
    Application,
    Context,
    EvidenceItem,
    Progress,
    judge,
    run_pipeline,
)
from app.auth import User, current_user
from app.config import get_settings
from app.gemini import Gemini, GeminiQuotaExhausted, get_gemini
from app.routers.applications import _audit, _owned_application
from app.schemas import AnalyzeResponse, ApplicationStatus, EvidenceType, FollowUpAnswerRequest
from app.store import get_firestore
from app.tools.camel import camelize
from app.usage import claim_run

router = APIRouter(prefix="/api/applications", tags=["analysis"])

STALE_RUN_SECONDS = 15 * 60  # a run older than this is treated as dead, so it can be restarted
MAX_FOLLOW_UP_ROUNDS = 2  # the owner is asked at most twice; after that, more evidence is needed


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

    settings = get_settings()
    await claim_run(db, user.uid, settings)
    return await _run(
        ref,
        user,
        lambda progress: run_pipeline(
            gemini=gemini,
            store=store,
            application=_application(data),
            items=items,
            progress=progress,
            max_parallel=settings.max_parallel_calls,
            double_read=settings.ledger_double_read,
        ),
        failed_status=ApplicationStatus.COLLECTING,
        action="analysis_completed",
    )


@router.post("/{application_id}/findings/{index}/answer", status_code=status.HTTP_204_NO_CONTENT)
async def answer_follow_up(
    application_id: str,
    index: int,
    body: FollowUpAnswerRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[firestore.AsyncClient, Depends(get_firestore)],
) -> None:
    """Record the owner's answer to one follow-up question, as the officer heard it."""
    ref, _ = await _owned_application(db, application_id, user)
    if not body.text:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Type the owner's answer; voice notes come later"
        )
    memo_ref = ref.collection("memo").document("current")
    snapshot = await memo_ref.get()
    findings = (snapshot.to_dict() or {}).get("findings", []) if snapshot.exists else []
    if not 0 <= index < len(findings) or not findings[index].get("followUpQuestion"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There is no such question")
    findings[index] = {**findings[index], "answer": body.text.strip()}
    await memo_ref.update({"findings": findings})
    await _audit(ref, user, "follow_up_answered", question=findings[index]["followUpQuestion"])


@router.post("/{application_id}/reverify", response_model=AnalyzeResponse)
async def reverify(
    application_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[firestore.AsyncClient, Depends(get_firestore)],
    gemini: Annotated[Gemini, Depends(get_gemini)],
) -> AnalyzeResponse:
    """Check the file again with the owner's answers, without reading the evidence again."""
    ref, data = await _owned_application(db, application_id, user)
    if _is_running(data):
        raise HTTPException(status.HTTP_409_CONFLICT, "An analysis is already running")
    memo = await ref.collection("memo").document("current").get()
    saved = await ref.collection("memo").document("context").get()
    if not (memo.exists and saved.exists):
        raise HTTPException(status.HTTP_409_CONFLICT, "Run the analysis first")
    context = Context.model_validate(saved.to_dict())
    if context.round >= MAX_FOLLOW_UP_ROUNDS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The owner has been asked twice; collect more evidence instead",
        )
    answers = [
        {"finding": f["text"], "question": f["followUpQuestion"], "answer": f["answer"]}
        for f in (memo.to_dict() or {}).get("findings", [])
        if f.get("answer") and f.get("followUpQuestion")
    ]
    if not answers:
        raise HTTPException(status.HTTP_409_CONFLICT, "Record at least one of the owner's answers")
    await claim_run(db, user.uid, get_settings())
    context = context.model_copy(update={"round": context.round + 1})
    return await _run(
        ref,
        user,
        lambda progress: judge(gemini=gemini, context=context, progress=progress, answers=answers),
        failed_status=ApplicationStatus(data.get("status", "needs_follow_up")),
        action="reverified_with_answers",
    )


async def _run(
    ref: Any,
    user: User,
    work: Callable[[Progress], Awaitable[AnalysisResult]],
    *,
    failed_status: ApplicationStatus,
    action: str,
) -> AnalyzeResponse:
    """Run analysis work inside this request, streaming its steps to Firestore, then store it."""
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
        result = await work(progress)
    except Exception as exc:
        await run_ref.update(
            {"state": "failed", "error": str(exc), "finishedAt": datetime.now(UTC)}
        )
        await ref.update({"status": failed_status.value})
        if isinstance(exc, GeminiQuotaExhausted):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Gemini's free daily quota is used up for today. It resets at 07:00 UTC; the "
                "sample files on the home page show finished analyses meanwhile.",
            ) from exc
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The analysis failed; try again") from exc

    for evidence_id, extraction in result.extractions.items():
        await (
            ref.collection("evidence")
            .document(evidence_id)
            .update({"label": extraction.get("label"), "extraction": camelize(extraction)})
        )
    needs_answers = any(
        f.follow_up_question and not f.resolved and f.severity in ("medium", "high")
        for f in result.findings
    )
    can_ask = result.round < MAX_FOLLOW_UP_ROUNDS
    new_status = (
        ApplicationStatus.NEEDS_FOLLOW_UP if needs_answers and can_ask else ApplicationStatus.READY
    )
    stored = result.model_dump(mode="json", by_alias=True, exclude={"extractions", "context"})
    await (
        ref.collection("memo")
        .document("current")
        .set({"runId": run_ref.id, **camelize(stored), "generatedAt": firestore.SERVER_TIMESTAMP})
    )
    # Kept as the pipeline wrote it, for re-checking with the owner's answers.
    await ref.collection("memo").document("context").set(result.context.model_dump(mode="json"))
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
    await _audit(ref, user, action, assessment=result.assessment.value, runId=run_ref.id)
    return AnalyzeResponse(
        run_id=run_ref.id, assessment=result.assessment, status=new_status, latency_ms=latency_ms
    )
