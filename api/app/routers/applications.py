"""The officer's flow: create an application, record consent, register evidence, decide.

Every change is written to the application's audit log. Officers only ever see their own
applications, and evidence can't be registered until the owner has given consent.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.auth import User, current_user
from app.schemas import (
    TIER_BY_TYPE,
    ApplicationStatus,
    ConsentRequest,
    CreateApplicationRequest,
    CreateApplicationResponse,
    DecisionAction,
    DecisionRequest,
    RegisterEvidenceRequest,
    RegisterEvidenceResponse,
)
from app.store import get_firestore

router = APIRouter(prefix="/api/applications", tags=["applications"])

DEMO_LENDER_ID = "demo-lender"

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]


async def _owned_application(db: firestore.AsyncClient, application_id: str, user: User):
    """Return the application's reference and data, or 404 if it doesn't exist or isn't theirs."""
    ref = db.collection("applications").document(application_id)
    snapshot = await ref.get()
    data = snapshot.to_dict() if snapshot.exists else None
    if not data or data.get("officerUid") != user.uid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return ref, data


async def _audit(ref, user: User, action: str, reason: str | None = None, **details: Any) -> None:
    await (
        ref.collection("audit")
        .document()
        .set(
            {
                "actor": user.uid,
                "action": action,
                "reason": reason,
                "details": details,
                "at": firestore.SERVER_TIMESTAMP,
            }
        )
    )


@router.post("", response_model=CreateApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    body: CreateApplicationRequest, user: CurrentUser, db: Db
) -> CreateApplicationResponse:
    ref = db.collection("applications").document()
    await ref.set(
        {
            "lenderId": DEMO_LENDER_ID,
            "officerUid": user.uid,
            "business": {
                "alias": body.alias,
                "type": body.business_type,
                "city": body.city,
                "yearsOperating": body.years_operating,
            },
            "request": {"amount": body.amount, "tenorMonths": body.tenor_months},
            "status": ApplicationStatus.DRAFT.value,
            "assessment": None,
            "consent": None,
            "sharedWith": [DEMO_LENDER_ID],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    await _audit(ref, user, "created")
    return CreateApplicationResponse(application_id=ref.id)


@router.post("/{application_id}/consent", status_code=status.HTTP_204_NO_CONTENT)
async def record_consent(
    application_id: str, body: ConsentRequest, user: CurrentUser, db: Db
) -> None:
    ref, _ = await _owned_application(db, application_id, user)
    new_status = ApplicationStatus.COLLECTING if body.given else ApplicationStatus.DRAFT
    await ref.update(
        {
            "consent": {
                "given": body.given,
                "version": body.consent_version,
                "at": firestore.SERVER_TIMESTAMP,
            },
            "status": new_status.value,
        }
    )
    await _audit(
        ref,
        user,
        "consent_given" if body.given else "consent_withdrawn",
        version=body.consent_version,
    )


@router.post(
    "/{application_id}/evidence",
    response_model=RegisterEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_evidence(
    application_id: str, body: RegisterEvidenceRequest, user: CurrentUser, db: Db
) -> RegisterEvidenceResponse:
    ref, data = await _owned_application(db, application_id, user)
    if not (data.get("consent") or {}).get("given"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Record the owner's consent first")
    expected_prefix = f"evidence/{application_id}/"
    if not body.storage_path.startswith(expected_prefix):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Evidence files must be stored under {expected_prefix}",
        )
    evidence_ref = ref.collection("evidence").document()
    await evidence_ref.set(
        {
            "type": body.type.value,
            "tier": TIER_BY_TYPE[body.type].value,
            "storagePath": body.storage_path,
            "capturedAt": body.captured_at,
            "gps": body.gps.model_dump() if body.gps else None,
            "quality": None,
            "extraction": None,
        }
    )
    await _audit(ref, user, "evidence_added", type=body.type.value, evidenceId=evidence_ref.id)
    return RegisterEvidenceResponse(evidence_id=evidence_ref.id)


@router.post("/{application_id}/decision", status_code=status.HTTP_204_NO_CONTENT)
async def record_decision(
    application_id: str, body: DecisionRequest, user: CurrentUser, db: Db
) -> None:
    ref, data = await _owned_application(db, application_id, user)
    decidable = (
        ApplicationStatus.READY,
        ApplicationStatus.NEEDS_FOLLOW_UP,
        ApplicationStatus.IN_REVIEW,
    )
    if data.get("status") not in {s.value for s in decidable}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only analysed applications can be decided")
    new_status = (
        ApplicationStatus.COLLECTING
        if body.action is DecisionAction.REQUEST_MORE
        else ApplicationStatus.DECIDED
    )
    await ref.update(
        {
            "status": new_status.value,
            "decision": {
                "action": body.action.value,
                "reason": body.reason,
                "by": user.uid,
                "at": firestore.SERVER_TIMESTAMP,
            },
        }
    )
    await _audit(ref, user, f"decision_{body.action.value}", reason=body.reason)
