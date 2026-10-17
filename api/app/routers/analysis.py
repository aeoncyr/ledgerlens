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

from app.agents.interview_listener import transcribe_answer
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
from app.routers.applications import EITHER, OFFICER, _audit, _owned_application, role_of
from app.schemas import (
    AnalyzeResponse,
    ApplicationStatus,
    ConfirmReadingRequest,
    ConfirmReadingResponse,
    EvidenceType,
    FollowUpAnswerRequest,
)
from app.store import get_firestore
from app.tools.camel import camelize
from app.usage import claim_run

router = APIRouter(prefix="/api/applications", tags=["analysis"])

STALE_RUN_SECONDS = 15 * 60  # a run older than this is treated as dead, so it can be restarted
MAX_FOLLOW_UP_ROUNDS = 2  # the owner is asked at most twice; after that, more evidence is needed
DECLINED = "(prefers not to answer)"  # shown where an answer would be
OWNER_DECLINED = "The owner preferred not to answer this question."  # what the verifier reads


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
        existing_monthly_debt=request.get("existingMonthlyDebt") or 0,
    )


def _check_not_settled(data: dict[str, Any]) -> None:
    """A file waiting for sign-off, or one with a loan on offer, is not checked again: the
    decision rests on the file as it was. After a decline the owner may build the file up again."""
    status_now = data.get("status")
    offered = (
        status_now == ApplicationStatus.DECIDED.value
        and (data.get("decision") or {}).get("action") == "approve"
    )
    if status_now == ApplicationStatus.AWAITING_SIGNOFF.value or offered:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The lender's decision rests on the file as it is, so it can't be checked again now.",
        )


def _no_gemini_on_demo(data: dict[str, Any]) -> None:
    """A demo file is a copy of a finished sample (``routers/demo.py``) and is never read again,
    so playing the story spends no Gemini quota."""
    if data.get("demo") is True:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This is a demo copy of a finished sample file, so it isn't checked again and no "
            "Gemini quota is used. Typed answers are saved; to watch a real check, start your own "
            "file.",
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
    ref, data = await _owned_application(db, application_id, user, EITHER)
    if not (data.get("consent") or {}).get("given"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Record the owner's consent first")
    _no_gemini_on_demo(data)
    _check_not_settled(data)
    if _is_running(data):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A check is already running on this file. Wait for it to finish.",
        )

    items = []
    async for snapshot in ref.collection("evidence").stream():
        evidence = snapshot.to_dict()
        items.append(
            EvidenceItem(
                id=snapshot.id,
                type=EvidenceType(evidence["type"]),
                storage_path=evidence["storagePath"],
                captured_at=evidence["capturedAt"],
                submitted_by=evidence.get("submittedBy") or "officer",
            )
        )
    if not items:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add at least one record before checking.")

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
    gemini: Annotated[Gemini, Depends(get_gemini)],
    store: Annotated[EvidenceStore, Depends(get_evidence_store)],
) -> None:
    """Record the owner's answer to one question: typed, spoken (Gemini transcribes it), or that
    they prefer not to answer, which is recorded neutrally."""
    ref, data = await _owned_application(db, application_id, user, EITHER)
    memo_ref = ref.collection("memo").document("current")
    snapshot = await memo_ref.get()
    findings = (snapshot.to_dict() or {}).get("findings", []) if snapshot.exists else []
    if not 0 <= index < len(findings) or not findings[index].get("followUpQuestion"):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "We can't find that question. Refresh the page to see the current ones.",
        )
    question = findings[index]["followUpQuestion"]

    answer: dict[str, Any] = {"answerBy": role_of(data, user), "declined": False}
    if body.declined:
        answer.update(answer=DECLINED, answerEn=DECLINED, declined=True)
    elif body.audio_path:
        _no_gemini_on_demo(data)
        if not body.audio_path.startswith(f"evidence/{application_id}/{user.uid}/"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Recordings must be in your own folder"
            )
        audio, mime_type = await store.read(body.audio_path)
        spoken, _ = await transcribe_answer(gemini, audio, mime_type, question)
        if not spoken.audible:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "We couldn't make out the recording. Try again somewhere quieter, "
                "or type the answer.",
            )
        answer.update(
            answer=spoken.transcript, answerEn=spoken.transcript_en, answerAudio=body.audio_path
        )
    else:
        answer.update(answer=(body.text or "").strip(), answerEn=None)

    findings[index] = {**findings[index], **answer}
    await memo_ref.update({"findings": findings})
    owner_ref = ref.collection("owner").document("summary")
    owner_summary = await owner_ref.get()
    if owner_summary.exists:
        questions = [
            {**q, "answer": answer["answer"], "declined": answer["declined"]}
            if q.get("index") == index
            else q
            for q in (owner_summary.to_dict() or {}).get("questions", [])
        ]
        await owner_ref.update({"questions": questions})
    await _audit(
        ref,
        user,
        "follow_up_declined" if body.declined else "follow_up_answered",
        question=question,
        spoken=bool(body.audio_path),
    )


