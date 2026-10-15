"""Test doubles so the suite runs offline."""

from __future__ import annotations

import pytest

from app.agents.ledger_reader import LedgerLine, LedgerReading

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


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()
