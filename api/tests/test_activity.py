"""Who opened my file: the owner's timeline, read from the audit log through an allowlist."""

from datetime import UTC, datetime, timedelta

import pytest

from app.routers.activity import OWNER_EVENTS, owner_timeline
from tests.test_decisions import (
    APPROVE,
    FILE,
    recommend,
)

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def owner(client_as):
    return client_as("owner-1")


@pytest.fixture
def officer(client_as):
    return client_as("officer-1")


@pytest.fixture
def reviewer(client_as):
    return client_as("reviewer-1")


@pytest.fixture
def file_id(owner, officer, fake_db):
    """An owner's file, shared with the officer, checked and ready for a decision."""
    file_id = owner.post("/api/owner/files", json=FILE).json()["applicationId"]
    owner.post(f"/api/applications/{file_id}/consent", json={"consentVersion": "v1", "given": True})
    code = owner.post(f"/api/applications/{file_id}/share").json()["shareCode"]
    officer.post(f"/api/shared/{code}")
    fake_db.docs[("applications", file_id)]["status"] = "ready"
    fake_db.docs[("applications", file_id, "memo", "current")] = {
        "policy": {"maxInstallment": 2_000_000}
    }
    return file_id


def events_of(client, file_id):
    response = client.get(f"/api/applications/{file_id}/activity")
    assert response.status_code == 200, response.text
    return response.json()["events"]


def test_the_owner_sees_who_opened_and_decided_on_their_file(
    owner, officer, reviewer, fake_db, file_id
):
    body = {**APPROVE, "assessmentAgreed": False, "disagreementReason": "Internal: shop visited."}
    code = recommend(officer, file_id, body)["signoffCode"]
    reviewer.post(f"/api/signoff/{code}")
    reviewer.post(
        f"/api/applications/{file_id}/signoff", json={"approve": True, "note": "Internal note"}
    )

    events = events_of(owner, file_id)

    assert [e["event"] for e in events] == [
        "started",
        "consent_given",
        "shared",
        "opened_by_lender",
        "decision_recommended",
        "signoff_opened",
        "signed_off",
        "sent_to_you",
    ]
    # Nothing internal leaves the log: no identities, reasons, notes or the officer's view.
    text = str(events)
    for secret in ("officer-1", "reviewer-1", "Internal", "assessment", "QRIS"):
        assert secret not in text
    assert set(events[0]) == {"event", "at", "count"}


def test_only_the_owner_can_read_the_timeline(officer, reviewer, client_as, file_id):
    assert officer.get(f"/api/applications/{file_id}/activity").status_code == 404
    assert client_as("stranger").get(f"/api/applications/{file_id}/activity").status_code == 404


def test_stopping_the_share_shows_on_the_timeline(owner, file_id):
    owner.delete(f"/api/applications/{file_id}/share")

    assert events_of(owner, file_id)[-1]["event"] == "share_stopped"


def test_the_timeline_is_oldest_first_and_folds_repeats():
    entries = [
        {"action": "condition_met", "at": T0 + timedelta(minutes=30)},
        {"action": "created_by_owner", "at": T0},
        {"action": "evidence_added", "at": T0 + timedelta(minutes=1)},
        {"action": "condition_met", "at": T0 + timedelta(minutes=20)},
        {"action": "assessment_disagreed", "at": T0 + timedelta(minutes=10)},
        {"action": "slik_recorded", "at": T0 + timedelta(minutes=11)},
        {"action": "invite_opened", "at": T0 + timedelta(minutes=2)},
    ]

    events = owner_timeline(entries)

    assert [(e.event, e.count) for e in events] == [
        ("started", 1),
        ("invite_opened", 1),
        ("condition_met", 2),
    ]
    assert events[-1].at == T0 + timedelta(minutes=30)


def test_internal_actions_are_not_on_the_allowlist():
    for internal in (
        "assessment_agreed",
        "assessment_disagreed",
        "slik_recorded",
        "policy_reapplied",
        "reading_confirmed",
        "follow_up_answered",
        "evidence_added",
    ):
        assert internal not in OWNER_EVENTS
