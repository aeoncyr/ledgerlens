"""Send each step of a loan to the lender's own tools: a Google Sheet or any webhook.

Many BPRs and koperasi keep their loan book in a spreadsheet, so the officer pastes the address of
a small Apps Script web app (or a Zapier, Make or n8n webhook) once, and every decision, offer and
condition is posted there as JSON. Settings live in ``lenders/{uid}``, keyed by the officer.

The API posts to an address a user typed, so the request is guarded against reaching our own
network (SSRF): https only, the host is resolved and every address must be public, the connection
goes to the address that was checked, redirects are not followed and nothing waits longer than
five seconds. A failed delivery is logged and never breaks the loan flow.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from google.cloud import firestore
from pydantic import Field

from app import events
from app.auth import User, current_user
from app.config import get_settings
from app.schemas import CamelModel
from app.store import get_firestore

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lender", tags=["integrations"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

TIMEOUT_SECONDS = 5.0
RECENT_DELIVERIES = 10
TESTS_PER_DAY = 20
BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal"}

Kind = Literal["sheets", "generic"]


# --- The SSRF guard ------------------------------------------------------------------------------


class UnsafeUrl(ValueError):
    """The address is not one LedgerLens will post to; the message says why, in plain words."""


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def check_shape(url: str, kind: Kind = "generic") -> str:
    """Check the address without touching the network; return its host name."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise UnsafeUrl("That is not a web address.") from exc
    if parts.scheme != "https":
        raise UnsafeUrl("The address must start with https://")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeUrl("The address has no host name.")
    if parts.username or parts.password:
        raise UnsafeUrl("Leave the user name and password out of the address.")
    if port not in (None, 443):
        raise UnsafeUrl("Only the standard https port (443) is allowed.")
    if host in BLOCKED_HOSTS or host.endswith((".internal", ".local", ".localhost")):
        raise UnsafeUrl("That address points inside a private network.")
    if kind == "sheets" and not (
        host == "script.google.com"
        and parts.path.startswith("/macros/")
        and parts.path.endswith("/exec")
    ):
        raise UnsafeUrl(
            "A Google Sheets address starts with https://script.google.com/macros/ and ends in "
            "/exec. Copy the Web app URL that Deploy shows, not the editor's address."
        )
    return host


async def resolve_public(host: str) -> str:
    """Resolve the host and return one address to connect to, if every address is public."""
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeUrl("That host name does not exist.") from exc
        addresses = list(dict.fromkeys(str(info[4][0]) for info in infos))
    if not addresses:
        raise UnsafeUrl("That host name does not exist.")
    # A name with one private address among public ones is refused as a whole.
    if not all(_public(address) for address in addresses):
        raise UnsafeUrl("That address points inside a private network.")
    return addresses[0]


# --- Delivery ------------------------------------------------------------------------------------


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def post_json(
    url: str, body: dict[str, Any], *, kind: Kind = "generic", secret: str | None = None
) -> dict[str, Any]:
    """Post the body to the address and describe what happened. Never raises."""
    started = time.monotonic()
    result: dict[str, Any] = {"ok": False, "status": None, "error": None}
    try:
        host = check_shape(url, kind)
        address = await resolve_public(host)
        parts = urlsplit(url.strip())
        # Connect to the address that was checked, so DNS can't change between check and use;
        # TLS still verifies the certificate against the real host name.
        netloc = f"[{address}]" if ":" in address else address
        pinned = urlunsplit(("https", netloc, parts.path or "/", parts.query, ""))
        content = json.dumps(body, ensure_ascii=False, default=str).encode()
        headers = {
            "Host": host,
            "Content-Type": "application/json",
            "User-Agent": "LedgerLens-Webhook/1",
        }
        if secret:
            headers["X-LedgerLens-Signature"] = sign(secret, content)
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, follow_redirects=False, trust_env=False
        ) as client:
            response = await client.post(
                pinned, content=content, headers=headers, extensions={"sni_hostname": host}
            )
        result["status"] = response.status_code
        # Apps Script runs doPost, then answers with a redirect to where its reply is served.
        redirected = response.is_redirect and kind == "sheets"
        result["ok"] = response.is_success or redirected
        if not result["ok"]:
            result["error"] = f"The receiver answered {response.status_code}."
    except UnsafeUrl as exc:
        result["error"] = str(exc)
    except httpx.TimeoutException:
        result["error"] = "The receiver took longer than five seconds to answer."
    except Exception as exc:  # network errors, TLS failures; never into the loan flow
        log.warning("webhook delivery failed: %s", exc)
        result["error"] = "Could not reach the receiver."
    result["ms"] = round((time.monotonic() - started) * 1000)
    return result


def _number(source: dict[str, Any] | None, *keys: str) -> Any:
    for key in keys:
        if source and source.get(key) is not None:
            return source[key]
    return None


