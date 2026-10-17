"""Verify the Firebase ID token that the web app sends with every request.

Judges are signed in anonymously by the web app, so there is no login wall, but every API call is
still tied to a Firebase user.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Annotated

import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from app.config import get_settings

_bearer = HTTPBearer(auto_error=False)


# Which of the two apps made a call: "owner", "officer" or "reviewer". One person plays every role
# on a demo file, so the API needs to be told which one; ``role_of`` honours it on demo files only.
ACT_AS_HEADER = "X-LedgerLens-Act-As"
ACTING_ROLES = ("owner", "officer", "reviewer")


@dataclass(frozen=True)
class User:
    uid: str
    anonymous: bool
    acting: str | None = None


@lru_cache
def _firebase_app() -> firebase_admin.App:
    project = get_settings().project
    return firebase_admin.initialize_app(options={"projectId": project} if project else None)


async def firebase_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "You're not signed in. Refresh the page to continue."
        )
    try:
        claims = await run_in_threadpool(
            firebase_auth.verify_id_token, credentials.credentials, _firebase_app()
        )
    except Exception as exc:  # invalid, expired or revoked token
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Your session has expired. Refresh the page to continue."
        ) from exc
    provider = claims.get("firebase", {}).get("sign_in_provider")
    return User(uid=claims["uid"], anonymous=provider == "anonymous")


async def current_user(
    user: Annotated[User, Depends(firebase_user)],
    act_as: Annotated[str | None, Header(alias=ACT_AS_HEADER)] = None,
) -> User:
    """The signed-in user, with the role the calling app says it plays (a claim, not a right)."""
    acting = (act_as or "").strip().lower()
    return replace(user, acting=acting if acting in ACTING_ROLES else None)
