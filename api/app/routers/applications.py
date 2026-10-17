"""Applications: created by an officer, or by a business owner who later shares them with a lender.

A file has up to three people on it. The officer (the lender's) recommends a decision; the owner
(the business's) can start the file, consent, add evidence and share it with one lender at a time;
a reviewer, a second person at the lender, signs off an approval or a decline (see
``decisions.py``). Each route says which of them may call it. Every change is written to the
application's audit log, and evidence can't be registered until consent is recorded.
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
    RegisterEvidenceRequest,
    RegisterEvidenceResponse,
)
from app.store import get_firestore

router = APIRouter(prefix="/api/applications", tags=["applications"])

DEMO_LENDER_ID = "demo-lender"

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]


OFFICER, OWNER, REVIEWER = "officer", "owner", "reviewer"
EITHER = (OFFICER, OWNER)


def role_of(data: dict[str, Any], user: User) -> str | None:
    """Whether the user is this file's officer, its owner or its reviewer (in that order)."""
    if data.get("officerUid") == user.uid:
        return OFFICER
    if data.get("ownerUid") == user.uid:
        return OWNER
    if data.get("reviewerUid") == user.uid:
        return REVIEWER
    return None


async def _owned_application(
    db: firestore.AsyncClient,
    application_id: str,
    user: User,
    roles: tuple[str, ...] = (OFFICER,),
):
    """Return the application's reference and data, or 404 if the user has no allowed role on it."""
    ref = db.collection("applications").document(application_id)
    snapshot = await ref.get()
    data = snapshot.to_dict() if snapshot.exists else None
    if not data or role_of(data, user) not in roles:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "We can't find this file. The link may be wrong, or it was removed.",
        )
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
            "ownerUid": None,
            "origin": OFFICER,
            "shareCode": None,
            "business": {
                "alias": body.alias,
                "type": body.business_type,
                "city": body.city,
                "yearsOperating": body.years_operating,
            },
            "request": {
                "amount": body.amount,
                "tenorMonths": body.tenor_months,
                "existingMonthlyDebt": body.existing_monthly_debt,
            },
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
    ref, data = await _owned_application(db, application_id, user, EITHER)
    new_status = ApplicationStatus.COLLECTING if body.given else ApplicationStatus.DRAFT
    await ref.update(
        {
            "consent": {
                "given": body.given,
                "version": body.consent_version,
                "at": firestore.SERVER_TIMESTAMP,
                "by": role_of(data, user),
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
    ref, data = await _owned_application(db, application_id, user, EITHER)
    if not (data.get("consent") or {}).get("given"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Record the owner's consent first")
    # The browser uploads into its own folder; Storage rules check that folder against the user's
    # ID, and this check ties it to an application the user owns.
    expected_prefix = f"evidence/{application_id}/{user.uid}/"
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
            # A photo an officer takes on a visit is harder to fake than one the owner sends.
            "submittedBy": role_of(data, user),
        }
    )
    await _audit(ref, user, "evidence_added", type=body.type.value, evidenceId=evidence_ref.id)
    return RegisterEvidenceResponse(evidence_id=evidence_ref.id)
