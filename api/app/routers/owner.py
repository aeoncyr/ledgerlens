"""The business owner's side: start a file, share it with a lender, withdraw it.

An owner can build their own credit file and then give a lender access with a share code, which the
officer opens as a link. The file stays the owner's: they can withdraw the lender's access at any
time, and only one lender has it at once. There is no lender directory or matching; the owner
decides who to show it to, as they would show a printed file.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.auth import User, current_user
from app.routers.applications import DEMO_LENDER_ID, OFFICER, OWNER, _audit, _owned_application
from app.schemas import (
    ApplicationStatus,
    ClaimResponse,
    CreateApplicationRequest,
    CreateApplicationResponse,
    ShareResponse,
)
from app.store import get_firestore

router = APIRouter(prefix="/api", tags=["owner"])

LINK_GONE = "This link no longer works. The owner may have stopped sharing; ask them for a new one."

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

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
            "request": {"amount": body.amount, "tenorMonths": body.tenor_months},
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
