"""Verify the Firebase ID token that the web app sends with every request.

Judges are signed in anonymously by the web app, so there is no login wall, but every API call is
still tied to a Firebase user.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from app.config import get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class User:
    uid: str
    anonymous: bool


@lru_cache
def _firebase_app() -> firebase_admin.App:
    project = get_settings().project
    return firebase_admin.initialize_app(options={"projectId": project} if project else None)


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        claims = await run_in_threadpool(
            firebase_auth.verify_id_token, credentials.credentials, _firebase_app()
        )
    except Exception as exc:  # invalid, expired or revoked token
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    provider = claims.get("firebase", {}).get("sign_in_provider")
    return User(uid=claims["uid"], anonymous=provider == "anonymous")
