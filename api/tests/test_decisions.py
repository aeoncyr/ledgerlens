"""The decision loop: recommend, sign off with a second person, and the owner's answers."""

import pytest

from app import events
from app.agents.decision_letter import DecisionLetter

FILE = {
    "alias": "Warung Bu Sari",
    "businessType": "Grocery stall",
    "city": "Bekasi",
    "yearsOperating": 8,
    "amount": 15_000_000,
    "tenorMonths": 12,
}
OFFER = {"amountRp": 15_000_000, "tenorMonths": 12, "annualRatePct": 6}
APPROVE = {
    "action": "approve",
    "reason": "QRIS and supplier receipts support the notebook's sales.",
    "offer": OFFER,
    "conditions": [{"text": "Send a supplier receipt from this month", "evidenceType": "receipt"}],
}


@pytest.fixture
def emitted():
    """Every event the loop emits, as (name, payload)."""
    seen: list[tuple[str, dict]] = []

    async def listen(event, payload):
        seen.append((event, payload))

    events.LISTENERS.append(listen)
    yield seen
    events.LISTENERS.remove(listen)


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


def application(fake_db, file_id):
    return fake_db.docs[("applications", file_id)]


def owner_decision(fake_db, file_id):
    return fake_db.docs.get(("applications", file_id, "owner", "decision"))


def audit_actions(fake_db, file_id):
    return [e["action"] for e in fake_db.docs_in("applications", file_id, "audit").values()]


def analyze(client, file_id):
    from app.routers import analysis

    client.app.dependency_overrides[analysis.get_evidence_store] = lambda: object()
    return client.post(f"/api/applications/{file_id}/analyze")


def add_evidence(client, uid, file_id, kind="receipt"):
    return client.post(
        f"/api/applications/{file_id}/evidence",
        json={
            "type": kind,
            "storagePath": f"evidence/{file_id}/{uid}/{kind}.jpg",
            "capturedAt": "2026-10-16T09:00:00+07:00",
        },
    )


