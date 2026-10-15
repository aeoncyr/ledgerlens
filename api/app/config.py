"""Runtime configuration, read once from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    project: str
    location: str
    gemini_api_key: str | None
    model_main: str
    model_fallback: str
    model_strong: str | None
    storage_bucket: str | None
    cors_origins: list[str]
    rate_limit_per_minute: int
    max_parallel_calls: int
    ledger_double_read: bool
    version: str

    @property
    def uses_free_tier(self) -> bool:
        """True when Gemini is reached with an AI Studio key rather than through Vertex AI."""
        return bool(self.gemini_api_key)

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        api_key = env.get("GEMINI_API_KEY") or None
        return cls(
            project=env.get("GOOGLE_CLOUD_PROJECT", ""),
            # No Gemini model is served in Jakarta, so Gemini calls use the global endpoint.
            location=env.get("GOOGLE_CLOUD_LOCATION", "global"),
            # With a key, Gemini is reached through the Gemini Developer API (Google AI Studio),
            # whose free tier we use for the prototype (D-013); without one, through Vertex AI.
            gemini_api_key=api_key,
            model_main=env.get("MODEL_MAIN", "gemini-3.8-flash"),
            # gemini-3.5-flash is not offered on the Developer API; 3.6 is, on the free tier too.
            model_fallback=env.get(
                "MODEL_FALLBACK", "gemini-3.6-flash" if api_key else "gemini-3.5-flash"
            ),
            model_strong=env.get("MODEL_STRONG") or None,
            storage_bucket=env.get("STORAGE_BUCKET") or None,
            cors_origins=_split(env.get("CORS_ORIGINS", "http://localhost:5173")),
            rate_limit_per_minute=int(env.get("RATE_LIMIT_PER_MINUTE", "10")),
            # The free tier allows only a few requests a minute, so make fewer calls at once.
            max_parallel_calls=int(env.get("MAX_PARALLEL_CALLS", "3" if api_key else "8")),
            ledger_double_read=env.get("LEDGER_DOUBLE_READ", "true").lower() == "true",
            version=env.get("APP_VERSION", "0.1.0"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
