"""The Gemini client's model chains, free-tier pacing and daily-quota fallthrough, offline."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.config import Settings
from app.gemini import Gemini, GeminiQuotaExhausted, ModelPacer


class Answer(BaseModel):
    ok: bool


DAILY = Exception(
    "429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
)
MINUTE = Exception("429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerMinutePerProjectPerModel")


class FakeModels:
    """Plays back a scripted outcome per model: an exception to raise, or success."""

    def __init__(self, script: dict[str, list]) -> None:
        self.script = script
        self.calls: list[str] = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append(model)
        outcomes = self.script.get(model, [])
        outcome = outcomes.pop(0) if outcomes else None
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(parsed=Answer(ok=True))


def make(script: dict[str, list], free_tier: bool = True):
    settings = replace(
        Settings.from_env(),
        gemini_api_key="test-key" if free_tier else None,
        reader_models=("lite-a", "lite-b"),
        writer_models=("flash-a", "flash-b"),
    )
    models = FakeModels(script)
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    slept: list[float] = []

    async def sleep(seconds):
        slept.append(seconds)

    return Gemini(settings, client=client, sleep=sleep), models, slept


def call(gemini, role="read"):
    return asyncio.run(gemini.generate(contents=["x"], schema=Answer, system="s", role=role))


def test_readers_and_writers_use_their_own_chains():
    gemini, models, _ = make({})

    assert call(gemini, "read")[1] == "lite-a"
    assert call(gemini, "write")[1] == "flash-a"
    assert models.calls == ["lite-a", "flash-a"]


def test_a_spent_daily_quota_moves_down_the_chain_and_stays_skipped():
    gemini, models, slept = make({"flash-a": [DAILY]})

    assert call(gemini, "write")[1] == "flash-b"
    assert call(gemini, "write")[1] == "flash-b"
    assert models.calls == ["flash-a", "flash-b", "flash-b"]
    assert slept == []  # no point waiting on a quota that resets tomorrow


def test_every_model_spent_raises_a_clear_error():
    gemini, _, _ = make({"lite-a": [DAILY], "lite-b": [DAILY]})

    with pytest.raises(GeminiQuotaExhausted, match="midnight Pacific"):
        call(gemini, "read")


def test_a_per_minute_limit_is_retried_after_a_wait():
    gemini, models, slept = make({"lite-a": [MINUTE]})

    assert call(gemini, "read")[1] == "lite-a"
    assert models.calls == ["lite-a", "lite-a"]
    assert slept and slept[0] >= 4


def test_a_model_that_keeps_failing_is_dropped_for_the_next():
    boom = RuntimeError("500 INTERNAL")
    gemini, models, _ = make({"lite-a": [boom, boom, boom]})

    assert call(gemini, "read")[1] == "lite-b"
    assert models.calls == ["lite-a"] * 3 + ["lite-b"]


def test_pacer_keeps_each_model_under_its_limit_and_spreads_the_load():
    now = [0.0]
    waits: list[float] = []

    async def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    pacer = ModelPacer(lambda model: 2, clock=lambda: now[0], sleep=sleep)

    async def take(n):
        return [await pacer.acquire(["a", "b"]) for _ in range(n)]

    picked = asyncio.run(take(5))

    assert picked == ["a", "a", "b", "b", "a"]  # a's minute is full, so b; then wait for a
    assert waits and 59 < waits[0] <= 60.1


def test_pacer_forgets_an_exhausted_model_after_the_reset():
    clock = [datetime(2026, 10, 15, 20, 0, tzinfo=UTC)]
    pacer = ModelPacer(lambda model: None, wall_clock=lambda: clock[0])

    pacer.mark_exhausted("a")
    assert not pacer.available("a")
    clock[0] = datetime(2026, 10, 16, 7, 1, tzinfo=UTC)
    assert pacer.available("a")


def test_vertex_ai_is_not_paced():
    gemini, models, slept = make({}, free_tier=False)

    for _ in range(20):
        call(gemini, "write")

    assert slept == []
    assert len(models.calls) == 20


def test_a_busy_model_hands_over_at_once_but_the_last_one_is_retried():
    busy = Exception("503 UNAVAILABLE: This model is currently experiencing high demand.")
    gemini, models, slept = make({"flash-a": [busy], "flash-b": [busy]})

    assert call(gemini, "write")[1] == "flash-b"
    assert models.calls == ["flash-a", "flash-b", "flash-b"]
    assert len(slept) == 1  # only the last model in the chain waited before retrying
