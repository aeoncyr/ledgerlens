"""Webhooks to the lender's own tools: the SSRF guard, the payload, settings and the listener."""

import asyncio
import hashlib
import hmac
import json
import socket

import httpx
import pytest

from app import events, integrations
from app.integrations import UnsafeUrl, check_shape, post_json, resolve_public, webhook_body

SHEETS_URL = "https://script.google.com/macros/s/AKfyc-example/exec"
PUBLIC_IP = "93.184.216.34"


def run(coro):
    return asyncio.run(coro)


# --- The guard -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/hook",
        "ftp://example.com/hook",
        "https://example.com:8443/hook",
        "https://user:pass@example.com/hook",
        "https://localhost/hook",
        "https://metadata.google.internal/computeMetadata/v1/",
        "https://anything.internal/hook",
        "https:///nohost",
        "not a url",
    ],
)
def test_the_shape_check_refuses_unsafe_addresses(url):
    with pytest.raises(UnsafeUrl):
        check_shape(url)


def test_a_sheets_address_must_be_an_apps_script_web_app():
    assert check_shape(SHEETS_URL, "sheets") == "script.google.com"
    with pytest.raises(UnsafeUrl, match="/exec"):
        check_shape("https://docs.google.com/spreadsheets/d/abc/edit", "sheets")
    with pytest.raises(UnsafeUrl):
        check_shape("https://script.google.com/home/projects/abc/edit", "sheets")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.5",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "ff02::1",
    ],
)
def test_private_and_metadata_addresses_are_refused(address):
    with pytest.raises(UnsafeUrl):
        run(resolve_public(address))


def test_a_public_literal_address_is_allowed():
    assert run(resolve_public("8.8.8.8")) == "8.8.8.8"


def fake_dns(monkeypatch, addresses):
    async def getaddrinfo(self, host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses]

    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", getaddrinfo)


def test_a_name_that_resolves_to_a_private_address_is_refused(monkeypatch):
    fake_dns(monkeypatch, [PUBLIC_IP, "10.0.0.7"])

    with pytest.raises(UnsafeUrl):
        run(resolve_public("rebind.example.com"))


def test_a_name_that_resolves_publicly_is_allowed(monkeypatch):
    fake_dns(monkeypatch, [PUBLIC_IP])

    assert run(resolve_public("hooks.example.com")) == PUBLIC_IP


# --- Delivery -------------------------------------------------------------------------------------


@pytest.fixture
def receiver(monkeypatch):
    """Answer every request with the given response, and keep the requests sent."""
    sent: list[httpx.Request] = []
    state = {"respond": lambda request: httpx.Response(200, json={"ok": True})}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return state["respond"](request)

    real_client = httpx.AsyncClient

    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["timeout"] == 5.0
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    async def resolved(host):
        return PUBLIC_IP

    monkeypatch.setattr(integrations.httpx, "AsyncClient", client)
    monkeypatch.setattr(integrations, "resolve_public", resolved)
    return sent, state


def test_posts_to_the_checked_address_with_a_signature(receiver):
    sent, _ = receiver
    body = {"event": "test", "alias": "Warung Contoh"}

    result = run(post_json("https://hooks.example.com/in?x=1", body, secret="s3cret"))

    assert result["ok"] is True and result["status"] == 200
    request = sent[0]
    assert request.url.host == PUBLIC_IP
    assert request.url.query == b"x=1"
    assert request.headers["host"] == "hooks.example.com"
    assert request.extensions["sni_hostname"] == "hooks.example.com"
    expected = hmac.new(b"s3cret", request.content, hashlib.sha256).hexdigest()
    assert request.headers["x-ledgerlens-signature"] == f"sha256={expected}"
    assert json.loads(request.content) == body


def test_a_redirect_is_not_followed(receiver):
    sent, state = receiver
    state["respond"] = lambda r: httpx.Response(302, headers={"Location": "https://10.0.0.1/"})

    generic = run(post_json("https://hooks.example.com/in", {}))
    sheets = run(post_json(SHEETS_URL, {}, kind="sheets"))

    assert len(sent) == 2
    assert generic["ok"] is False and generic["status"] == 302
    # Apps Script answers every doPost with a redirect to its reply; the row is already added.
    assert sheets["ok"] is True


def test_failures_are_reported_never_raised(receiver):
    _, state = receiver

    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    state["respond"] = slow
    assert "five seconds" in run(post_json("https://hooks.example.com/in", {}))["error"]

    def broken(request):
        raise httpx.ConnectError("refused", request=request)

    state["respond"] = broken
    assert run(post_json("https://hooks.example.com/in", {}))["ok"] is False
    assert "https" in run(post_json("http://hooks.example.com/in", {}))["error"]


