"""The demo story: one browser plays every role on a copy of a sample, and nowhere else."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.agents.decision_letter import DecisionLetter
from app.auth import ACT_AS_HEADER, User, firebase_user
from app.config import get_settings
from app.gemini import get_gemini
from app.main import create_app
from app.routers import demo
from app.store import get_firestore

OWNER = {ACT_AS_HEADER: "owner"}
OFFICER = {ACT_AS_HEADER: "officer"}
REVIEWER = {ACT_AS_HEADER: "reviewer"}

FILE = {
    "alias": "Warung Bu Sari",
    "businessType": "Grocery stall",
    "city": "Bekasi",
    "yearsOperating": 8,
    "amount": 15_000_000,
    "tenorMonths": 12,
}
APPROVE = {
    "action": "approve",
    "reason": "QRIS and supplier receipts support the notebook's sales.",
    "offer": {"amountRp": 15_000_000, "tenorMonths": 12, "annualRatePct": 6},
}


@pytest.fixture
def browser(fake_gemini, fake_db):
    """A client signed in as one user, whose role header goes through the real ``current_user``
    (the shared ``client_as`` fixture replaces it, and with it the header)."""

    def make(uid: str) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_gemini] = lambda: fake_gemini
        app.dependency_overrides[get_firestore] = lambda: fake_db
        app.dependency_overrides[firebase_user] = lambda: User(uid=uid, anonymous=True)
        return TestClient(app)

    return make


@pytest.fixture
def judge(browser):
    return browser("judge-1")


@pytest.fixture
def letter(fake_gemini):
    fake_gemini.reading = DecisionLetter(
        en="Your lender offers [[offer_amount]].",
        id="Pemberi pinjaman menawarkan [[offer_amount]].",
    )


def start(client, sample="bu-sari"):
    response = client.post("/api/demo/story", json={"sample": sample})
    assert response.status_code == 201, response.text
    return response.json()["applicationId"]


def application(fake_db, file_id):
    return fake_db.docs[("applications", file_id)]


def sign_off(client, file_id, headers=None):
    url = f"/api/applications/{file_id}/signoff"
    return client.post(url, json={"approve": True}, headers=headers)


def recommended(judge, file_id):
    """The judge shares the file as the owner, opens it as the officer and recommends approval."""
    code = judge.post(f"/api/applications/{file_id}/share", headers=OWNER).json()["shareCode"]
    assert judge.post(f"/api/shared/{code}", headers=OFFICER).status_code == 200
    response = judge.post(f"/api/applications/{file_id}/decision", json=APPROVE, headers=OFFICER)
    assert response.status_code == 200, response.text
    return response.json()["signoffCode"]


# --- Starting the story ---------------------------------------------------------------------------


def test_the_story_copies_a_finished_sample_without_calling_gemini(judge, fake_db, fake_gemini):
    file_id = start(judge)

    stored = application(fake_db, file_id)
    assert stored["demo"] is True and stored["demoSample"] == "bu-sari"
    assert (stored["ownerUid"], stored["officerUid"]) == ("judge-1", None)
    assert stored["business"]["alias"] == "Warung Bu Sari"
    assert stored["status"] == "ready" and stored["assessment"] == "verified"
    assert stored["consent"]["given"] is True

    evidence = fake_db.docs_in("applications", file_id, "evidence")
    assert len(evidence) == 17
    page = evidence["notebook-2026-08-1"]
    assert page["storagePath"] == "/samples/bu-sari/notebook-2026-08-1.webp"
    assert any(line["amountRp"] for line in page["extraction"]["lines"])

    memo = fake_db.docs[("applications", file_id, "memo", "current")]
    assert memo["policy"]["maxInstallment"] == 1_414_800
    assert memo["copiedFrom"] == "sample:bu-sari"
    assert ("applications", file_id, "memo", "context") in fake_db.docs
    summary = fake_db.docs[("applications", file_id, "owner", "summary")]
    assert summary["status"] == "ready" and summary["questions"]
    assert fake_gemini.calls == []


def test_a_sample_with_open_questions_starts_with_them(judge, fake_db):
    file_id = start(judge, "pak-hendra")

    assert application(fake_db, file_id)["status"] == "needs_follow_up"
    summary = fake_db.docs[("applications", file_id, "owner", "summary")]
    assert summary["status"] == "needs_answers"


def test_an_unknown_sample_is_refused(judge):
    assert judge.post("/api/demo/story", json={"sample": "pak-nobody"}).status_code == 404
    assert judge.post("/api/demo/story", json={"sample": "../config"}).status_code == 422


def test_starting_again_replaces_the_earlier_copy(judge, fake_db):
    first = start(judge)
    code = recommended(judge, first)

    second = start(judge)

    assert second != first
    assert ("applications", first) not in fake_db.docs
    assert fake_db.docs_in("applications", first, "evidence") == {}
    assert ("signoffs", code) not in fake_db.docs
    assert not [c for c, d in fake_db.docs_in("shares").items() if d["applicationId"] == first]
    assert fake_db.docs[("demoStories", "judge-1")] == {"bu-sari": second}


def test_a_visitor_has_a_daily_limit(judge, monkeypatch):
    limited = replace(get_settings(), demo_stories_per_user_per_day=2)
    monkeypatch.setattr(demo, "get_settings", lambda: limited)

    start(judge)
    start(judge, "pak-joko")

    refused = judge.post("/api/demo/story", json={"sample": "pak-hendra"})
    assert refused.status_code == 429
    assert "too many times today" in refused.json()["detail"]


def test_the_whole_site_has_a_daily_limit(browser, monkeypatch):
    limited = replace(get_settings(), demo_stories_per_day=1)
    monkeypatch.setattr(demo, "get_settings", lambda: limited)

    start(browser("judge-1"))

    assert browser("judge-2").post("/api/demo/story", json={"sample": "bu-sari"}).status_code == 429


# --- Playing every role ---------------------------------------------------------------------------


def test_one_browser_plays_the_whole_loop(judge, fake_db, fake_gemini, letter):
    file_id = start(judge)
    code = recommended(judge, file_id)

    assert judge.post(f"/api/signoff/{code}", headers=REVIEWER).status_code == 200
    assert application(fake_db, file_id)["reviewerUid"] == "judge-1"
    signed = sign_off(judge, file_id, REVIEWER)
    assert signed.status_code == 204, signed.text
    assert application(fake_db, file_id)["status"] == "decided"

    offer = f"/api/applications/{file_id}/offer"
    answered = judge.post(offer, json={"accept": True}, headers=OWNER)
    assert answered.status_code == 204, answered.text
    decision = fake_db.docs[("applications", file_id, "owner", "decision")]
    assert (decision["state"], decision["answeredBy"]) == ("accepted", "owner")
    assert len(fake_gemini.calls) == 1  # the owner's letter, and nothing else


def test_on_a_demo_file_each_step_needs_its_role(judge, fake_db, letter):
    file_id = start(judge)
    code = recommended(judge, file_id)
    judge.post(f"/api/signoff/{code}", headers=REVIEWER)

    # Without the supervisor's role the officer is the one calling, and can't sign off.
    assert sign_off(judge, file_id).status_code == 404
    assert sign_off(judge, file_id, REVIEWER).status_code == 204
    # The officer doesn't answer for an owner who is in the app.
    offer = f"/api/applications/{file_id}/offer"
    assert judge.post(offer, json={"accept": True}, headers=OFFICER).status_code == 403


def test_a_role_the_user_does_not_hold_is_ignored_on_a_demo_file(judge, browser, fake_db):
    file_id = start(judge)
    code = recommended(judge, file_id)

    # Before anyone claims the sign-off the judge is not the reviewer, so the claim falls back to
    # the judge's first role on the file, the officer's.
    assert sign_off(judge, file_id, REVIEWER).status_code == 404
    # Nobody else gets a role on someone's demo file by naming one.
    stranger = browser("stranger-1")
    assert stranger.post(f"/api/applications/{file_id}/share", headers=OWNER).status_code == 404
    assert stranger.post(f"/api/signoff/{code}", headers=REVIEWER).status_code == 200
    assert judge.post(f"/api/signoff/{code}", headers=REVIEWER).status_code == 409


def test_a_demo_file_is_never_checked_again(judge, fake_db, fake_gemini):
    from app.routers import analysis

    judge.app.dependency_overrides[analysis.get_evidence_store] = lambda: object()
    file_id = start(judge)

    for path in ("analyze", "reverify"):
        refused = judge.post(f"/api/applications/{file_id}/{path}", headers=OWNER)
        assert refused.status_code == 409
        assert "demo copy" in refused.json()["detail"]
    spoken = judge.post(
        f"/api/applications/{file_id}/findings/0/answer",
        json={"audioPath": f"evidence/{file_id}/judge-1/answer.webm"},
        headers=OWNER,
    )
    assert spoken.status_code == 409
    typed = judge.post(
        f"/api/applications/{file_id}/findings/0/answer",
        json={"text": "Boleh, nanti saya foto."},
        headers=OWNER,
    )
    assert typed.status_code == 204
    assert fake_gemini.calls == []


# --- Real files keep four eyes --------------------------------------------------------------------


@pytest.fixture
def real_file(browser, fake_db):
    """A real owner's file, shared with a real officer and ready for a decision."""
    owner, officer = browser("owner-1"), browser("officer-1")
    file_id = owner.post("/api/owner/files", json=FILE).json()["applicationId"]
    owner.post(f"/api/applications/{file_id}/consent", json={"consentVersion": "v1", "given": True})
    code = owner.post(f"/api/applications/{file_id}/share").json()["shareCode"]
    officer.post(f"/api/shared/{code}")
    fake_db.docs[("applications", file_id)]["status"] = "ready"
    fake_db.docs[("applications", file_id, "memo", "current")] = {
        "policy": {"maxInstallment": 2_000_000}
    }
    return file_id


