"""The decision loop: the officer recommends, a second person signs off, the owner hears back.

An approval or a decline is first a recommendation. It waits for a second person at the lender
(four eyes, as lenders already require for credit decisions), who opens it with a code like a
share code, reads the file without changing it, and either signs it off or sends it back with a
note. Asking the owner for more evidence needs no sign-off and goes to the owner at once.

When a decision is final, the owner gets ``owner/decision``: what was decided, the offer with its
repayment schedule (computed by ``app.loan``), any conditions, and a short letter in English and
Bahasa Indonesia. The owner then accepts or declines the offer, marks conditions as met, or sends
the records asked for. Every step is in the audit log and is emitted as an event (``app.events``)
for webhooks and notifications.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app import events
from app.agents.decision_letter import write_letter
from app.auth import User, current_user
from app.gemini import Gemini, get_gemini
from app.loan import make_offer
from app.routers.applications import (
    EITHER,
    OFFICER,
    REVIEWER,
    _audit,
    _owned_application,
    role_of,
)
from app.routers.owner import new_share_code
from app.schemas import (
    ApplicationStatus,
    ClaimResponse,
    DecisionAction,
    DecisionRequest,
    DecisionResponse,
    EvidenceType,
    OfferAnswerRequest,
    SignoffRequest,
)
from app.store import get_firestore

router = APIRouter(prefix="/api", tags=["decisions"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]
Writer = Annotated[Gemini, Depends(get_gemini)]

DECIDABLE = {
    ApplicationStatus.READY.value,
    ApplicationStatus.NEEDS_FOLLOW_UP.value,
    ApplicationStatus.IN_REVIEW.value,
}
# What the owner's copy of a final decision says, by action, until the owner answers it.
OWNER_STATE = {
    DecisionAction.APPROVE: "offered",
    DecisionAction.DECLINE: "declined",
    DecisionAction.REQUEST_MORE: "requested",
}
SIGNOFF_GONE = (
    "This sign-off link no longer works. The decision may already be signed off or sent back; "
    "ask the officer for a new link."
)
NO_DECISION = "There is no decision on this file to answer yet."
RECORD_NAMES = {
    EvidenceType.LEDGER_PAGE: "a notebook page",
    EvidenceType.QRIS_HISTORY: "a QRIS history screenshot",
    EvidenceType.RECEIPT: "a receipt",
    EvidenceType.SHOP_PHOTO: "a photo of the business",
    EvidenceType.INTERVIEW_AUDIO: "a recorded interview",
}


def _payload(application_id: str, data: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """What every event carries, so a listener needs nothing else to describe it."""
    return {
        "applicationId": application_id,
        "officerUid": data.get("officerUid"),
        "alias": data["business"]["alias"],
        "at": datetime.now(UTC).isoformat(),
        **extra,
    }


async def _evidence_counts(ref: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    async for snapshot in ref.collection("evidence").stream():
        kind = (snapshot.to_dict() or {}).get("type", "other")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


async def _max_installment(ref: Any) -> int | None:
    memo = await ref.collection("memo").document("current").get()
    policy = (memo.to_dict() or {}).get("policy") if memo.exists else None
    return (policy or {}).get("maxInstallment")


async def _finalise(
    ref: Any,
    application_id: str,
    data: dict[str, Any],
    decision: dict[str, Any],
    gemini: Gemini,
    user: User,
    signed_off_by: str | None,
) -> None:
    """Write the owner's copy of a final decision, with its letter, and announce it."""
    action = DecisionAction(decision["action"])
    conditions = decision.get("conditions") or []
    counts = await _evidence_counts(ref)
    letter = await write_letter(
        gemini,
        action=action,
        alias=data["business"]["alias"],
        reason=decision["reason"],
        conditions=[c["text"] for c in conditions],
        offer=decision.get("offer"),
        requested_amount=data["request"]["amount"],
    )
    await (
        ref.collection("owner")
        .document("decision")
        .set(
            {
                "action": action.value,
                "offer": decision.get("offer"),
                "conditions": [
                    {
                        **c,
                        "met": False,
                        "metAt": None,
                        # A condition met by a record needs a new one, not one already on file.
                        "evidenceBefore": counts.get(c.get("evidenceType") or "", 0),
                    }
                    for c in conditions
                ],
                "letter": letter,
                "state": OWNER_STATE[action],
                "evidenceCountAtDecision": sum(counts.values()),
                "decidedAt": firestore.SERVER_TIMESTAMP,
            }
        )
    )
    await _audit(
        ref,
        user,
        "decision_sent_to_owner",
        decided=action.value,
        letter=letter["source"],
        model=letter["model"],
    )
    await events.emit(
        "decision.final",
        _payload(
            application_id,
            data,
            action=action.value,
            reason=decision["reason"],
            offer=decision.get("offer"),
            conditions=conditions,
            signedOffBy=signed_off_by,
        ),
    )


# --- The officer recommends -----------------------------------------------------------------------


