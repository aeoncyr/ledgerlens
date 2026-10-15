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
    model_main: str
    model_fallback: str
    model_strong: str | None
    storage_bucket: str | None
    cors_origins: list[str]
    rate_limit_per_minute: int
    version: str

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        return cls(
            project=env.get("GOOGLE_CLOUD_PROJECT", ""),
            # No Gemini model is served in Jakarta, so Gemini calls use the global endpoint.
            location=env.get("GOOGLE_CLOUD_LOCATION", "global"),
            model_main=env.get("MODEL_MAIN", "gemini-3.8-flash"),
            model_fallback=env.get("MODEL_FALLBACK", "gemini-3.5-flash"),
            model_strong=env.get("MODEL_STRONG") or None,
            storage_bucket=env.get("STORAGE_BUCKET") or None,
            cors_origins=_split(env.get("CORS_ORIGINS", "http://localhost:5173")),
            rate_limit_per_minute=int(env.get("RATE_LIMIT_PER_MINUTE", "10")),
            version=env.get("APP_VERSION", "0.1.0"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