def test_the_role_header_is_ignored_on_a_real_file(browser, fake_db, real_file):
    officer, owner = browser("officer-1"), browser("owner-1")

    # Naming a role the caller holds elsewhere, or none, changes nothing.
    decide = f"/api/applications/{real_file}/decision"
    assert owner.post(decide, json=APPROVE, headers=OFFICER).status_code == 404
    assert officer.post(f"/api/applications/{real_file}/share", headers=OWNER).status_code == 404


def test_the_header_does_not_split_one_person_on_a_real_file(browser, fake_db):
    """An owner who opens their own share link holds two roles on a real file, but the header
    never lets them act as the owner there: they are the officer, as before."""
    me = browser("owner-1")
    file_id = me.post("/api/owner/files", json=FILE).json()["applicationId"]
    me.post(f"/api/applications/{file_id}/consent", json={"consentVersion": "v1", "given": True})
    code = me.post(f"/api/applications/{file_id}/share").json()["shareCode"]
    me.post(f"/api/shared/{code}")
    assert application(fake_db, file_id)["officerUid"] == "owner-1"

    assert me.delete(f"/api/applications/{file_id}/share", headers=OWNER).status_code == 404


def test_a_real_file_still_needs_a_second_person(browser, fake_db, real_file):
    officer, owner = browser("officer-1"), browser("owner-1")
    code = officer.post(f"/api/applications/{real_file}/decision", json=APPROVE).json()[
        "signoffCode"
    ]

    for headers in ({}, REVIEWER):
        assert officer.post(f"/api/signoff/{code}", headers=headers).status_code == 409
        assert owner.post(f"/api/signoff/{code}", headers=headers).status_code == 403
    assert application(fake_db, real_file)["reviewerUid"] is None
    assert sign_off(officer, real_file, REVIEWER).status_code == 404


def test_a_real_file_cannot_be_turned_into_a_demo(browser, fake_db, real_file):
    """Only the API sets ``demo``; a value that is merely truthy doesn't count."""
    fake_db.docs[("applications", real_file)]["demo"] = "yes"
    officer = browser("officer-1")
    code = officer.post(f"/api/applications/{real_file}/decision", json=APPROVE).json()[
        "signoffCode"
    ]

    assert officer.post(f"/api/signoff/{code}", headers=REVIEWER).status_code == 409
