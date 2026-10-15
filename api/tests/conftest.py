"""Test doubles for Gemini, Firestore and Firebase Auth, so the suite runs offline."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.ledger_reader import LedgerLine, LedgerReading
from app.auth import User, current_user
from app.gemini import get_gemini
from app.main import create_app
from app.store import get_firestore

SAMPLE_READING = LedgerReading(
    legible=True,
    lines=[
        LedgerLine(
            line=1,
            date_text="11/9",
            description="jual sembako",
            amount_text="610rb",
            kind="sale",
            confidence=0.95,
        ),
        LedgerLine(
            line=2,
            date_text="14/9",
            description="Sabtu pasar",
            amount_text="2,1jt",
            kind="sale",
            confidence=0.9,
        ),
        LedgerLine(
            line=3,
            date_text=None,
            description="kasbon Bu Tini",
            amount_text="20rb",
            kind="receivable",
            confidence=0.85,
        ),
        LedgerLine(
            line=4,
            date_text=None,
            description="catatan",
            amount_text=None,
            kind="other",
            confidence=0.6,
        ),
    ],
)


class FakeGemini:
    def __init__(self, reading: LedgerReading = SAMPLE_READING) -> None:
        self.reading = reading
        self.calls: list[dict] = []

    async def generate(self, *, contents, schema, system, temperature=0.0, attempts=3):
        self.calls.append({"contents": contents, "schema": schema, "system": system})
        return self.reading, "gemini-test"


class FakeDocument:
    def __init__(self, store: dict, doc_id: str) -> None:
        self._store = store
        self.id = doc_id

    async def set(self, data: dict) -> None:
        self._store[self.id] = data


class FakeCollection:
    def __init__(self, store: dict) -> None:
        self._store = store

    def document(self) -> FakeDocument:
        return FakeDocument(self._store, f"doc-{len(self._store) + 1}")


class FakeFirestore:
    def __init__(self) -> None:
        self.collections: dict[str, dict] = {}

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self.collections.setdefault(name, {}))


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def fake_db() -> FakeFirestore:
    return FakeFirestore()


@pytest.fixture
def client(fake_gemini: FakeGemini, fake_db: FakeFirestore) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_gemini] = lambda: fake_gemini
    app.dependency_overrides[get_firestore] = lambda: fake_db
    app.dependency_overrides[current_user] = lambda: User(uid="judge-1", anonymous=True)
    return TestClient(app)


@pytest.fixture
def anonymous_client() -> TestClient:
    """A client with no auth override, to check that protected routes reject missing tokens."""
    return TestClient(create_app())
