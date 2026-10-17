"""Pilot requests from the public "For lenders" page: validation, storage and daily limits."""

from app.routers import pilot

REQUEST = {
    "lenderName": "BPR Contoh Sejahtera",
    "lenderType": "bpr",
    "province": "Jawa Barat",
    "filesPerMonth": 40,
    "contactName": "Ibu Contoh",
    "email": "kredit@example.com",
    "consent": True,
}


def _requests(fake_db) -> dict[str, dict]:
    return fake_db.docs_in("pilotRequests")


def test_a_request_is_stored_with_its_consent(client, fake_db):
    response = client.post("/api/pilot-requests", json=REQUEST)
    assert response.status_code == 201
    body = response.json()
    assert body["replyBy"] == "email"
    saved = _requests(fake_db)[body["id"]]
    assert saved["lenderName"] == "BPR Contoh Sejahtera"
    assert saved["lenderType"] == "bpr"
    assert saved["filesPerMonth"] == 40
    assert saved["email"] == "kredit@example.com"
    assert saved["whatsapp"] is None
    assert saved["consent"] == {"given": True, "text": pilot.CONSENT_TEXT}
    assert saved["uid"] == "judge-1"
    assert saved["status"] == "new"


def test_a_whatsapp_number_alone_is_enough(client, fake_db):
    request = {**REQUEST, "email": "", "whatsapp": "+62 812-3456-7890"}
    response = client.post("/api/pilot-requests", json=request)
    assert response.status_code == 201
    assert response.json()["replyBy"] == "whatsapp"
    (saved,) = _requests(fake_db).values()
    assert saved["email"] is None
    assert saved["whatsapp"] == "+62 812-3456-7890"


def test_a_request_needs_the_consent_box(client, fake_db):
    response = client.post("/api/pilot-requests", json={**REQUEST, "consent": False})
    assert response.status_code == 422
    assert "tick the box" in response.json()["detail"]
    assert _requests(fake_db) == {}


def test_a_request_needs_a_way_to_reply(client, fake_db):
    response = client.post("/api/pilot-requests", json={**REQUEST, "email": "  "})
    assert response.status_code == 422
    assert "email address or a WhatsApp number" in response.json()["detail"]
    assert _requests(fake_db) == {}


def test_a_malformed_contact_is_refused_in_plain_words(client):
    bad_email = client.post("/api/pilot-requests", json={**REQUEST, "email": "kredit@"})
    assert bad_email.status_code == 422
    assert "doesn't look complete" in bad_email.json()["detail"]
    bad_number = client.post(
        "/api/pilot-requests", json={**REQUEST, "email": None, "whatsapp": "call me"}
    )
    assert bad_number.status_code == 422
    assert "WhatsApp number" in bad_number.json()["detail"]


def test_an_unknown_lender_type_is_refused(client):
    response = client.post("/api/pilot-requests", json={**REQUEST, "lenderType": "bank"})
    assert response.status_code == 422


def test_a_visitor_can_send_only_a_few_requests_a_day(client, fake_db):
    for _ in range(pilot.REQUESTS_PER_USER_PER_DAY):
        assert client.post("/api/pilot-requests", json=REQUEST).status_code == 201
    response = client.post("/api/pilot-requests", json=REQUEST)
    assert response.status_code == 429
    assert "no need to send it again" in response.json()["detail"]
    assert len(_requests(fake_db)) == pilot.REQUESTS_PER_USER_PER_DAY


def test_the_site_has_a_daily_limit(client_as, fake_db, monkeypatch):
    monkeypatch.setattr(pilot, "REQUESTS_PER_DAY", 2)
    assert client_as("lender-a").post("/api/pilot-requests", json=REQUEST).status_code == 201
    assert client_as("lender-b").post("/api/pilot-requests", json=REQUEST).status_code == 201
    response = client_as("lender-c").post("/api/pilot-requests", json=REQUEST)
    assert response.status_code == 429
    assert len(_requests(fake_db)) == 2


def test_a_refused_request_is_not_counted(client, fake_db):
    client.post("/api/pilot-requests", json={**REQUEST, "consent": False})
    usage = fake_db.docs_in("usage")
    assert usage == {}


def test_a_request_needs_a_signed_in_browser(anonymous_client):
    assert anonymous_client.post("/api/pilot-requests", json=REQUEST).status_code == 401
