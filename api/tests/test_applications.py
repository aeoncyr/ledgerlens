import pytest

NEW_APPLICATION = {
    "alias": "Warung Bu Sari",
    "businessType": "grocery stall",
    "city": "Bekasi",
    "yearsOperating": 6,
    "amount": 10_000_000,
    "tenorMonths": 12,
}


def evidence(application_id, **overrides):
    body = {
        "type": "qris_history",
        "storagePath": f"evidence/{application_id}/judge-1/qris-1.png",
        "capturedAt": "2026-10-15T09:30:00+07:00",
        "gps": {"lat": -6.24, "lng": 106.99},
    }
    return {**body, **overrides}


@pytest.fixture
def application_id(client):
    response = client.post("/api/applications", json=NEW_APPLICATION)
    assert response.status_code == 201
    return response.json()["applicationId"]


def give_consent(client, application_id, given=True):
    return client.post(
        f"/api/applications/{application_id}/consent",
        json={"consentVersion": "1.0", "given": given},
    )


def test_creates_a_draft_owned_by_the_officer(client, fake_db, application_id):
    stored = fake_db.docs_in("applications")[application_id]

    assert stored["status"] == "draft"
    assert stored["officerUid"] == "judge-1"
    assert stored["business"]["alias"] == "Warung Bu Sari"
    assert stored["request"] == {"amount": 10_000_000, "tenorMonths": 12}
    audit = fake_db.docs_in("applications", application_id, "audit")
    assert [entry["action"] for entry in audit.values()] == ["created"]


def test_consent_moves_the_application_to_collecting(client, fake_db, application_id):
    assert give_consent(client, application_id).status_code == 204

    stored = fake_db.docs_in("applications")[application_id]
    assert stored["status"] == "collecting"
    assert stored["consent"]["given"] is True
    assert stored["consent"]["version"] == "1.0"


def test_evidence_needs_consent_first(client, application_id):
    response = client.post(
        f"/api/applications/{application_id}/evidence", json=evidence(application_id)
    )

    assert response.status_code == 409


def test_registers_evidence_with_its_tier(client, fake_db, application_id):
    give_consent(client, application_id)

    response = client.post(
        f"/api/applications/{application_id}/evidence", json=evidence(application_id)
    )

    assert response.status_code == 201
    evidence_id = response.json()["evidenceId"]
    stored = fake_db.docs_in("applications", application_id, "evidence")[evidence_id]
    assert stored["type"] == "qris_history"
    assert stored["tier"] == "hard"
    assert stored["gps"] == {"lat": -6.24, "lng": 106.99}


def test_evidence_must_live_under_its_application(client, application_id):
    give_consent(client, application_id)

    response = client.post(
        f"/api/applications/{application_id}/evidence",
        json=evidence(application_id, storagePath="evidence/someone-else/qris.png"),
    )

    assert response.status_code == 422


def test_evidence_must_be_in_the_officers_own_folder(client, application_id):
    give_consent(client, application_id)

    response = client.post(
        f"/api/applications/{application_id}/evidence",
        json=evidence(application_id, storagePath=f"evidence/{application_id}/other-uid/q.png"),
    )

    assert response.status_code == 422


def test_other_officers_cannot_see_the_application(client_as, application_id):
    other = client_as("another-officer")

    response = give_consent(other, application_id)

    assert response.status_code == 404


def test_decision_needs_an_analysed_application(client, application_id):
    response = client.post(
        f"/api/applications/{application_id}/decision",
        json={"action": "approve", "reason": "Cash flow supports the instalment"},
    )

    assert response.status_code == 409


def test_decision_is_recorded_with_its_reason(client, fake_db, application_id):
    fake_db.docs[("applications", application_id)]["status"] = "ready"

    response = client.post(
        f"/api/applications/{application_id}/decision",
        json={"action": "request_more", "reason": "Ask for three months of supplier receipts"},
    )

    assert response.status_code == 204
    stored = fake_db.docs_in("applications")[application_id]
    assert stored["status"] == "collecting"
    assert stored["decision"]["reason"] == "Ask for three months of supplier receipts"
    actions = [
        e["action"] for e in fake_db.docs_in("applications", application_id, "audit").values()
    ]
    assert actions[-1] == "decision_request_more"
