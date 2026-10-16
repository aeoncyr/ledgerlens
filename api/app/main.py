"""LedgerLens API entry point. Cloud Run starts it with ``uvicorn app.main:app``."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analysis, applications, health, owner, readings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LedgerLens API",
        version=settings.version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(applications.router)
    app.include_router(analysis.router)
    app.include_router(owner.router)
    app.include_router(readings.router)
    return app


app = create_app()
