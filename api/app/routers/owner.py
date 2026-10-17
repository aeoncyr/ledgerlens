"""The business owner's side: start a file, share it with a lender, withdraw it, delete it.

An owner can build their own credit file and then give a lender access with a share code, which the
officer opens as a link. The file stays the owner's: they can withdraw the lender's access at any
time, and only one lender has it at once. There is no lender directory or matching; the owner
decides who to show it to, as they would show a printed file. The owner can also delete the file
for good, as Indonesia's personal data protection law (UU PDP) lets them, unless a lender is
deciding on it or they have accepted a loan on it.
"""

from __future__ import annotations

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.analysis.evidence_store import EvidenceRemover
from app.auth import User, current_user
from app.routers.analysis import _is_running, get_evidence_store
from app.routers.applications import (
    DEMO_LENDER_ID,
    OFFICER,
    OWNER,
    REVIEWER,
    _audit,
    _owned_application,
    role_of,
)
from app.schemas import (
    ApplicationStatus,
    ClaimResponse,
    CreateApplicationRequest,
    CreateApplicationResponse,
    ShareResponse,
)
from app.store import get_firestore

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["owner"])

LINK_GONE = "This link no longer works. The owner may have stopped sharing; ask them for a new one."

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]


def get_evidence_remover() -> EvidenceRemover:
    """The same Cloud Storage bucket the readers read from."""
    return get_evidence_store()  # a CloudStorageStore, which can also delete


Remover = Annotated[EvidenceRemover, Depends(get_evidence_remover)]

# Easy to read aloud or type from a phone: no 0/O, 1/I/L.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def new_share_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


@router.post(
    "/owner/files", response_model=CreateApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def create_owner_file(
    body: CreateApplicationRequest, user: CurrentUser, db: Db
) -> CreateApplicationResponse:
    """An owner starts their own file. No lender sees it until the owner shares it."""
    ref = db.collection("applications").document()
    await ref.set(
        {
            "lenderId": None,
            "officerUid": None,
            "ownerUid": user.uid,
            "origin": OWNER,
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
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    await _audit(ref, user, "created_by_owner")
    return CreateApplicationResponse(application_id=ref.id)


@router.post("/applications/{application_id}/share", response_model=ShareResponse)
async def share(application_id: str, user: CurrentUser, db: Db) -> ShareResponse:
    """Give the owner a code a lender can open. Asking again returns the same code."""
    ref, data = await _owned_application(db, application_id, user, (OWNER,))
    code = data.get("shareCode")
    if not code:
        code = new_share_code()
        await (
            db.collection("shares")
            .document(code)
            .set(
                {
                    "applicationId": application_id,
                    "ownerUid": user.uid,
                    "at": firestore.SERVER_TIMESTAMP,
                }
            )
        )
        await ref.update({"shareCode": code})
        await _audit(ref, user, "share_link_created")
    return ShareResponse(share_code=code, path=f"/app/shared/{code}")


@router.delete("/applications/{application_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_share(application_id: str, user: CurrentUser, db: Db) -> None:
    """The owner takes the file back: the code stops working and the lender loses access."""
    ref, data = await _owned_application(db, application_id, user, (OWNER,))
    code = data.get("shareCode")
    if code:
        await db.collection("shares").document(code).delete()
    had_lender = data.get("officerUid")
    await ref.update({"shareCode": None, "officerUid": None, "lenderId": None, "sharedAt": None})
    await _audit(ref, user, "share_withdrawn", hadLender=bool(had_lender))


@router.post("/shared/{code}", response_model=ClaimResponse)
async def open_shared_file(code: str, user: CurrentUser, db: Db) -> ClaimResponse:
    """A lender's officer opens a file an owner shared with them."""
    share_doc = await db.collection("shares").document(code.strip().upper()).get()
    if not share_doc.exists:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            LINK_GONE,
        )
    application_id = share_doc.to_dict()["applicationId"]
    ref = db.collection("applications").document(application_id)
    snapshot = await ref.get()
    data = snapshot.to_dict() if snapshot.exists else None
    if not data:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            LINK_GONE,
        )
    holder = data.get("officerUid")
    if holder and holder != user.uid:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Another loan officer has already opened this file. Only one lender can hold it "
            "at a time.",
        )
    if not holder:
        await ref.update(
            {
                "officerUid": user.uid,
                "lenderId": DEMO_LENDER_ID,
                "sharedAt": firestore.SERVER_TIMESTAMP,
            }
        )
        await _audit(ref, user, "opened_by_lender", role=OFFICER)
    return ClaimResponse(application_id=application_id)


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(application_id: str, user: CurrentUser, db: Db, remover: Remover) -> None:
    """The owner deletes the file for good: every record, reading, check, memo, decision, code and
    stored photo or recording, whoever added it. Nothing is kept to audit it, because the file and
    its audit log are gone; the server log notes only that a file was deleted."""
    ref, data = await _owned_application(db, application_id, user, (OWNER, OFFICER, REVIEWER))
    if role_of(data, user) != OWNER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the business owner can delete this file. A lender can stop working on it, but "
            "the file is the owner's.",
        )
    if data.get("status") == ApplicationStatus.AWAITING_SIGNOFF.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Your lender is deciding on this file right now, so it can't be deleted yet. Once they "
            "have decided, you can delete it.",
        )
    if _is_running(data):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Your records are being checked right now. Wait for the check to finish, then delete "
            "the file.",
        )
    owner_decision = await ref.collection("owner").document("decision").get()
    if owner_decision.exists and (owner_decision.to_dict() or {}).get("state") == "accepted":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You accepted a loan offer on this file, so your lender needs to keep it while the "
            "loan is arranged. Ask your lender if you want it removed.",
        )

    # Photos and recordings first: if anything fails after this, the file is still listed and
    # the owner can simply delete it again.
    removed = await remover.delete_prefix(f"evidence/{application_id}/")
    codes = {
        "shares": data.get("shareCode"),
        "signoffs": (data.get("decision") or {}).get("signoffCode"),
    }
    for collection, code in codes.items():
        if code:
            await db.collection(collection).document(code).delete()
    # The application and everything under it: evidence, runs, memo, owner, audit.
    await db.recursive_delete(ref)
    log.info("An owner deleted application %s and %d stored files", application_id, removed)