def webhook_body(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    """The JSON a receiver gets: flat columns a spreadsheet can append, plus the full event."""
    offer = payload.get("offer") or {}
    application_id = payload.get("applicationId")
    base = get_settings().public_app_url.rstrip("/")
    return {
        "event": event,
        "sentAt": datetime.now(UTC).isoformat(),
        "at": payload.get("at"),
        "applicationId": application_id,
        "alias": payload.get("alias"),
        "action": payload.get("action"),
        "reason": payload.get("reason"),
        "amountRp": _number(offer, "amountRp", "amount_rp"),
        "tenorMonths": _number(offer, "tenorMonths", "tenor_months"),
        "annualRatePct": _number(offer, "annualRatePct", "annual_rate_pct"),
        "instalmentRp": _number(offer, "instalmentRp", "instalment_rp"),
        "link": f"{base}/app/{application_id}" if application_id else base,
        "data": {k: v for k, v in payload.items() if k != "officerUid"},
    }


SAMPLE_EVENT = {
    "applicationId": "sample",
    "alias": "Warung Contoh (test)",
    "action": "approve",
    "reason": "A test from LedgerLens. You can delete this row.",
    "offer": {"amountRp": 10_000_000, "tenorMonths": 12, "annualRatePct": 6.0},
}


async def _log_delivery(
    db: firestore.AsyncClient, uid: str, event: str, application_id: Any, result: dict[str, Any]
) -> dict[str, Any]:
    entry = {
        "event": event,
        "applicationId": application_id,
        "ok": result["ok"],
        "status": result["status"],
        "error": result["error"],
        "ms": result.get("ms"),
        "at": datetime.now(UTC).isoformat(),
    }
    lender = db.collection("lenders").document(uid)
    await lender.collection("deliveries").document().set(entry)
    snapshot = await lender.get()
    if snapshot.exists:
        recent = (snapshot.to_dict() or {}).get("recentDeliveries", [])
        await lender.update({"recentDeliveries": [entry, *recent][:RECENT_DELIVERIES]})
    return entry


async def deliver(event: str, payload: dict[str, Any]) -> None:
    """The listener on every LedgerLens event: post it to the officer's webhook, if they set one."""
    uid = payload.get("officerUid")
    if not uid:
        return
    db = _firestore()
    snapshot = await db.collection("lenders").document(uid).get()
    settings = (snapshot.to_dict() or {}) if snapshot.exists else {}
    url = settings.get("webhookUrl")
    if not url:
        return
    kind = settings.get("kind", "generic")
    result = await post_json(
        url, webhook_body(event, payload), kind=kind, secret=settings.get("secret")
    )
    await _log_delivery(db, uid, event, payload.get("applicationId"), result)


_app: FastAPI | None = None


def _firestore() -> firestore.AsyncClient:
    # The listener runs outside a request, so it resolves Firestore as the routes do, including
    # any override the app has (the tests' in-memory Firestore).
    overrides = _app.dependency_overrides if _app else {}
    return overrides.get(get_firestore, get_firestore)()


def register(app: FastAPI) -> None:
    """Listen to LedgerLens events; called when the app is created."""
    global _app
    _app = app
    if deliver not in events.LISTENERS:
        events.LISTENERS.append(deliver)


# --- Settings routes -----------------------------------------------------------------------------


class LenderSettingsIn(CamelModel):
    webhook_url: str | None = Field(
        default=None, max_length=2048, description="Empty to stop sending"
    )
    kind: Kind = "sheets"


class Delivery(CamelModel):
    event: str
    application_id: str | None = None
    ok: bool
    status: int | None = None
    error: str | None = None
    ms: int | None = None
    at: str


class LenderSettingsOut(CamelModel):
    webhook_url: str | None = None
    kind: Kind = "sheets"
    secret: str | None = Field(
        default=None, description="Signs each delivery (X-LedgerLens-Signature, HMAC-SHA256)"
    )
    recent_deliveries: list[Delivery] = Field(default_factory=list)


def _settings_out(data: dict[str, Any]) -> LenderSettingsOut:
    return LenderSettingsOut(
        webhook_url=data.get("webhookUrl"),
        kind=data.get("kind", "sheets"),
        secret=data.get("secret"),
        recent_deliveries=data.get("recentDeliveries", []),
    )


@router.get("/settings", response_model=LenderSettingsOut)
async def get_lender_settings(user: CurrentUser, db: Db) -> LenderSettingsOut:
    snapshot = await db.collection("lenders").document(user.uid).get()
    return _settings_out((snapshot.to_dict() or {}) if snapshot.exists else {})


@router.put("/settings", response_model=LenderSettingsOut)
async def put_lender_settings(
    body: LenderSettingsIn, user: CurrentUser, db: Db
) -> LenderSettingsOut:
    url = (body.webhook_url or "").strip() or None
    if url:
        try:
            await resolve_public(check_shape(url, body.kind))
        except UnsafeUrl as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    ref = db.collection("lenders").document(user.uid)
    snapshot = await ref.get()
    data = (snapshot.to_dict() or {}) if snapshot.exists else {}
    data.update(
        {
            "webhookUrl": url,
            "kind": body.kind,
            "secret": data.get("secret") or secrets.token_urlsafe(24),
            "updatedAt": datetime.now(UTC).isoformat(),
        }
    )
    await ref.set(data)
    return _settings_out(data)


@router.post("/test", response_model=Delivery)
async def send_test(user: CurrentUser, db: Db) -> Delivery:
    """Send a sample event to the saved address, so the officer sees a row arrive."""
    ref = db.collection("lenders").document(user.uid)
    snapshot = await ref.get()
    data = (snapshot.to_dict() or {}) if snapshot.exists else {}
    if not data.get("webhookUrl"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Save an address first")
    today = datetime.now(UTC).date().isoformat()
    tests = data.get("tests") or {}
    count = tests.get("count", 0) if tests.get("date") == today else 0
    if count >= TESTS_PER_DAY:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "That is enough test rows for today."
        )
    await ref.update({"tests": {"date": today, "count": count + 1}})
    payload = {**SAMPLE_EVENT, "officerUid": user.uid, "at": datetime.now(UTC).isoformat()}
    result = await post_json(
        data["webhookUrl"],
        webhook_body("test", payload),
        kind=data.get("kind", "generic"),
        secret=data.get("secret"),
    )
    entry = await _log_delivery(db, user.uid, "test", None, result)
    return Delivery.model_validate(entry)
