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

    async def generate(self, *, contents, schema, system, temperature=0.0, attempts=3, role="read"):
        self.calls.append({"contents": contents, "schema": schema, "system": system})
        return self.reading, "gemini-test"


class FakeSnapshot:
    def __init__(self, data: dict | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict | None:
        return None if self._data is None else dict(self._data)


class FakeDocument:
    def __init__(self, db: FakeFirestore, path: tuple[str, ...]) -> None:
        self._db = db
        self._path = path
        self.id = path[-1]

    async def set(self, data: dict) -> None:
        self._db.docs[self._path] = dict(data)

    async def delete(self) -> None:
        self._db.docs.pop(self._path, None)

    async def get(self) -> FakeSnapshot:
        return FakeSnapshot(self._db.docs.get(self._path))

    async def update(self, data: dict) -> None:
        if self._path not in self._db.docs:
            raise KeyError(f"No document at {'/'.join(self._path)}")
        self._db.docs[self._path].update(data)

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self._db, (*self._path, name))


class FakeCollection:
    def __init__(self, db: FakeFirestore, path: tuple[str, ...]) -> None:
        self._db = db
        self._path = path

    async def stream(self):
        for doc_id, data in self._db.docs_in(*self._path).items():
            snapshot = FakeSnapshot(data)
            snapshot.id = doc_id
            yield snapshot

    def document(self, doc_id: str | None = None) -> FakeDocument:
        if doc_id is None:
            self._db.counter += 1
            doc_id = f"doc-{self._db.counter}"
        return FakeDocument(self._db, (*self._path, doc_id))

    def where(self, *, filter) -> FakeQuery:
        return FakeQuery(self, [filter])


class FakeQuery:
    """Equality filters and a limit, which is all the API asks of a query."""

    def __init__(self, collection: FakeCollection, filters: list, limit: int | None = None) -> None:
        self._collection = collection
        self._filters = filters
        self._limit = limit

    def where(self, *, filter) -> FakeQuery:
        return FakeQuery(self._collection, [*self._filters, filter], self._limit)

    def limit(self, count: int) -> FakeQuery:
        return FakeQuery(self._collection, self._filters, count)

    async def stream(self):
        yielded = 0
        async for snapshot in self._collection.stream():
            data = snapshot.to_dict() or {}
            if not all(
                f.op_string == "==" and data.get(f.field_path) == f.value for f in self._filters
            ):
                continue
            if self._limit is not None and yielded >= self._limit:
                return
            yielded += 1
            yield snapshot


class FakeFirestore:
    """An in-memory stand-in for Firestore, keyed by document path."""

    def __init__(self) -> None:
        self.docs: dict[tuple[str, ...], dict] = {}
        self.counter = 0

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self, (name,))

    async def recursive_delete(self, reference: FakeDocument) -> int:
        """Delete a document and everything under it, as the real client does."""
        prefix = reference._path
        doomed = [path for path in self.docs if path[: len(prefix)] == prefix]
        for path in doomed:
            del self.docs[path]
        return len(doomed)

    def docs_in(self, *collection_path: str) -> dict[str, dict]:
        return {p[-1]: d for p, d in self.docs.items() if p[:-1] == collection_path}

    @property
    def collections(self) -> dict[str, dict[str, dict]]:
        return {path[0]: self.docs_in(path[0]) for path in self.docs if len(path) == 2}


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def fake_db() -> FakeFirestore:
    return FakeFirestore()


@pytest.fixture
def client_as(fake_gemini: FakeGemini, fake_db: FakeFirestore):
    """Build a client signed in as the given user, sharing one fake Gemini and Firestore."""

    def make(uid: str) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_gemini] = lambda: fake_gemini
        app.dependency_overrides[get_firestore] = lambda: fake_db
        app.dependency_overrides[current_user] = lambda: User(uid=uid, anonymous=True)
        return TestClient(app)

    return make


@pytest.fixture
def client(client_as) -> TestClient:
    return client_as("judge-1")


@pytest.fixture
def anonymous_client() -> TestClient:
    """A client with no auth override, to check that protected routes reject missing tokens."""
    return TestClient(create_app())
