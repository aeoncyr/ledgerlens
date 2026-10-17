"""Who opened my file: the owner's own timeline of what happened to their file.

The audit log is the lender's (Firestore rules keep it from the owner), and much of it is internal:
who at the lender did what, the reasons they wrote, the second person's notes. The owner still has
a right to know who has seen their file and where it stands, so this route reads the log for them
and returns only an allowlist of events, each as a fixed key the owner app words in English or
Bahasa Indonesia. No officer's identity, reason, note or figure leaves the log this way.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from google.cloud import firestore

from app.auth import User, current_user
from app.routers.applications import OWNER, _owned_application
from app.schemas import CamelModel
from app.store import get_firestore

router = APIRouter(prefix="/api/applications", tags=["activity"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

# The audit actions the owner may see, and the owner-safe event each becomes. Anything not listed
# here (findings, readings, agreement with the assessment, SLIK, policy, notes) stays internal.
OWNER_EVENTS: dict[str, str] = {
    "created_by_owner": "started",
    "demo_story_started": "started",
    "created": "started_by_lender",
    "invite_created": "invited",
    "invite_opened": "invite_opened",
    "consent_given": "consent_given",
    "consent_withdrawn": "consent_withdrawn",
    "analysis_completed": "checked",
    "reverified_with_answers": "checked_again",
    "share_link_created": "shared",
    "opened_by_lender": "opened_by_lender",
    "share_withdrawn": "share_stopped",
    # Recommending either way reads the same: the owner learns what was decided once it is final.
    "recommended_approve": "decision_recommended",
    "recommended_decline": "decision_recommended",
    "signoff_opened": "signoff_opened",
    "signoff_returned": "decision_reconsidered",
    "decision_approve": "signed_off",
    "decision_decline": "signed_off",
    "decision_sent_to_owner": "sent_to_you",
    "offer_accepted": "offer_accepted",
    "offer_declined": "offer_declined",
    "condition_met": "condition_met",
    "requested_records_sent": "records_sent",
}


class ActivityEvent(CamelModel):
    event: str
    at: datetime | None
    count: int = 1


class ActivityResponse(CamelModel):
    events: list[ActivityEvent]


def _when(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def owner_timeline(entries: list[dict[str, Any]]) -> list[ActivityEvent]:
    """The allowlisted events, oldest first; repeats in a row fold into one, with a count."""
    latest = datetime.max.replace(tzinfo=UTC)
    # A time the server has not filled in yet is the newest; the sort is stable for ties.
    ordered = sorted(entries, key=lambda e: _when(e.get("at")) or latest)
    events: list[ActivityEvent] = []
    for entry in ordered:
        event = OWNER_EVENTS.get(entry.get("action") or "")
        if not event:
            continue
        if events and events[-1].event == event:
            events[-1].count += 1
            events[-1].at = _when(entry.get("at"))
            continue
        events.append(ActivityEvent(event=event, at=_when(entry.get("at"))))
    return events


@router.get("/{application_id}/activity", response_model=ActivityResponse)
async def file_activity(application_id: str, user: CurrentUser, db: Db) -> ActivityResponse:
    """The owner's timeline of their own file. Only the owner may read it."""
    ref, _ = await _owned_application(db, application_id, user, (OWNER,))
    entries = [(s.to_dict() or {}) async for s in ref.collection("audit").stream()]
    return ActivityResponse(events=owner_timeline(entries))