def test_the_payload_has_flat_columns_and_the_full_event():
    payload = {
        "applicationId": "app-1",
        "officerUid": "officer-1",
        "alias": "Warung Bu Sari",
        "at": "2026-10-17T09:00:00+07:00",
        "action": "approve",
        "reason": "Cash flow supports it",
        "offer": {
            "amountRp": 10_000_000,
            "tenorMonths": 12,
            "annualRatePct": 6.0,
            "instalmentRp": 860_664,
        },
    }

    body = webhook_body("decision.final", payload)

    assert body["event"] == "decision.final"
    assert body["alias"] == "Warung Bu Sari"
    assert (body["amountRp"], body["tenorMonths"], body["instalmentRp"]) == (
        10_000_000,
        12,
        860_664,
    )
    assert body["link"].endswith("/app/app-1")
    assert "officerUid" not in body["data"]
    assert body["data"]["offer"]["annualRatePct"] == 6.0


def test_an_event_without_an_offer_leaves_the_amount_empty():
    body = webhook_body("condition.met", {"applicationId": "a", "index": 0, "text": "KTP copy"})

    assert body["amountRp"] is None and body["action"] is None
    assert body["data"]["text"] == "KTP copy"


# --- Settings routes ------------------------------------------------------------------------------


@pytest.fixture
def public_dns(monkeypatch):
    async def resolved(host):
        return PUBLIC_IP

    monkeypatch.setattr(integrations, "resolve_public", resolved)


def test_settings_need_a_signed_in_user(anonymous_client):
    assert anonymous_client.get("/api/lender/settings").status_code == 401
    assert anonymous_client.put("/api/lender/settings", json={}).status_code == 401
    assert anonymous_client.post("/api/lender/test").status_code == 401


def test_settings_are_saved_per_officer(client_as, fake_db, public_dns):
    officer, other = client_as("officer-1"), client_as("officer-2")

    saved = officer.put(
        "/api/lender/settings", json={"webhookUrl": SHEETS_URL, "kind": "sheets"}
    ).json()

    assert saved["webhookUrl"] == SHEETS_URL and saved["secret"]
    assert fake_db.docs[("lenders", "officer-1")]["kind"] == "sheets"
    assert other.get("/api/lender/settings").json()["webhookUrl"] is None
    again = officer.put("/api/lender/settings", json={"webhookUrl": "", "kind": "sheets"}).json()
    assert again["webhookUrl"] is None and again["secret"] == saved["secret"]


def test_unsafe_addresses_are_refused_with_a_reason(client):
    response = client.put(
        "/api/lender/settings",
        json={"webhookUrl": "https://169.254.169.254/latest/meta-data", "kind": "generic"},
    )

    assert response.status_code == 422
    assert "private network" in response.json()["detail"]


def test_a_test_needs_a_saved_address(client):
    assert client.post("/api/lender/test").status_code == 409


def test_a_test_is_sent_and_logged(client, fake_db, public_dns, monkeypatch):
    client.put(
        "/api/lender/settings",
        json={"webhookUrl": "https://hooks.example.com/in", "kind": "generic"},
    )
    sent = []

    async def fake_post(url, body, *, kind, secret):
        sent.append(body)
        return {"ok": True, "status": 200, "error": None, "ms": 12}

    monkeypatch.setattr(integrations, "post_json", fake_post)

    response = client.post("/api/lender/test")

    assert response.status_code == 200 and response.json()["ok"] is True
    assert sent[0]["event"] == "test" and sent[0]["alias"].endswith("(test)")
    assert fake_db.docs_in("lenders", "judge-1", "deliveries")
    recent = client.get("/api/lender/settings").json()["recentDeliveries"]
    assert recent[0]["event"] == "test"


# --- The listener ---------------------------------------------------------------------------------


def test_events_reach_the_officers_webhook(client, fake_db, public_dns, monkeypatch):
    client.put(
        "/api/lender/settings",
        json={"webhookUrl": "https://hooks.example.com/in", "kind": "generic"},
    )
    sent = []

    async def fake_post(url, body, *, kind, secret):
        sent.append((url, body))
        return {"ok": False, "status": 500, "error": "The receiver answered 500.", "ms": 3}

    monkeypatch.setattr(integrations, "post_json", fake_post)
    payload = {"applicationId": "app-1", "officerUid": "judge-1", "alias": "Warung A", "at": "t"}

    run(events.emit("offer.accepted", payload))
    run(events.emit("offer.accepted", {**payload, "officerUid": "no-settings"}))

    assert len(sent) == 1 and sent[0][1]["event"] == "offer.accepted"
    log = list(fake_db.docs_in("lenders", "judge-1", "deliveries").values())
    assert log[0]["ok"] is False and log[0]["applicationId"] == "app-1"


def test_a_broken_listener_never_breaks_the_caller(monkeypatch):
    async def broken(event, payload):
        raise RuntimeError("down")

    monkeypatch.setattr(events, "LISTENERS", [broken])

    run(events.emit("decision.final", {"officerUid": "x"}))