@router.post("/applications/{application_id}/decision", response_model=DecisionResponse)
async def record_decision(
    application_id: str, body: DecisionRequest, user: CurrentUser, db: Db, gemini: Writer
) -> DecisionResponse:
    ref, data = await _owned_application(db, application_id, user)
    if data.get("status") not in DECIDABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Check the evidence before recording a decision."
            if data.get("status") != ApplicationStatus.AWAITING_SIGNOFF.value
            else "This decision is waiting for a second person to sign it off.",
        )
    offer = None
    if body.offer:
        offer = make_offer(
            body.offer.amount_rp,
            body.offer.tenor_months,
            body.offer.annual_rate_pct,
            await _max_installment(ref),
        ).model_dump(by_alias=True)
    conditions = [
        {"text": c.text.strip(), "evidenceType": c.evidence_type.value if c.evidence_type else None}
        for c in body.conditions
    ]
    decision: dict[str, Any] = {
        "action": body.action.value,
        "reason": body.reason,
        "offer": offer,
        "conditions": conditions,
        "by": user.uid,
        "at": datetime.now(UTC),
    }

    if body.action is DecisionAction.REQUEST_MORE:
        # Asking for more evidence decides nothing, so it goes to the owner without a sign-off.
        decision["state"] = "final"
        await ref.update({"status": ApplicationStatus.COLLECTING.value, "decision": decision})
        await _audit(ref, user, "decision_request_more", reason=body.reason, asked=len(conditions))
        await _finalise(ref, application_id, data, decision, gemini, user, signed_off_by=None)
        return DecisionResponse(state="final")

    code = new_share_code()
    await (
        db.collection("signoffs")
        .document(code)
        .set(
            {
                "applicationId": application_id,
                "officerUid": user.uid,
                "reviewerUid": None,
                "at": firestore.SERVER_TIMESTAMP,
            }
        )
    )
    decision.update(state="recommended", signoffCode=code)
    await ref.update(
        {
            "status": ApplicationStatus.AWAITING_SIGNOFF.value,
            "decision": decision,
            # A new recommendation needs a new sign-off, by whoever opens the new link.
            "reviewerUid": None,
        }
    )
    await _audit(
        ref,
        user,
        f"recommended_{body.action.value}",
        reason=body.reason,
        withinPolicy=offer["withinPolicy"] if offer else None,
    )
    await events.emit(
        "decision.recommended",
        _payload(
            application_id,
            data,
            action=body.action.value,
            reason=body.reason,
            offer=offer,
            conditions=conditions,
        ),
    )
    return DecisionResponse(state="recommended", signoff_code=code, path=f"/app/signoff/{code}")


# --- A second person signs off --------------------------------------------------------------------


@router.post("/signoff/{code}", response_model=ClaimResponse)
async def claim_signoff(code: str, user: CurrentUser, db: Db) -> ClaimResponse:
    """A second person opens a recommendation to sign it off. The first to open it holds it."""
    code = code.strip().upper()
    signoff_ref = db.collection("signoffs").document(code)
    signoff = await signoff_ref.get()
    if not signoff.exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, SIGNOFF_GONE)
    application_id = signoff.to_dict()["applicationId"]
    ref = db.collection("applications").document(application_id)
    snapshot = await ref.get()
    data = snapshot.to_dict() if snapshot.exists else None
    if (
        not data
        or data.get("status") != ApplicationStatus.AWAITING_SIGNOFF.value
        or (data.get("decision") or {}).get("signoffCode") != code
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, SIGNOFF_GONE)
    # Four eyes: the officer can't sign off their own recommendation, nor the owner their own file.
    # Only on a demo file, where one person plays every role on purpose, may they do both.
    demo = data.get("demo") is True
    if data.get("officerUid") == user.uid and not demo:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You recommended this decision, so someone else has to sign it off. Send them the "
            "link, or open it in another browser to try both roles.",
        )
    if data.get("ownerUid") == user.uid and not demo:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This link is for the lender's staff. The decision will reach you in your file.",
        )
    holder = data.get("reviewerUid")
    if holder and holder != user.uid:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Someone else is already signing off this decision.",
        )
    if not holder:
        await ref.update({"reviewerUid": user.uid})
        await signoff_ref.update({"reviewerUid": user.uid})
        await _audit(ref, user, "signoff_opened", role=REVIEWER)
    return ClaimResponse(application_id=application_id)


