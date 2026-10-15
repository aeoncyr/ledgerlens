"""Firestore access. Only the backend writes results; the web app reads them with security rules."""

from __future__ import annotations

from functools import lru_cache

from google.cloud import firestore

from app.config import get_settings


@lru_cache
def get_firestore() -> firestore.AsyncClient:
    return firestore.AsyncClient(project=get_settings().project or None)
