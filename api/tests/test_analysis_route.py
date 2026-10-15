from datetime import UTC, datetime

import pytest

from app.analysis.pipeline import AnalysisResult
from app.routers import analysis
from app.schemas import Assessment, Finding
from app.tools.cashflow import summarise
from app.tools.policy import PolicyResult

CAPTURED = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


def canned_result(findings: list[Finding]) -> AnalysisResult:
    return AnalysisResult(
        assessment=Assessment.VERIFIED,
        policy=PolicyResult(
            assessment=Assessment.VERIFIED,
            evidence_strength=80,
            capacity_basis=5_000_000,
            max_installment=1_500_000,
            requested_installment=1_290_000,
            within_policy=True,
            reasons=["Sources agree."],
        ),
        cashflow=summarise([]),
        findings=findings,
        confirmations=[],
        memo={"headline": "Sources agree.", "figures": []},
        facts=[],
        extractions={"ev-1": {"label": "Notebook page 1", "lines": []}},
        unreadable=[],
        models=["gemini-test"],
        figure_problems=[],
    )


@pytest.fixture
def ready_application(client, fake_db, monkeypatch):
    calls = []

    async def fake_pipeline(*, gemini, store, application, items, progress, **_options):
        calls.append(items)
        await progress("ledger_reader", "Read 14 lines from Notebook page 1", "done")
        result = canned_result(monkeypatch.findings)
        result.extractions = {items[0].id: {"label": "Notebook page 1", "lines": []}}
        return result

    monkeypatch.findings = []
    monkeypatch.setattr(analysis, "run_pipeline", fake_pipeline)
    client.app.dependency_overrides[analysis.get_evidence_store] = lambda: object()

    created = client.post(
        "/api/applications",
        json={
            "alias": "Warung Uji",
            "businessType": "Grocery stall",
            "city": "Bekasi",
            "yearsOperating": 5,
            "amount": 10_000_000,
            "tenorMonths": 12,
        },
    )
    app_id = created.json()["applicationId"]
    client.post(f"/api/applications/{app_id}/consent", json={"consentVersion": "v1", "given": True})
    client.post(
        f"/api/applications/{app_id}/evidence",
        json={
            "type": "ledger_page",
            "storagePath": f"evidence/{app_id}/judge-1/p1.jpg",
            "capturedAt": CAPTURED.isoformat(),
        },
    )
    return app_id, calls, monkeypatch


def test_analyze_stores_the_credit_file_and_progress(client, fake_db, ready_application):
    app_id, calls, _ = ready_application

    response = client.post(f"/api/applications/{app_id}/analyze")

    assert response.status_code == 200
    body = response.json()
    assert (body["assessment"], body["status"]) == ("verified", "ready")
    assert len(calls[0]) == 1
    application = fake_db.docs[("applications", app_id)]
    assert application["assessment"] == "verified"
    assert application["evidenceStrength"] == 80
    memo = fake_db.docs[("applications", app_id, "memo", "current")]
    assert memo["memo"]["headline"] == "Sources agree."
    run = fake_db.docs[("applications", app_id, "runs", body["runId"])]
    assert run["state"] == "done"
    assert run["steps"][0]["message"] == "Read 14 lines from Notebook page 1"


def test_material_questions_put_the_file_into_follow_up(client, ready_application):
    app_id, _, patch = ready_application
    patch.findings = [
        Finding(
            kind="discrepancy",
            severity="medium",
            text="Sales differ.",
            follow_up_question="Boleh dijelaskan, Bu?",
        )
    ]

    response = client.post(f"/api/applications/{app_id}/analyze")

    assert response.json()["status"] == "needs_follow_up"


def test_analysis_needs_evidence(client):
    created = client.post(
        "/api/applications",
        json={
            "alias": "Warung Kosong",
            "businessType": "Grocery stall",
            "city": "Bekasi",
            "yearsOperating": 1,
            "amount": 5_000_000,
            "tenorMonths": 6,
        },
    )
    app_id = created.json()["applicationId"]
    client.post(f"/api/applications/{app_id}/consent", json={"consentVersion": "v1", "given": True})
    client.app.dependency_overrides[analysis.get_evidence_store] = lambda: object()

    response = client.post(f"/api/applications/{app_id}/analyze")

    assert response.status_code == 409