@router.post("/applications/{application_id}/signoff", status_code=status.HTTP_204_NO_CONTENT)
async def sign_off(
    application_id: str, body: SignoffRequest, user: CurrentUser, db: Db, gemini: Writer
) -> None:
    """Approve the recommendation (it becomes final) or send it back to the officer with a note."""
    ref, data = await _owned_application(db, application_id, user, (REVIEWER,))
    decision = dict(data.get("decision") or {})
    if data.get("status") != ApplicationStatus.AWAITING_SIGNOFF.value or not decision:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "There is no recommendation waiting for your sign-off."
        )
    code = decision.get("signoffCode")
    if code:
        await db.collection("signoffs").document(code).delete()
    decision.update(
        signoffCode=None,
        signoff={
            "approved": body.approve,
            "note": body.note.strip(),
            "by": user.uid,
            "at": datetime.now(UTC),
        },
    )
    if not body.approve:
        decision["state"] = "returned"
        await ref.update({"status": ApplicationStatus.IN_REVIEW.value, "decision": decision})
        await _audit(ref, user, "signoff_returned", reason=body.note.strip())
        return

    decision["state"] = "final"
    await ref.update({"status": ApplicationStatus.DECIDED.value, "decision": decision})
    await _audit(
        ref,
        user,
        f"decision_{decision['action']}",
        reason=body.note.strip() or None,
        signedOff=True,
    )
    await _finalise(ref, application_id, data, decision, gemini, user, signed_off_by=user.uid)


# --- The owner answers ----------------------------------------------------------------------------


async def _owner_side(db: firestore.AsyncClient, application_id: str, user: User):
    """The owner answers for themselves. On a file an officer started there is no owner in the
    app, so the officer records the owner's answer, as they record answers to questions."""
    ref, data = await _owned_application(db, application_id, user, EITHER)
    if role_of(data, user) == OFFICER and data.get("ownerUid"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The business owner answers this in their own app."
        )
    decision_ref = ref.collection("owner").document("decision")
    snapshot = await decision_ref.get()
    if not snapshot.exists:
        raise HTTPException(status.HTTP_409_CONFLICT, NO_DECISION)
    return ref, data, decision_ref, snapshot.to_dict() or {}


@router.post("/applications/{application_id}/offer", status_code=status.HTTP_204_NO_CONTENT)
async def answer_offer(
    application_id: str, body: OfferAnswerRequest, user: CurrentUser, db: Db
) -> None:
    ref, data, decision_ref, owner_decision = await _owner_side(db, application_id, user)
    if owner_decision.get("action") != DecisionAction.APPROVE.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "There is no loan offer on this file.")
    if owner_decision.get("state") != "offered":
        raise HTTPException(status.HTTP_409_CONFLICT, "This offer has already been answered.")
    await decision_ref.update(
        {
            "state": "accepted" if body.accept else "declined_by_owner",
            "answeredAt": firestore.SERVER_TIMESTAMP,
            "answeredBy": role_of(data, user),
        }
    )
    await _audit(ref, user, "offer_accepted" if body.accept else "offer_declined")
    await events.emit(
        "offer.accepted" if body.accept else "offer.declined",
        _payload(application_id, data, offer=owner_decision.get("offer")),
    )


@router.post(
    "/applications/{application_id}/conditions/{index}/met",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def condition_met(application_id: str, index: int, user: CurrentUser, db: Db) -> None:
    """The owner says a condition is met; one met by a record needs that record sent first."""
    ref, data, decision_ref, owner_decision = await _owner_side(db, application_id, user)
    conditions = list(owner_decision.get("conditions") or [])
    if not 0 <= index < len(conditions):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We can't find that condition.")
    if owner_decision.get("state") != "accepted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Accept the offer first.")
    condition = conditions[index]
    if condition.get("met"):
        return
    kind = condition.get("evidenceType")
    if kind and (await _evidence_counts(ref)).get(kind, 0) <= condition.get("evidenceBefore", 0):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Send {RECORD_NAMES.get(EvidenceType(kind), 'the record')} under Your records "
            "first, then mark this as done.",
        )
    # Firestore can't put a server timestamp inside a list, so the time is the API's.
    conditions[index] = {**condition, "met": True, "metAt": datetime.now(UTC)}
    await decision_ref.update({"conditions": conditions})
    await _audit(ref, user, "condition_met", reason=None, index=index, text=condition["text"])
    await events.emit(
        "condition.met", _payload(application_id, data, index=index, text=condition["text"])
    )


@router.post(
    "/applications/{application_id}/requested/sent", status_code=status.HTTP_204_NO_CONTENT
)
async def requested_sent(application_id: str, user: CurrentUser, db: Db) -> None:
    """The owner tells the lender they have sent the records asked for."""
    ref, data, decision_ref, owner_decision = await _owner_side(db, application_id, user)
    if (
        owner_decision.get("action") != DecisionAction.REQUEST_MORE.value
        or owner_decision.get("state") != "requested"
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Your lender isn't waiting for records.")
    count = sum((await _evidence_counts(ref)).values())
    added = count - owner_decision.get("evidenceCountAtDecision", 0)
    if added <= 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Add the records under Your records first, then send them."
        )
    await decision_ref.update(
        {"state": "sent", "sentAt": firestore.SERVER_TIMESTAMP, "sentCount": added}
    )
    await ref.update({"status": ApplicationStatus.COLLECTING.value})
    await _audit(ref, user, "requested_records_sent", count=added)
    await events.emit("evidence.requested_received", _payload(application_id, data, count=added))