def recommend(officer, file_id, body=APPROVE):
    response = officer.post(f"/api/applications/{file_id}/decision", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def approved(officer, reviewer, file_id):
    code = recommend(officer, file_id)["signoffCode"]
    reviewer.post(f"/api/signoff/{code}")
    signed = reviewer.post(f"/api/applications/{file_id}/signoff", json={"approve": True})
    assert signed.status_code == 204


# --- Recommending ---------------------------------------------------------------------------------


def test_approving_needs_an_offer(officer, file_id):
    body = {"action": "approve", "reason": "Cash flow covers the instalment."}

    assert officer.post(f"/api/applications/{file_id}/decision", json=body).status_code == 422


def test_an_approval_is_a_recommendation_until_signed_off(officer, fake_db, file_id, emitted):
    result = recommend(officer, file_id)

    assert result["state"] == "recommended"
    assert result["path"] == f"/app/signoff/{result['signoffCode']}"
    stored = application(fake_db, file_id)
    assert stored["status"] == "awaiting_signoff"
    assert stored["decision"]["state"] == "recommended"
    offer = stored["decision"]["offer"]
    assert (offer["instalmentRp"], offer["withinPolicy"], offer["maxInstallmentRp"]) == (
        1_290_996,
        True,
        2_000_000,
    )
    assert len(offer["schedule"]) == 12
    assert fake_db.docs[("signoffs", result["signoffCode"])]["applicationId"] == file_id
    assert owner_decision(fake_db, file_id) is None  # the owner hears nothing yet
    assert [name for name, _ in emitted] == ["decision.recommended"]
    payload = emitted[0][1]
    assert (payload["applicationId"], payload["officerUid"], payload["alias"]) == (
        file_id,
        "officer-1",
        "Warung Bu Sari",
    )
    assert payload["offer"]["instalmentRp"] == 1_290_996 and payload["at"]


def test_an_offer_above_the_policy_limit_is_marked(officer, fake_db, file_id):
    fake_db.docs[("applications", file_id, "memo", "current")]["policy"]["maxInstallment"] = 900_000

    recommend(officer, file_id)

    assert application(fake_db, file_id)["decision"]["offer"]["withinPolicy"] is False


def test_a_recommendation_waiting_for_sign_off_cannot_be_replaced(officer, file_id):
    recommend(officer, file_id)

    again = officer.post(f"/api/applications/{file_id}/decision", json=APPROVE)

    assert again.status_code == 409


def test_a_file_waiting_for_sign_off_is_not_checked_again(officer, owner, file_id):
    recommend(officer, file_id)

    refused = analyze(owner, file_id)
    assert refused.status_code == 409 and "can't be checked again" in refused.json()["detail"]


# --- Signing off ----------------------------------------------------------------------------------


def test_the_officer_cannot_sign_off_their_own_recommendation(officer, fake_db, file_id):
    code = recommend(officer, file_id)["signoffCode"]

    assert officer.post(f"/api/signoff/{code}").status_code == 409
    signed = officer.post(f"/api/applications/{file_id}/signoff", json={"approve": True})
    assert signed.status_code == 404
    assert application(fake_db, file_id)["status"] == "awaiting_signoff"


def test_the_owner_cannot_sign_off(officer, owner, fake_db, file_id):
    code = recommend(officer, file_id)["signoffCode"]

    assert owner.post(f"/api/signoff/{code}").status_code == 403
    signed = owner.post(f"/api/applications/{file_id}/signoff", json={"approve": True})
    assert signed.status_code == 404
    assert application(fake_db, file_id).get("reviewerUid") is None


def test_one_reviewer_holds_a_sign_off(officer, reviewer, client_as, fake_db, file_id):
    code = recommend(officer, file_id)["signoffCode"]

    assert reviewer.post(f"/api/signoff/{code.lower()}").json() == {"applicationId": file_id}
    assert reviewer.post(f"/api/signoff/{code}").status_code == 200  # opening again is fine
    assert client_as("reviewer-2").post(f"/api/signoff/{code}").status_code == 409
    assert application(fake_db, file_id)["reviewerUid"] == "reviewer-1"
    assert audit_actions(fake_db, file_id).count("signoff_opened") == 1


def test_sending_back_needs_a_note_and_returns_the_file(officer, reviewer, fake_db, file_id):
    code = recommend(officer, file_id)["signoffCode"]
    reviewer.post(f"/api/signoff/{code}")
    url = f"/api/applications/{file_id}/signoff"

    assert reviewer.post(url, json={"approve": False}).status_code == 422
    note = "Lower the amount: the receipts cover two months only."
    assert reviewer.post(url, json={"approve": False, "note": note}).status_code == 204

    stored = application(fake_db, file_id)
    assert stored["status"] == "in_review"
    assert stored["decision"]["state"] == "returned"
    assert stored["decision"]["signoff"]["note"] == note
    assert ("signoffs", code) not in fake_db.docs
    assert reviewer.post(f"/api/signoff/{code}").status_code == 404
    assert owner_decision(fake_db, file_id) is None
    # The officer can recommend again, and the new link needs a new sign-off.
    again = recommend(officer, file_id)
    assert again["signoffCode"] != code
    assert application(fake_db, file_id)["reviewerUid"] is None


def test_signing_off_makes_it_final_and_tells_the_owner(
    officer, reviewer, fake_db, file_id, emitted
):
    approved(officer, reviewer, file_id)

    stored = application(fake_db, file_id)
    assert (stored["status"], stored["decision"]["state"]) == ("decided", "final")
    assert stored["decision"]["signoff"]["by"] == "reviewer-1"
    sent = owner_decision(fake_db, file_id)
    assert (sent["action"], sent["state"]) == ("approve", "offered")
    assert sent["offer"]["instalmentRp"] == 1_290_996
    assert sent["conditions"][0]["met"] is False
    # The fake Gemini answers with the wrong schema, so the template wrote the letter.
    assert sent["letter"]["source"] == "template"
    assert "Rp 1.290.996" in sent["letter"]["en"] and "Rp 1.290.996" in sent["letter"]["id"]
    assert "[[" not in sent["letter"]["en"] + sent["letter"]["id"]
    assert [name for name, _ in emitted] == ["decision.recommended", "decision.final"]
    assert emitted[1][1]["signedOffBy"] == "reviewer-1"
    actions = audit_actions(fake_db, file_id)
    assert actions[-4:] == [
        "recommended_approve",
        "signoff_opened",
        "decision_approve",
        "decision_sent_to_owner",
    ]


def test_the_letter_comes_from_gemini_with_figures_filled_by_code(
    officer, reviewer, fake_gemini, fake_db, file_id
):
    fake_gemini.reading = DecisionLetter(
        en="Your lender offers [[offer_amount]]; you repay [[offer_instalment]] a month.",
        id="Pemberi pinjaman menawarkan [[offer_amount]]; cicilan [[offer_instalment]] per bulan.",
    )

    approved(officer, reviewer, file_id)

    letter = owner_decision(fake_db, file_id)["letter"]
    assert letter["source"] == "gemini"
    assert letter["en"] == "Your lender offers Rp 15.000.000; you repay Rp 1.290.996 a month."
    assert len(fake_gemini.calls) == 1  # one writer call per final decision


def test_a_figure_the_model_wrote_itself_never_reaches_the_owner(
    officer, reviewer, fake_gemini, fake_db, file_id
):
    fake_gemini.reading = DecisionLetter(
        en="You repay Rp 1.300.000 a month.", id="Cicilan Rp 1.300.000 per bulan."
    )

    approved(officer, reviewer, file_id)

    letter = owner_decision(fake_db, file_id)["letter"]
    assert "1.300.000" not in letter["en"] + letter["id"]
    assert letter["figureProblems"]
    assert len(fake_gemini.calls) == 2  # asked once more, then scrubbed


def test_a_broken_listener_never_breaks_the_decision(officer, file_id):
    async def broken(event, payload):
        raise RuntimeError("webhook down")

    events.LISTENERS.append(broken)
    try:
        assert recommend(officer, file_id)["state"] == "recommended"
    finally:
        events.LISTENERS.remove(broken)


# --- The owner answers ----------------------------------------------------------------------------


def test_the_owner_accepts_the_offer(officer, reviewer, owner, fake_db, file_id, emitted):
    approved(officer, reviewer, file_id)
    url = f"/api/applications/{file_id}/offer"

    assert officer.post(url, json={"accept": True}).status_code == 403  # the owner answers
    assert owner.post(url, json={"accept": True}).status_code == 204
    assert owner_decision(fake_db, file_id)["state"] == "accepted"
    assert owner.post(url, json={"accept": False}).status_code == 409  # answered once
    assert emitted[-1][0] == "offer.accepted"
    assert emitted[-1][1]["offer"]["amountRp"] == 15_000_000
    assert "offer_accepted" in audit_actions(fake_db, file_id)


def test_the_owner_can_decline_the_offer(officer, reviewer, owner, fake_db, file_id, emitted):
    approved(officer, reviewer, file_id)

    owner.post(f"/api/applications/{file_id}/offer", json={"accept": False})

    assert owner_decision(fake_db, file_id)["state"] == "declined_by_owner"
    assert emitted[-1][0] == "offer.declined"


def test_a_condition_met_by_a_record_needs_a_new_record(
    officer, reviewer, owner, fake_db, file_id, emitted
):
    add_evidence(owner, "owner-1", file_id)  # a receipt already on file does not count
    approved(officer, reviewer, file_id)
    url = f"/api/applications/{file_id}/conditions/0/met"

    assert owner.post(url).status_code == 409  # accept the offer first
    owner.post(f"/api/applications/{file_id}/offer", json={"accept": True})
    assert owner.post(url).status_code == 409  # no new receipt yet
    assert owner.post(f"/api/applications/{file_id}/conditions/5/met").status_code == 404
    add_evidence(owner, "owner-1", file_id)
    assert owner.post(url).status_code == 204

    condition = owner_decision(fake_db, file_id)["conditions"][0]
    assert condition["met"] is True and condition["metAt"]
    assert emitted[-1] == (
        "condition.met",
        {**emitted[-1][1], "index": 0, "text": "Send a supplier receipt from this month"},
    )


def test_a_loan_on_offer_is_not_checked_again(officer, reviewer, owner, file_id):
    approved(officer, reviewer, file_id)

    refused = analyze(owner, file_id)
    assert refused.status_code == 409 and "can't be checked again" in refused.json()["detail"]


def test_a_decline_is_signed_off_and_explained(officer, reviewer, fake_db, file_id):
    body = {"action": "decline", "reason": "The notebook and QRIS disagree on September sales."}
    code = recommend(officer, file_id, body)["signoffCode"]
    reviewer.post(f"/api/signoff/{code}")
    reviewer.post(f"/api/applications/{file_id}/signoff", json={"approve": True})

    sent = owner_decision(fake_db, file_id)
    assert (sent["action"], sent["state"], sent["offer"]) == ("decline", "declined", None)
    assert "September" in sent["letter"]["en"]


def test_asking_for_more_goes_to_the_owner_at_once(owner, officer, fake_db, file_id, emitted):
    body = {
        "action": "request_more",
        "reason": "Sales need a second source.",
        "conditions": [{"text": "Three months of QRIS history", "evidenceType": "qris_history"}],
    }

    final = {"state": "final", "signoffCode": None, "path": None}
    assert recommend(officer, file_id, body) == final

    assert application(fake_db, file_id)["status"] == "collecting"
    sent = owner_decision(fake_db, file_id)
    assert (sent["action"], sent["state"]) == ("request_more", "requested")
    assert "Three months of QRIS history" in sent["letter"]["en"]
    assert emitted[-1][0] == "decision.final" and emitted[-1][1]["signedOffBy"] is None

    url = f"/api/applications/{file_id}/requested/sent"
    assert owner.post(url).status_code == 409  # nothing sent yet
    add_evidence(owner, "owner-1", file_id, "qris_history")
    assert owner.post(url).status_code == 204
    sent = owner_decision(fake_db, file_id)
    assert (sent["state"], sent["sentCount"]) == ("sent", 1)
    assert emitted[-1][0] == "evidence.requested_received" and emitted[-1][1]["count"] == 1
    assert "requested_records_sent" in audit_actions(fake_db, file_id)


def test_on_an_officers_own_file_the_officer_records_the_owners_answer(
    client_as, reviewer, fake_db
):
    officer = client_as("officer-9")
    file_id = officer.post("/api/applications", json=FILE).json()["applicationId"]
    fake_db.docs[("applications", file_id)]["status"] = "ready"
    approved(officer, reviewer, file_id)

    answered = officer.post(f"/api/applications/{file_id}/offer", json={"accept": True})

    assert answered.status_code == 204
    assert owner_decision(fake_db, file_id)["answeredBy"] == "officer"
