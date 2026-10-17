"""A lender invites a business owner to send their records.

The officer creates an invite and sends its link (``/owner/invite/CODE``) by WhatsApp. The owner
who opens it sees which lender is asking, agrees, and starts a file that is already shared with
that officer, through the same share code an owner would create (``routers/owner.py``), so it stays
the owner's: they can stop sharing it or delete it at any time. An invite works once and for
fourteen days. An owner who opens it learns only the lender's name and type, never who the officer
is.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.auth import User, current_user
from app.routers.applications import DEMO_LENDER_ID, OFFICER, _audit
from app.routers.lender import LenderType, lender_profile
from app.routers.owner import create_share_code, new_owner_file, new_share_code
from app.schemas import CamelModel, ClaimResponse, CreateApplicationRequest
from app.store import get_firestore

router = APIRouter(prefix="/api/invites", tags=["invites"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

INVITE_DAYS = 14
RECENT_INVITES = 20
INVITES_PER_DAY = 30

GONE = "This invite link doesn't work. It may be mistyped; ask your lender to send it again."
USED = "This invite has already been used to start a file. Ask your lender for a new one."
EXPIRED = "This invite has expired. Invites work for 14 days; ask your lender for a new one."
OWN = (
    "This invite comes from your own lender workspace in this browser. To play the business "
    "owner, open the link in a private window or on another phone."
)

InviteState = Literal["open", "used", "expired"]


class InviteOut(CamelModel):
    """An invite as the officer who made it sees it."""

    code: str
    path: str
    lender_name: str
    created_at: str
    expires_at: str
    state: InviteState
    application_id: str | None = None


class InvitePublic(CamelModel):
    """What an owner opening the link learns: who is asking, and whether it still works."""

    code: str
    lender_name: str
    lender_type: LenderType | None = None
    expires_at: str
    state: InviteState
    application_id: str | None = None
    own: bool = False


def _iso(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _state(invite: dict[str, Any], now: datetime) -> InviteState:
    if invite.get("usedBy"):
        return "used"
    return "expired" if invite["expiresAt"] <= now else "open"


def _out(code: str, invite: dict[str, Any], now: datetime) -> InviteOut:
    return InviteOut(
        code=code,
        path=f"/owner/invite/{code}",
        lender_name=invite["lenderName"],
        created_at=_iso(invite["createdAt"]),
        expires_at=_iso(invite["expiresAt"]),
        state=_state(invite, now),
        application_id=invite.get("applicationId"),
    )


async def _invite(db: firestore.AsyncClient, code: str) -> tuple[Any, dict[str, Any]]:
    ref = db.collection("invites").document(code.strip().upper())
    snapshot = await ref.get()
    if not snapshot.exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, GONE)
    return ref, snapshot.to_dict() or {}


@router.post("", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite(user: CurrentUser, db: Db) -> InviteOut:
    """The officer asks a business owner to send their records."""
    profile = await lender_profile(db, user.uid)
    if not (profile or {}).get("name"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Add your lender's name in Settings first, so the owner knows who is asking.",
        )
    lender = db.collection("lenders").document(user.uid)
    now = datetime.now(UTC)
    today = now.date().isoformat()
    made = profile.get("invitesMade") or {}
    count = made.get("count", 0) if made.get("date") == today else 0
    if count >= INVITES_PER_DAY:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"That is {INVITES_PER_DAY} invites today, the most one workspace can send in a day.",
        )
    code = new_share_code()
    while (await db.collection("invites").document(code).get()).exists:
        code = new_share_code()
    invite = {
        "officerUid": user.uid,
        "lenderName": profile["name"],
        "lenderType": profile.get("type"),
        "createdAt": now,
        "expiresAt": now + timedelta(days=INVITE_DAYS),
        "usedBy": None,
        "applicationId": None,
    }
    await db.collection("invites").document(code).set(invite)
    await lender.update(
        {
            "invites": [code, *(profile.get("invites") or [])][:RECENT_INVITES],
            "invitesMade": {"date": today, "count": count + 1},
        }
    )
    return _out(code, invite, now)


@router.get("", response_model=list[InviteOut])
async def list_invites(user: CurrentUser, db: Db) -> list[InviteOut]:
    """The officer's recent invites, newest first, and whether each was used."""
    profile = await lender_profile(db, user.uid)
    now = datetime.now(UTC)
    out = []
    for code in (profile or {}).get("invites") or []:
        snapshot = await db.collection("invites").document(code).get()
        invite = snapshot.to_dict() if snapshot.exists else None
        if invite and invite.get("officerUid") == user.uid:
            out.append(_out(code, invite, now))
    return out


@router.get("/{code}", response_model=InvitePublic)
async def open_invite(code: str, user: CurrentUser, db: Db) -> InvitePublic:
    """What the owner sees before agreeing: the lender's name and whether the invite works."""
    ref, invite = await _invite(db, code)
    mine = invite.get("usedBy") == user.uid
    return InvitePublic(
        code=ref.id,
        lender_name=invite["lenderName"],
        lender_type=invite.get("lenderType"),
        expires_at=_iso(invite["expiresAt"]),
        state=_state(invite, datetime.now(UTC)),
        application_id=invite.get("applicationId") if mine else None,
        own=invite.get("officerUid") == user.uid,
    )


@router.post("/{code}/accept", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def accept_invite(
    code: str, body: CreateApplicationRequest, user: CurrentUser, db: Db
) -> ClaimResponse:
    """The owner agrees: a new file, theirs, already shared with the officer who invited them."""
    ref, invite = await _invite(db, code)
    if invite.get("usedBy") == user.uid and invite.get("applicationId"):
        return ClaimResponse(application_id=invite["applicationId"])  # asked twice
    if invite.get("officerUid") == user.uid:
        raise HTTPException(status.HTTP_409_CONFLICT, OWN)
    if invite.get("usedBy"):
        raise HTTPException(status.HTTP_409_CONFLICT, USED)
    if invite["expiresAt"] <= datetime.now(UTC):
        raise HTTPException(status.HTTP_410_GONE, EXPIRED)

    officer = invite["officerUid"]
    application = await new_owner_file(
        db,
        body,
        user,
        officerUid=officer,
        lenderId=DEMO_LENDER_ID,
        lenderName=invite["lenderName"],
        invite=ref.id,
        sharedAt=firestore.SERVER_TIMESTAMP,
    )
    # The same share code an owner creates, so stopping sharing works as it always does.
    await create_share_code(db, application, user.uid)
    await ref.update(
        {"usedBy": user.uid, "applicationId": application.id, "usedAt": datetime.now(UTC)}
    )
    audit = application.collection("audit")
    await audit.document().set(
        {
            "actor": officer,
            "action": "invite_created",
            "reason": None,
            "details": {"code": ref.id, "lender": invite["lenderName"], "role": OFFICER},
            "at": invite["createdAt"],  # when the officer made it, so the log reads in order
        }
    )
    await _audit(application, user, "invite_opened", code=ref.id, lender=invite["lenderName"])
    return ClaimResponse(application_id=application.id)
