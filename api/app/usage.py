"""Daily limits on analyses, so the public demo keeps working for everyone.

The prototype runs on Gemini's free tier, which allows only so many calls a day. Without a limit,
one visitor running analyses in a loop could use the day's quota and leave the demo broken for
the judges. Each run (an analysis or a re-check) counts once, per visitor and for the whole site.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from google.cloud import firestore

from app.config import Settings


async def claim_run(db: firestore.AsyncClient, uid: str, settings: Settings) -> None:
    """Count one run against today's limits, or refuse it with an explanation."""
    today = datetime.now(UTC).date().isoformat()
    ref = db.collection("usage").document(today)
    snapshot = await ref.get()
    usage = (snapshot.to_dict() if snapshot.exists else None) or {"total": 0, "byUser": {}}
    mine = usage["byUser"].get(uid, 0)
    if mine >= settings.runs_per_user_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You've used all {mine} checks this browser gets today. The checks run on Gemini's "
            "free tier, so the demo has a daily limit. It resets at midnight UTC (07:00 in "
            "Jakarta); the sample files on the home page are always open.",
        )
    if usage["total"] >= settings.runs_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Today's demo checks are used up: LedgerLens runs on Gemini's free tier, which has a "
            "daily limit. It resets at midnight UTC (07:00 in Jakarta); the sample files on the "
            "home page are always open.",
        )
    usage["total"] += 1
    usage["byUser"][uid] = mine + 1
    # Read then write: two runs racing could both slip under the limit, which is harmless here.
    await ref.set(usage)
