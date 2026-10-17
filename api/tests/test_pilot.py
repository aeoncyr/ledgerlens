"""The pilot dashboard, and the officer's agreement with LedgerLens's assessment that it counts."""

import csv
import io
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_decisions import (
    APPROVE,
    FILE,
    application,
    audit_actions,
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


def audit_entries(fake_db, file_id):
    return list(fake_db.docs_in("applications", file_id, "audit").values())


@pytest.fixture
def checked(fake_db, file_id):
    """The file has an outcome, as the analysis would have left it."""
    application(fake_db, file_id)["assessment"] = "partially_verified"
    return file_id


# --- Agree or disagree with the assessment --------------------------------------------------------


def test_the_officer_agreeing_is_stored_on_the_decision_and_audited(officer, fake_db, checked):
    recommend(officer, checked, {**APPROVE, "assessmentAgreed": True})

    decision = application(fake_db, checked)["decision"]
    assert decision["assessmentAgreed"] is True
    assert decision["disagreementReason"] is None
    assert decision["assessmentAtDecision"] == "partially_verified"
    agreed = [e for e in audit_entries(fake_db, checked) if e["action"] == "assessment_agreed"]
    assert agreed[0]["details"] == {"assessment": "partially_verified"}


def test_disagreeing_needs_a_reason(officer, checked):
    body = {**APPROVE, "assessmentAgreed": False, "disagreementReason": " no "}

    response = officer.post(f"/api/applications/{checked}/decision", json=body)

    assert response.status_code == 422
    assert "why you disagree" in response.text


def test_a_disagreement_keeps_its_reason(officer, fake_db, checked):
    reason = "The notebook gap is the Lebaran closure; I visited the shop."
    body = {
        "action": "request_more",
        "reason": "Please send three months of QRIS history.",
        "conditions": [{"text": "QRIS history for three months", "evidenceType": "qris_history"}],
        "assessmentAgreed": False,
        "disagreementReason": f"  {reason} ",
    }

    recommend(officer, checked, body)

    decision = application(fake_db, checked)["decision"]
    assert (decision["assessmentAgreed"], decision["disagreementReason"]) == (False, reason)
    entry = next(
        e for e in audit_entries(fake_db, checked) if e["action"] == "assessment_disagreed"
    )
    assert entry["reason"] == reason
    # The owner's copy of the decision never carries the officer's view of the assessment.
    sent = fake_db.docs[("applications", checked, "owner", "decision")]
    assert "assessmentAgreed" not in sent and "disagreementReason" not in sent


def test_a_decision_without_an_answer_is_still_accepted(officer, fake_db, checked):
    recommend(officer, checked)

    assert application(fake_db, checked)["decision"]["assessmentAgreed"] is None
    assert not {"assessment_agreed", "assessment_disagreed"} & set(audit_actions(fake_db, checked))


def test_the_csv_export_says_whether_the_officer_agreed(officer, checked):
    body = {**APPROVE, "assessmentAgreed": False, "disagreementReason": "Seasonal dip explained."}
    recommend(officer, checked, body)

    text = officer.get(f"/api/applications/{checked}/export.csv").text.lstrip("﻿")
    header, row = list(csv.reader(io.StringIO(text)))[:2]
    summary = dict(zip(header, row, strict=True))

    assert summary["Officer agrees with LedgerLens"] == "no"
    assert summary["Why the officer disagrees"] == "Seasonal dip explained."


def test_the_json_export_carries_the_agreement(officer, checked):
    recommend(officer, checked, {**APPROVE, "assessmentAgreed": True})

    exported = officer.get(f"/api/applications/{checked}/export.json").json()

    assert exported["decision"]["assessmentAgreed"] is True


# --- The dashboard --------------------------------------------------------------------------------


def seed(fake_db, file_id, *, officer="officer-1", **fields):
    """A file as Firestore would hold it, with its audit, runs, evidence and credit file."""
    data = {
        "officerUid": officer,
        "ownerUid": None,
        "origin": "officer",
        "business": {"alias": f"Toko {file_id}"},
        "status": "ready",
        "assessment": None,
        "createdAt": T0,
    }
    data.update(fields.pop("app", {}))
    fake_db.docs[("applications", file_id)] = data
    for i, kind in enumerate(fields.pop("evidence", [])):
        fake_db.docs[("applications", file_id, "evidence", f"e{i}")] = {"type": kind}
    for i, (action, minutes) in enumerate(fields.pop("audit", [])):
        fake_db.docs[("applications", file_id, "audit", f"a{i}")] = {
            "action": action,
            "at": T0 + timedelta(minutes=minutes),
        }
    for i, (state, minutes) in enumerate(fields.pop("runs", [])):
        fake_db.docs[("applications", file_id, "runs", f"r{i}")] = {
            "state": state,
            "finishedAt": T0 + timedelta(minutes=minutes),
        }
    if "findings" in fields:
        fake_db.docs[("applications", file_id, "memo", "current")] = {
            "findings": [{"kind": kind} for kind in fields.pop("findings")]
        }


@pytest.fixture
def workspace(fake_db):
    seed(
        fake_db,
        "f1",
        app={
            "assessment": "verified",
            "status": "decided",
            "decision": {"action": "approve", "state": "final", "assessmentAgreed": True},
        },
        evidence=["ledger_page", "qris_history", "receipt"],
        audit=[("evidence_added", 0), ("evidence_added", 5), ("recommended_approve", 40)],
        runs=[("done", 10), ("done", 30)],
        findings=["discrepancy", "fraud_signal"],
    )
    seed(
        fake_db,
        "f2",
        app={
            "assessment": "inconsistent",
            "origin": "owner",
            "decision": {
                "action": "request_more",
                "state": "final",
                "assessmentAgreed": False,
                "disagreementReason": "Visited; the stock is there.",
            },
        },
        evidence=["ledger_page"],
        audit=[("evidence_added", 0), ("decision_request_more", 120)],
        runs=[("failed", 3), ("done", 20)],
        findings=["fraud_signal", "missing_evidence"],
    )
    seed(fake_db, "f3", app={"status": "collecting"}, evidence=[], audit=[])
    seed(
        fake_db,
        "demo",
        app={"assessment": "verified", "demo": True, "origin": "owner"},
        evidence=["ledger_page"],
        findings=["low_confidence"],
    )
    # Another officer's file is never counted.
    seed(fake_db, "theirs", officer="officer-2", app={"assessment": "verified"})


def test_the_dashboard_counts_only_the_officers_own_files(officer, workspace):
    report = officer.get("/api/pilot").json()

    assert report["files"] == 4
    assert report["demoFiles"] == 1
    assert {r["applicationId"] for r in report["rows"]} == {"f1", "f2", "f3", "demo"}
    assert report["byOrigin"] == {"officer": 2, "owner": 2}
    assert report["byOutcome"] == {"verified": 2, "inconsistent": 1, "not_checked": 1}


def test_demo_files_can_be_left_out(officer, workspace):
    report = officer.get("/api/pilot", params={"includeDemo": "false"}).json()

    assert report["files"] == 3
    assert report["demoFiles"] == 1
    assert report["includeDemo"] is False
    assert report["findingsByKind"]["low_confidence"] == 0


def test_the_dashboard_times_files_from_the_first_record(officer, workspace):
    report = officer.get("/api/pilot", params={"includeDemo": "false"}).json()
    rows = {r["applicationId"]: r for r in report["rows"]}

    # f1: first record at 0, first finished check at 10, decision at 40.
    assert (rows["f1"]["minutesToAnalysis"], rows["f1"]["minutesToDecision"]) == (10.0, 40.0)
    # f2: the failed run does not count as a finished check.
    assert (rows["f2"]["minutesToAnalysis"], rows["f2"]["minutesToDecision"]) == (20.0, 120.0)
    assert rows["f3"]["minutesToAnalysis"] is None
    assert report["medianMinutesToAnalysis"] == 15.0
    assert report["medianMinutesToDecision"] == 80.0
    assert (report["timedToAnalysis"], report["timedToDecision"]) == (2, 2)


def test_the_dashboard_counts_findings_agreement_and_missing_records(officer, workspace):
    report = officer.get("/api/pilot", params={"includeDemo": "false"}).json()

    assert report["findingsByKind"] == {
        "fraud_signal": 2,
        "discrepancy": 1,
        "missing_evidence": 1,
        "low_confidence": 0,
    }
    assert report["filesWithFraudSignal"] == 2
    assert (report["decided"], report["agreed"], report["disagreed"]) == (2, 1, 1)
    assert report["agreedPct"] == 50
    # Only checked files say what was missing: f1 lacks two kinds, f2 four.
    assert report["checkedFiles"] == 2
    missing = {m["type"]: m["files"] for m in report["missingEvidence"]}
    assert missing == {
        "shop_photo": 2,
        "interview_audio": 2,
        "qris_history": 1,
        "receipt": 1,
    }
    assert report["missingEvidence"][0]["files"] == 2


def test_an_empty_workspace_has_no_figures_to_show(officer):
    report = officer.get("/api/pilot").json()

    assert report["files"] == 0
    assert report["medianMinutesToAnalysis"] is None
    assert report["agreedPct"] is None
    assert report["rows"] == []


def test_the_dashboard_exports_its_table_as_csv(officer, workspace):
    response = officer.get("/api/pilot/export.csv")

    assert response.status_code == 200
    assert "ledgerlens-pilot-" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("﻿"))))
    assert len(rows) == 4
    f2 = next(r for r in rows if r["Business"] == "Toko f2")
    assert f2["Officer and LedgerLens"] == "disagrees"
    assert f2["Why the officer disagrees"] == "Visited; the stock is there."
    assert f2["Started by"] == "owner"
    assert next(r for r in rows if r["Business"] == "Toko demo")["Demo copy"] == "yes"


def test_a_real_decision_shows_on_the_dashboard(officer, checked):
    recommend(officer, checked, {**APPROVE, "assessmentAgreed": True})

    report = officer.get("/api/pilot").json()

    assert (report["decided"], report["agreed"], report["agreedPct"]) == (1, 1, 100)
    assert report["byOrigin"] == {"owner": 1}


def test_the_dashboard_needs_a_signed_in_user(anonymous_client):
    assert anonymous_client.get("/api/pilot").status_code == 401
