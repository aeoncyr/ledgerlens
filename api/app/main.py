"""LedgerLens API entry point. Cloud Run starts it with ``uvicorn app.main:app``."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import integrations
from app.config import get_settings
from app.routers import (
    activity,
    analysis,
    applications,
    decisions,
    demo,
    exports,
    health,
    invites,
    lender,
    owner,
    pilot,
    pilot_requests,
    policy,
    readings,
)


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
    app.include_router(decisions.router)
    app.include_router(analysis.router)
    app.include_router(owner.router)
    app.include_router(readings.router)
    app.include_router(exports.router)
    app.include_router(demo.router)
    app.include_router(pilot_requests.router)
    app.include_router(pilot.router)
    app.include_router(activity.router)
    app.include_router(integrations.router)
    app.include_router(lender.router)
    app.include_router(policy.router)
    app.include_router(invites.router)
    integrations.register(app)
    return app


app = create_app()
