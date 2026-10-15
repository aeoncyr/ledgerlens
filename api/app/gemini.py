"""A thin wrapper around the Google Gen AI SDK.

Every call asks for JSON that matches a Pydantic schema, retries with backoff, and falls back to a
second model if the main one keeps failing, so a busy model slows the demo instead of breaking it.
"""

from __future__ import annotations

import asyncio
import logging
import random
from functools import lru_cache
from typing import Any, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiError(RuntimeError):
    """Raised when no model returned a valid structured answer."""


class Gemini:
    def __init__(self, settings: Settings, client: genai.Client | None = None) -> None:
        self._settings = settings
        self._client = client or _client_for(settings)

    async def generate(
        self,
        *,
        contents: Any,
        schema: type[T],
        system: str,
        temperature: float = 0.0,
        attempts: int = 4,
    ) -> tuple[T, str]:
        """Return the parsed answer and the model that produced it."""
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )
        last_error: Exception | None = None
        for model in (self._settings.model_main, self._settings.model_fallback):
            for attempt in range(attempts):
                try:
                    response = await self._client.aio.models.generate_content(
                        model=model, contents=contents, config=config
                    )
                    if isinstance(response.parsed, schema):
                        return response.parsed, model
                    raise GeminiError(f"{model} returned output that does not match the schema")
                except Exception as exc:  # network errors, quota, invalid output
                    last_error = exc
                    log.warning(
                        "Gemini call failed (model=%s, attempt=%d): %s", model, attempt, exc
                    )
                    await asyncio.sleep(_backoff(exc, attempt))
        raise GeminiError("All Gemini models failed") from last_error


def _client_for(settings: Settings) -> genai.Client:
    if settings.gemini_api_key:
        return genai.Client(enterprise=False, api_key=settings.gemini_api_key)
    return genai.Client(
        enterprise=True, project=settings.project or None, location=settings.location
    )


def _backoff(exc: Exception, attempt: int) -> float:
    """Wait longer when the quota is exhausted (429): it clears in seconds, not milliseconds."""
    exhausted = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
    base = 4.0 if exhausted else 0.5
    return base * 2**attempt + random.uniform(0, base)


@lru_cache
def get_gemini() -> Gemini:
    return Gemini(get_settings())