@router.post(
    "/{application_id}/evidence/{evidence_id}/confirm", response_model=ConfirmReadingResponse
)
async def confirm_reading(
    application_id: str,
    evidence_id: str,
    body: ConfirmReadingRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[firestore.AsyncClient, Depends(get_firestore)],
) -> ConfirmReadingResponse:
    """The officer settles a line where the two readings of a notebook page disagree."""
    ref, _ = await _owned_application(db, application_id, user, (OFFICER,))
    context_ref = ref.collection("memo").document("context")
    saved = await context_ref.get()
    if not saved.exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Check the evidence first.")
    context = Context.model_validate(saved.to_dict())
    extraction = context.extractions.get(evidence_id) or {}
    disputed = {d["line"] for d in extraction.get("disagreements", [])}
    if body.line not in disputed:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Both readings of that line already agree, so there is nothing to confirm.",
        )

    confirmed = {k: dict(v) for k, v in context.confirmed.items()}
    confirmed.setdefault(evidence_id, {})[str(body.line)] = body.amount_rp
    lines = [
        {**line, "amountRp": body.amount_rp, "confidence": 1.0, "confirmedByOfficer": True}
        if line.get("line") == body.line
        else line
        for line in extraction.get("lines", [])
    ]
    extractions = {**context.extractions, evidence_id: {**extraction, "lines": lines}}
    context = context.model_copy(
        update={"confirmed": confirmed, "extractions": extractions, "pending_confirmations": True}
    )
    await context_ref.set(context.model_dump(mode="json"))
    await (
        ref.collection("evidence")
        .document(evidence_id)
        .update({"extraction": camelize(extractions[evidence_id])})
    )
    await _audit(
        ref,
        user,
        "reading_confirmed",
        evidenceId=evidence_id,
        line=body.line,
        amount=body.amount_rp,
    )
    pending = sum(
        1
        for ev, ex in context.extractions.items()
        for d in ex.get("disagreements", [])
        if str(d["line"]) not in context.confirmed.get(ev, {})
    )
    return ConfirmReadingResponse(pending=pending)


@router.post("/{application_id}/reverify", response_model=AnalyzeResponse)
async def reverify(
    application_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[firestore.AsyncClient, Depends(get_firestore)],
    gemini: Annotated[Gemini, Depends(get_gemini)],
) -> AnalyzeResponse:
    """Check the file again with the owner's answers, without reading the evidence again."""
    ref, data = await _owned_application(db, application_id, user, EITHER)
    _no_gemini_on_demo(data)
    _check_not_settled(data)
    if _is_running(data):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A check is already running on this file. Wait for it to finish.",
        )
    memo = await ref.collection("memo").document("current").get()
    saved = await ref.collection("memo").document("context").get()
    if not (memo.exists and saved.exists):
        raise HTTPException(status.HTTP_409_CONFLICT, "Check the evidence first.")
    context = Context.model_validate(saved.to_dict())
    answers = [
        {
            "finding": f["text"],
            "question": f["followUpQuestion"],
            "answer": OWNER_DECLINED if f.get("declined") else f["answer"],
        }
        for f in (memo.to_dict() or {}).get("findings", [])
        if f.get("answer") and f.get("followUpQuestion")
    ]
    new_answers = [a for a in answers if a["question"] not in context.answered]
    if not new_answers and not context.pending_confirmations:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Record one of the owner's answers or confirm a disputed reading first",
        )
    if new_answers and context.round >= MAX_FOLLOW_UP_ROUNDS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The owner has already answered two rounds of questions. Ask for more records instead.",
        )
    await claim_run(db, user.uid, get_settings())
    context = context.model_copy(
        update={
            # A new round only when the owner answered something new; confirming a reading is
            # the officer's own check and does not use up one of the owner's two rounds.
            "round": context.round + (1 if new_answers else 0),
            "answered": [a["question"] for a in answers],
            "pending_confirmations": False,
        }
    )
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

    async def progress(
        agent: str, message: str, state: str, detail: dict[str, Any] | None = None
    ) -> None:
        async with lock:
            step = {"agent": agent, "message": message, "state": state, "at": datetime.now(UTC)}
            if detail:
                step["detail"] = camelize(detail)
            steps.append(step)
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
                "Gemini's free daily quota is used up for today. It resets at midnight Pacific "
                "time (early afternoon in Jakarta); the sample files on the home page are always "
                "open.",
            ) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The check stopped partway, usually because Gemini was busy. Nothing is lost: "
            "run it again in a minute.",
        ) from exc

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
    # What the owner may read: the summary written for them and the questions put to them, never
    # the officer's findings, figures or outcome.
    summary = result.memo.get("owner_summary") or {}
    await (
        ref.collection("owner")
        .document("summary")
        .set(
            {
                "status": "needs_answers" if needs_answers and can_ask else "ready",
                "verified": summary.get("verified", ""),
                "missing": summary.get("missing", ""),
                "tips": summary.get("tips", []),
                "verifiedEn": summary.get("verified_en", ""),
                "missingEn": summary.get("missing_en", ""),
                "tipsEn": summary.get("tips_en", []),
                "questions": [
                    {
                        "index": index,
                        "question": f.follow_up_question,
                        "questionEn": f.follow_up_question_en,
                        "answer": f.answer,
                    }
                    for index, f in enumerate(result.findings)
                    if f.follow_up_question and not f.resolved
                ],
                "evidenceCount": len(result.context.evidence_ids),
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )
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
