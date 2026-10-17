"""The demo story: one browser plays the owner, the officer and the supervisor on one file.

A judge tries LedgerLens alone, but a real file needs three people: the owner who shares it, the
officer who recommends a decision and a second person who signs it off. ``POST /api/demo/story``
copies a finished sample file (its evidence, readings, credit file and owner summary, bundled in
``app/demo_samples`` by ``eval/bundle_demo_samples.py``) into a new file marked ``demo``, owned by
the caller, so no analysis runs and no Gemini quota is spent until the owner's letter.

On a demo file, and only there, the same person may hold every role: ``role_of`` honours the role
the calling app names (``X-LedgerLens-Act-As``) and the sign-off may be claimed by the officer who
recommended it. Demo files are never checked again (``analysis._no_gemini_on_demo``). Each visitor
keeps one demo file per sample: starting the story again replaces it.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore
from pydantic import Field

from app.analysis.pipeline import AnalysisResult
from app.auth import User, current_user
from app.config import get_settings
from app.routers.analysis import MAX_FOLLOW_UP_ROUNDS
from app.routers.applications import OFFICER, OWNER, _audit
from app.schemas import TIER_BY_TYPE, ApplicationStatus, CamelModel, EvidenceType
from app.store import get_firestore
from app.tools.camel import camelize
from app.usage import claim_demo_story

router = APIRouter(prefix="/api/demo", tags=["demo"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

SAMPLES = Path(__file__).resolve().parent.parent / "demo_samples"
SUBCOLLECTIONS = ("evidence", "memo", "owner", "audit", "runs", "lender")


class DemoStoryRequest(CamelModel):
    sample: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9-]+$")


class DemoStoryResponse(CamelModel):
    application_id: str
    sample: str


@lru_cache
def load_sample(slug: str) -> dict[str, Any] | None:
    """A bundled sample: its evidence list and the analysis exactly as it was saved."""
    path = SAMPLES / f"{slug}.json"
    if not path.is_file():
        return None
    sample = json.loads(path.read_text())
    sample["analysis"] = AnalysisResult.model_validate(sample.pop("result"))
    return sample


async def _remove(db: firestore.AsyncClient, application_id: str, uid: str) -> None:
    """Delete a visitor's earlier demo file, with its share and sign-off codes. Never a real one."""
    ref = db.collection("applications").document(application_id)
    snapshot = await ref.get()
    data = snapshot.to_dict() if snapshot.exists else None
    if not data or data.get("demo") is not True or data.get("ownerUid") != uid:
        return
    for name in SUBCOLLECTIONS:
        async for child in ref.collection(name).stream():
            await ref.collection(name).document(child.id).delete()
    if data.get("shareCode"):
        await db.collection("shares").document(data["shareCode"]).delete()
    code = (data.get("decision") or {}).get("signoffCode")
    if code:
        await db.collection("signoffs").document(code).delete()
    await ref.delete()


@router.post("/story", response_model=DemoStoryResponse, status_code=status.HTTP_201_CREATED)
async def start_story(body: DemoStoryRequest, user: CurrentUser, db: Db) -> DemoStoryResponse:
    """Copy a finished sample into a demo file the caller owns, ready for the owner to share."""
    sample = load_sample(body.sample)
    if sample is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There is no sample file with that name.")
    await claim_demo_story(db, user.uid, get_settings())

    mine = db.collection("demoStories").document(user.uid)
    earlier = await mine.get()
    stories = (earlier.to_dict() if earlier.exists else None) or {}
    if stories.get(body.sample):
        await _remove(db, stories[body.sample], user.uid)

    result: AnalysisResult = sample["analysis"]
    application = sample["application"]
    # The same rule a real run uses (analysis._run) for whether the owner has questions to answer.
    needs_answers = any(
        f.follow_up_question and not f.resolved and f.severity in ("medium", "high")
        for f in result.findings
    )
    can_ask = result.round < MAX_FOLLOW_UP_ROUNDS
    new_status = (
        ApplicationStatus.NEEDS_FOLLOW_UP if needs_answers and can_ask else ApplicationStatus.READY
    )

    ref = db.collection("applications").document()
    await ref.set(
        {
            "lenderId": None,
            "officerUid": None,
            "ownerUid": user.uid,
            "origin": OWNER,
            "shareCode": None,
            "demo": True,
            "demoSample": body.sample,
            "business": {
                "alias": application["alias"],
                "type": application["businessType"],
                "city": application["city"],
                "yearsOperating": application["yearsOperating"],
            },
            "request": {
                "amount": application["amount"],
                "tenorMonths": application["tenorMonths"],
            },
            "status": new_status.value,
            "assessment": result.assessment.value,
            "evidenceStrength": result.policy.evidence_strength,
            "flagCount": len(result.findings),
            "consent": {
                "given": True,
                "version": "demo",
                "at": firestore.SERVER_TIMESTAMP,
                "by": OWNER,
            },
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    await _audit(ref, user, "demo_story_started", sample=body.sample)

    for item in sample["evidence"]:
        kind = EvidenceType(item["type"])
        extraction = result.extractions.get(item["id"]) or {}
        # The photos are the public copies the web app serves; the sample was analysed as records
        # taken on an officer's visit, so they keep that label.
        await (
            ref.collection("evidence")
            .document(item["id"])
            .set(
                {
                    "type": kind.value,
                    "tier": TIER_BY_TYPE[kind].value,
                    "storagePath": item["image"],
                    "capturedAt": datetime.fromisoformat(item["capturedAt"]),
                    "gps": None,
                    "quality": None,
                    "label": extraction.get("label"),
                    "extraction": camelize(extraction),
                    "submittedBy": OFFICER,
                }
            )
        )

    # What a real run stores (analysis._run), from the sample's saved analysis.
    stored = result.model_dump(mode="json", by_alias=True, exclude={"extractions", "context"})
    await (
        ref.collection("memo")
        .document("current")
        .set(
            {
                "runId": None,
                "copiedFrom": f"sample:{body.sample}",
                **camelize(stored),
                "generatedAt": firestore.SERVER_TIMESTAMP,
            }
        )
    )
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
    # Kept so the officer can confirm a disputed reading, as on a real file.
    await ref.collection("memo").document("context").set(result.context.model_dump(mode="json"))

    await mine.set({**stories, body.sample: ref.id})
    return DemoStoryResponse(application_id=ref.id, sample=body.sample)
