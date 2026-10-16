"""The owner's side: start a file, share it with one lender, withdraw it."""

import pytest

from tests.test_analysis_route import canned_result

FILE = {
    "alias": "Warung Bu Sari",
    "businessType": "Grocery stall",
    "city": "Bekasi",
    "yearsOperating": 8,
    "amount": 15_000_000,
    "tenorMonths": 12,
}


@pytest.fixture
def owner(client_as):
    return client_as("owner-1")


@pytest.fixture
def officer(client_as):
    return client_as("officer-1")


@pytest.fixture
def file_id(owner):
    created = owner.post("/api/owner/files", json=FILE)
    assert created.status_code == 201
    return created.json()["applicationId"]


def test_an_owner_starts_a_file_no_lender_can_see(owner, officer, fake_db, file_id):
    stored = fake_db.docs[("applications", file_id)]

    assert (stored["ownerUid"], stored["officerUid"], stored["origin"]) == (
        "owner-1",
        None,
        "owner",
    )
    consent = {"consentVersion": "v1", "given": True}
    assert officer.post(f"/api/applications/{file_id}/consent", json=consent).status_code == 404
    assert owner.post(f"/api/applications/{file_id}/consent", json=consent).status_code == 204
    assert fake_db.docs[("applications", file_id)]["consent"]["by"] == "owner"


def test_evidence_the_owner_sends_is_marked_as_theirs(owner, fake_db, file_id):
    owner.post(f"/api/applications/{file_id}/consent", json={"consentVersion": "v1", "given": True})

    added = owner.post(
        f"/api/applications/{file_id}/evidence",
        json={
            "type": "qris_history",
            "storagePath": f"evidence/{file_id}/owner-1/qris.png",
            "capturedAt": "2026-10-16T09:00:00+07:00",
        },
    )

    evidence = fake_db.docs[("applications", file_id, "evidence", added.json()["evidenceId"])]
    assert evidence["submittedBy"] == "owner"


def test_sharing_gives_one_lender_access_until_the_owner_withdraws(
    owner, officer, client_as, fake_db, file_id
):
    first = owner.post(f"/api/applications/{file_id}/share").json()
    again = owner.post(f"/api/applications/{file_id}/share").json()
    assert first == again
    assert first["path"] == f"/app/shared/{first['shareCode']}"

    opened = officer.post(f"/api/shared/{first['shareCode'].lower()}")
    assert opened.json() == {"applicationId": file_id}
    assert fake_db.docs[("applications", file_id)]["officerUid"] == "officer-1"
    assert client_as("officer-2").post(f"/api/shared/{first['shareCode']}").status_code == 409

    assert owner.delete(f"/api/applications/{file_id}/share").status_code == 204
    assert fake_db.docs[("applications", file_id)]["officerUid"] is None
    assert officer.post(f"/api/shared/{first['shareCode']}").status_code == 404
    consent = {"consentVersion": "v1", "given": True}
    assert officer.post(f"/api/applications/{file_id}/consent", json=consent).status_code == 404


def test_only_the_owner_shares_and_only_the_officer_decides(owner, officer, fake_db, file_id):
    code = owner.post(f"/api/applications/{file_id}/share").json()["shareCode"]
    officer.post(f"/api/shared/{code}")
    fake_db.docs[("applications", file_id)]["status"] = "ready"
    decision = {
        "action": "approve",
        "reason": "Cash flow covers the instalment.",
        "offer": {"amountRp": 15_000_000, "tenorMonths": 12, "annualRatePct": 6},
    }

    assert officer.post(f"/api/applications/{file_id}/share").status_code == 404
    assert owner.post(f"/api/applications/{file_id}/decision", json=decision).status_code == 404
    assert officer.post(f"/api/applications/{file_id}/decision", json=decision).status_code == 200


def test_an_owner_check_writes_a_summary_for_the_owner(owner, fake_db, file_id, monkeypatch):
    from app.routers import analysis
    from app.schemas import Finding

    owner.post(f"/api/applications/{file_id}/consent", json={"consentVersion": "v1", "given": True})
    owner.post(
        f"/api/applications/{file_id}/evidence",
        json={
            "type": "ledger_page",
            "storagePath": f"evidence/{file_id}/owner-1/p1.jpg",
            "capturedAt": "2026-10-16T09:00:00+07:00",
        },
    )
    question = Finding(
        kind="missing_evidence",
        severity="medium",
        text="There is no QRIS history.",
        follow_up_question="Apakah Ibu memakai QRIS?",
        follow_up_question_en="Do you use QRIS?",
    )

    async def fake_pipeline(*, items, **_):
        result = canned_result([question])
        result.memo["owner_summary"] = {
            "verified": "Penjualan cocok.",
            "missing": "Riwayat QRIS.",
            "tips": ["Simpan nota."],
            "verified_en": "Sales match.",
            "missing_en": "QRIS history.",
            "tips_en": ["Keep receipts."],
        }
        result.extractions = {items[0].id: {"label": "Notebook page 1"}}
        return result

    monkeypatch.setattr(analysis, "run_pipeline", fake_pipeline)
    owner.app.dependency_overrides[analysis.get_evidence_store] = lambda: object()

    assert owner.post(f"/api/applications/{file_id}/analyze").status_code == 200
    summary = fake_db.docs[("applications", file_id, "owner", "summary")]
    assert (summary["status"], summary["verifiedEn"], summary["tips"]) == (
        "needs_answers",
        "Sales match.",
        ["Simpan nota."],
    )
    assert summary["questions"] == [
        {
            "index": 0,
            "question": "Apakah Ibu memakai QRIS?",
            "questionEn": "Do you use QRIS?",
            "answer": None,
        }
    ]

    owner.post(f"/api/applications/{file_id}/findings/0/answer", json={"text": "Belum, Pak."})
    summary = fake_db.docs[("applications", file_id, "owner", "summary")]
    assert summary["questions"][0]["answer"] == "Belum, Pak."
