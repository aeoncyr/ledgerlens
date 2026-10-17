"""Pilot requests from the public "For lenders" page.

A lender who wants to try LedgerLens beside its own officers leaves its name, type, province, rough
volume and one way to reach a person. Requests are stored in ``pilotRequests`` and read by the team
in the Google Cloud console only: no browser may read them (the Firestore rules deny everything not
listed, and this collection is not listed). Nothing is sent anywhere, so the page promises a reply
and nothing more.

The page is public, so the endpoint is limited per visitor and for the whole site each day, counted
in ``usage/pilot-{UTC date}`` like the demo limits.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore
from pydantic import Field

from app.auth import User, current_user
from app.schemas import CamelModel
from app.store import get_firestore

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["pilot"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

REQUESTS_PER_USER_PER_DAY = 3
REQUESTS_PER_DAY = 50

# What the visitor agreed to, stored with the request so we know which text they saw.
CONSENT_TEXT = (
    "LedgerLens may store these details and use them only to reply about a pilot. "
    "Ask us and we delete them."
)

LenderType = Literal["bpr", "bprs", "cooperative", "microfinance", "other"]

# Loose on purpose: a typo is caught by the person replying, not by a stricter pattern.
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Indonesian numbers are written many ways ("0812-3456-7890", "+62 812 3456 7890").
WHATSAPP = re.compile(r"^\+?[0-9][0-9 ()-]{6,22}[0-9]$")


class PilotRequestIn(CamelModel):
    lender_name: str = Field(min_length=2, max_length=120)
    lender_type: LenderType
    province: str = Field(min_length=2, max_length=60)
    files_per_month: int = Field(ge=1, le=100_000)
    contact_name: str = Field(min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    whatsapp: str | None = Field(default=None, max_length=30)
    consent: bool


class PilotRequestOut(CamelModel):
    id: str
    reply_by: Literal["email", "whatsapp"]


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


async def _claim(db: firestore.AsyncClient, uid: str) -> None:
    """Count one request against today's limits, or refuse it in plain words."""
    today = datetime.now(UTC).date().isoformat()
    ref = db.collection("usage").document(f"pilot-{today}")
    snapshot = await ref.get()
    usage = (snapshot.to_dict() if snapshot.exists else None) or {"total": 0, "byUser": {}}
    mine = usage["byUser"].get(uid, 0)
    if mine >= REQUESTS_PER_USER_PER_DAY:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "We already have your request from today. We'll reply to it; there's no need to send "
            "it again.",
        )
    if usage["total"] >= REQUESTS_PER_DAY:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "We've had a lot of requests today. Please try again tomorrow.",
        )
    usage["total"] += 1
    usage["byUser"][uid] = mine + 1
    await ref.set(usage)


@router.post("/pilot-requests", response_model=PilotRequestOut, status_code=status.HTTP_201_CREATED)
async def create_pilot_request(body: PilotRequestIn, user: CurrentUser, db: Db) -> PilotRequestOut:
    if not body.consent:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Please tick the box to let us keep these details, so we can reply.",
        )
    email = _clean(body.email)
    whatsapp = _clean(body.whatsapp)
    if not email and not whatsapp:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Add an email address or a WhatsApp number, so we can reply.",
        )
    if email and not EMAIL.match(email):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "That email address doesn't look complete. Check it, or leave it empty and give a "
            "WhatsApp number.",
        )
    if whatsapp and not WHATSAPP.match(whatsapp):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "That WhatsApp number doesn't look right. Use digits, for example 0812 3456 7890.",
        )

    await _claim(db, user.uid)
    ref = db.collection("pilotRequests").document()
    await ref.set(
        {
            "lenderName": body.lender_name.strip(),
            "lenderType": body.lender_type,
            "province": body.province.strip(),
            "filesPerMonth": body.files_per_month,
            "contactName": body.contact_name.strip(),
            "email": email,
            "whatsapp": whatsapp,
            "consent": {"given": True, "text": CONSENT_TEXT},
            "uid": user.uid,
            "status": "new",
            "createdAt": datetime.now(UTC).isoformat(),
        }
    )
    # The id only: the contact details stay out of the server log.
    log.info("pilot request %s saved", ref.id)
    return PilotRequestOut(id=ref.id, reply_by="email" if email else "whatsapp")
