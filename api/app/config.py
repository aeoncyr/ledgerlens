"""Runtime configuration, read once from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


# Gemini Developer API free tier, checked in AI Studio on 2026-10-15: Flash-Lite models allow 15
# requests a minute and 500 a day each; Flash models 5 a minute and 20 a day each.
FREE_READERS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
# Flash-Lite closes the writers' chain: when every Flash model is busy at once (seen on 2026-10-16),
# a lighter writer finishes the file instead of the whole check failing.
FREE_WRITERS = (
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    *FREE_READERS,
)
FREE_TIER_RPM = {"lite": 15, "flash": 5}


@dataclass(frozen=True)
class Settings:
    project: str
    location: str
    gemini_api_key: str | None
    reader_models: tuple[str, ...]
    writer_models: tuple[str, ...]
    writer_thinking: str | None
    model_strong: str | None
    storage_bucket: str | None
    cors_origins: list[str]
    rate_limit_per_minute: int
    runs_per_day: int
    runs_per_user_per_day: int
    max_parallel_calls: int
    ledger_double_read: bool
    public_app_url: str
    version: str
    # Demo stories (routers/demo.py) a day, per visitor and for the whole site. They cost no
    # Gemini call, but each writes a copy of a sample file to Firestore.
    demo_stories_per_user_per_day: int = 5
    demo_stories_per_day: int = 150

    @property
    def uses_free_tier(self) -> bool:
        """True when Gemini is reached with an AI Studio key rather than through Vertex AI."""
        return bool(self.gemini_api_key)

    @property
    def model_main(self) -> str:
        return self.writer_models[0]

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        api_key = env.get("GEMINI_API_KEY") or None
        main = env.get("MODEL_MAIN", "gemini-3.8-flash")
        fallback = env.get("MODEL_FALLBACK", "gemini-3.5-flash")
        return cls(
            project=env.get("GOOGLE_CLOUD_PROJECT", ""),
            # No Gemini model is served in Jakarta, so Gemini calls use the global endpoint.
            location=env.get("GOOGLE_CLOUD_LOCATION", "global"),
            # With a key, Gemini is reached through the Gemini Developer API (Google AI Studio),
            # whose free tier we use for the prototype (D-013); without one, through Vertex AI.
            gemini_api_key=api_key,
            # Readers make most of the calls and only transcribe; the verifier and memo writer
            # make two calls per analysis and do the reasoning. On the free tier every model has
            # its own daily quota, so each role works down a chain of models (D-014).
            reader_models=tuple(
                _split(env.get("READER_MODELS", ""))
                or (FREE_READERS if api_key else (main, fallback))
            ),
            writer_models=tuple(
                _split(env.get("WRITER_MODELS", ""))
                or (FREE_WRITERS if api_key else (main, fallback))
            ),
            # How hard the verifier and memo writer think before answering (minimal, low, medium,
            # high). On the free tier, high thinking over a whole case file takes minutes a call.
            writer_thinking=env.get("WRITER_THINKING") or ("low" if api_key else None),
            model_strong=env.get("MODEL_STRONG") or None,
            storage_bucket=env.get("STORAGE_BUCKET") or None,
            cors_origins=_split(env.get("CORS_ORIGINS", "http://localhost:5173")),
            rate_limit_per_minute=int(env.get("RATE_LIMIT_PER_MINUTE", "10")),
            # Analyses and re-checks a day, for the whole demo and for one visitor. The free tier's
            # writer models allow about 80 calls a day, two per run, so 35 leaves room for retries.
            runs_per_day=int(env.get("RUNS_PER_DAY", "35" if api_key else "500")),
            runs_per_user_per_day=int(env.get("RUNS_PER_USER_PER_DAY", "6")),
            # Calls are paced per model on the free tier; this only caps how many are in flight.
            max_parallel_calls=int(env.get("MAX_PARALLEL_CALLS", "4" if api_key else "8")),
            ledger_double_read=env.get("LEDGER_DOUBLE_READ", "true").lower() == "true",
            # Where the web app lives, for links in webhooks and exports.
            public_app_url=env.get("PUBLIC_APP_URL", "https://ledger-lens-511708.web.app"),
            version=env.get("APP_VERSION", "0.1.0"),
            demo_stories_per_user_per_day=int(env.get("DEMO_STORIES_PER_USER_PER_DAY", "5")),
            demo_stories_per_day=int(env.get("DEMO_STORIES_PER_DAY", "150")),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
