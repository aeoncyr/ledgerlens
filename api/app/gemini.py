"""A thin wrapper around the Google Gen AI SDK.

Every call asks for JSON that matches a Pydantic schema. Readers and writers each work down their
own chain of models (``Settings.reader_models`` and ``writer_models``), so a busy or exhausted model
slows the demo instead of breaking it.

On the Gemini Developer API free tier each model has its own small quota: a few requests a minute
and a fixed number a day. The pacer keeps every model under its per-minute limit, spreads calls
across the chain, and skips a model for the rest of the day once its daily quota is spent.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import Counter, defaultdict, deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Literal, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import FREE_TIER_RPM, Settings, get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Role = Literal["read", "write"]

# Free-tier daily quotas reset at midnight Pacific time: 07:00 UTC while daylight saving lasts. If
# a model is retried an hour early after the change, it is simply marked exhausted again.
QUOTA_RESET_HOUR_UTC = 7

# A call that takes longer than this is abandoned for the next model in the chain.
CALL_TIMEOUT_SECONDS = {"read": 90.0, "write": 150.0}


class GeminiError(RuntimeError):
    """Raised when no model returned a valid structured answer."""


class GeminiQuotaExhausted(GeminiError):
    """Raised when every model in the chain has used up its free daily quota."""


def free_tier_rpm(model: str) -> int:
    return FREE_TIER_RPM["lite"] if "lite" in model else FREE_TIER_RPM["flash"]


def _next_reset(now: datetime) -> float:
    reset = now.replace(hour=QUOTA_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    if reset <= now:
        reset += timedelta(days=1)
    return reset.timestamp()


class ModelPacer:
    """Keeps each model under its requests-per-minute limit and out of use once its day is spent."""

    def __init__(
        self,
        rpm: Callable[[str], int | None],
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._rpm = rpm
        self._clock = clock
        self._sleep = sleep
        self._wall_clock = wall_clock
        self._starts: dict[str, deque[float]] = defaultdict(deque)
        self._exhausted_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def available(self, model: str) -> bool:
        return self._exhausted_until.get(model, 0) <= self._wall_clock().timestamp()

    def mark_exhausted(self, model: str) -> None:
        self._exhausted_until[model] = _next_reset(self._wall_clock())

    def _wait(self, model: str, now: float) -> float:
        limit = self._rpm(model)
        if limit is None:
            return 0.0
        window = self._starts[model]
        while window and window[0] <= now - 60:
            window.popleft()
        return 0.0 if len(window) < limit else window[0] + 60 - now + 0.05

    async def acquire(self, chain: list[str]) -> str | None:
        """Reserve a call on whichever model in the chain is free soonest, preferring earlier ones.

        Returns None when every model in the chain has spent its daily quota.
        """
        while True:
            async with self._lock:
                candidates = [m for m in chain if self.available(m)]
                if not candidates:
                    return None
                now = self._clock()
                wait, _, model = min(
                    (self._wait(m, now), index, m) for index, m in enumerate(candidates)
                )
                if wait <= 0:
                    self._starts[model].append(now)
                    return model
            await self._sleep(wait)


def _is_overloaded(exc: Exception) -> bool:
    """A model that is busy right now; another model in the chain may well not be."""
    text = str(exc)
    return isinstance(exc, TimeoutError) or "503" in text or "UNAVAILABLE" in text


def _is_daily_quota(exc: Exception) -> bool:
    text = str(exc)
    return ("429" in text or "RESOURCE_EXHAUSTED" in text) and "PerDay" in text


def _backoff(exc: Exception, attempt: int) -> float:
    """Wait longer when the quota is exhausted (429): it clears in seconds, not milliseconds."""
    exhausted = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
    base = 4.0 if exhausted else 0.5
    return base * 2**attempt + random.uniform(0, base)


class Gemini:
    def __init__(
        self,
        settings: Settings,
        client: genai.Client | None = None,
        pacer: ModelPacer | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._client = client or _client_for(settings)
        self._pacer = pacer or ModelPacer(free_tier_rpm if settings.uses_free_tier else _no_limit)
        self._sleep = sleep

    async def generate(
        self,
        *,
        contents: Any,
        schema: type[T],
        system: str,
        temperature: float = 0.0,
        attempts: int = 3,
        role: Role = "read",
    ) -> tuple[T, str]:
        """Return the parsed answer and the model that produced it."""
        thinking = self._settings.writer_thinking if role == "write" else None
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=(
                types.ThinkingConfig(thinking_level=types.ThinkingLevel(thinking.upper()))
                if thinking
                else None
            ),
        )
        chain = self._settings.reader_models if role == "read" else self._settings.writer_models
        remaining = list(chain)
        failures: Counter[str] = Counter()
        last_error: Exception | None = None
        while remaining:
            model = await self._pacer.acquire(remaining)
            if model is None:
                raise GeminiQuotaExhausted(
                    "Gemini's free daily quota is used up for every model; it resets at "
                    "midnight Pacific time"
                ) from last_error
            try:
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=model, contents=contents, config=config
                    ),
                    timeout=CALL_TIMEOUT_SECONDS[role],
                )
                if isinstance(response.parsed, schema):
                    return response.parsed, model
                raise GeminiError(f"{model} returned output that does not match the schema")
            except GeminiError as exc:
                last_error = exc
                failures[model] += 1
            except Exception as exc:  # network errors, quota, server errors
                last_error = exc
                if _is_daily_quota(exc):
                    log.warning("%s has used its daily quota; moving down the chain", model)
                    self._pacer.mark_exhausted(model)
                    continue
                if _is_overloaded(exc) and len(remaining) > 1:
                    log.warning("%s is busy or slow (%r); trying the next model", model, exc)
                    remaining.remove(model)
                    continue
                failures[model] += 1
                log.warning(
                    "Gemini call failed (model=%s, try %d): %s", model, failures[model], exc
                )
            if failures[model] >= attempts:
                remaining.remove(model)
            else:
                await self._sleep(_backoff(last_error, failures[model] - 1))
        raise GeminiError("All Gemini models failed") from last_error


def _no_limit(model: str) -> None:
    return None


def _client_for(settings: Settings) -> genai.Client:
    if settings.gemini_api_key:
        return genai.Client(enterprise=False, api_key=settings.gemini_api_key)
    return genai.Client(
        enterprise=True, project=settings.project or None, location=settings.location
    )


@lru_cache
def get_gemini() -> Gemini:
    return Gemini(get_settings())
