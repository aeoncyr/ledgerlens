from datetime import UTC, datetime

import pytest

from app.analysis.pipeline import AnalysisResult, Context
from app.routers import analysis
from app.schemas import Assessment, Finding
from app.tools.cashflow import summarise
from app.tools.policy import PolicyResult

CAPTURED = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


def canned_context(round_: int = 0) -> Context:
    return Context(
        application={
            "alias": "Warung Uji",
            "business_type": "Grocery stall",
            "city": "Bekasi",
            "years_operating": 5,
            "amount": 10_000_000,
            "tenor_months": 12,
        },
        case_file={"facts": []},
        facts=[],
        summary=summarise([]),
        checks={},
        present=[],
        quoted=[],
        evidence_ids=[],
        extractions={},
        unreadable=[],
        reader_models=["gemini-test"],
        round=round_,
    )


def canned_result(findings: list[Finding], round_: int = 0) -> AnalysisResult:
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
        round=round_,
        context=canned_context(round_),
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
    assert (
        memo["policy"]["maxInstallment"] == 1_500_000
    )  # stored camelCase, as the web app reads it
    run = fake_db.docs[("applications", app_id, "runs", body["runId"])]
    assert run["state"] == "done"
    assert run["steps"][0]["message"] == "Read 14 lines from Notebook page 1"


def test_declared_monthly_debts_reach_the_pipeline(client, monkeypatch):
    seen = []

    async def fake_pipeline(*, application, **_options):
        seen.append(application)
        result = canned_result([])
        result.extractions = {}
        return result

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
            "existingMonthlyDebt": 350_000,
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

    assert client.post(f"/api/applications/{app_id}/analyze").status_code == 200
    assert seen[0].existing_monthly_debt == 350_000


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


QUESTION = Finding(
    kind="discrepancy",
    severity="medium",
    text="Sales differ.",
    follow_up_question="Boleh dijelaskan, Bu?",
)


@pytest.fixture
def answered_file(client, ready_application, monkeypatch):
    app_id, _, patch = ready_application
    patch.findings = [QUESTION]
    client.post(f"/api/applications/{app_id}/analyze")
    asked = []

    async def fake_judge(*, gemini, context, progress, answers=None, policy=None):
        asked.append((context.round, answers))
        await progress("verifier", "1 finding(s), 1 explained by the owner", "done")
        explained = QUESTION.model_copy(update={"resolved": True, "answer": answers[0]["answer"]})
        result = canned_result([explained], round_=context.round)
        result.extractions = {}  # a re-check reads nothing new
        return result

    monkeypatch.setattr(analysis, "judge", fake_judge)
    return app_id, asked


def test_answers_are_stored_and_the_file_is_checked_again(client, fake_db, answered_file):
    app_id, asked = answered_file

    saved = client.post(
        f"/api/applications/{app_id}/findings/0/answer",
        json={"text": "Hari Sabtu ramai karena pasar."},
    )
    response = client.post(f"/api/applications/{app_id}/reverify")

    assert saved.status_code == 204
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert asked == [
        (
            1,
            [
                {
                    "finding": "Sales differ.",
                    "question": "Boleh dijelaskan, Bu?",
                    "answer": "Hari Sabtu ramai karena pasar.",
                }
            ],
        )
    ]
    memo = fake_db.docs[("applications", app_id, "memo", "current")]
    assert memo["findings"][0]["resolved"] is True
    assert memo["round"] == 1


def test_rechecking_needs_an_answer(client, answered_file):
    app_id, _ = answered_file

    response = client.post(f"/api/applications/{app_id}/reverify")

    assert response.status_code == 409


def test_only_questions_can_be_answered(client, answered_file):
    app_id, _ = answered_file

    response = client.post(
        f"/api/applications/{app_id}/findings/5/answer", json={"text": "Tidak ada."}
    )

    assert response.status_code == 404


def test_the_owner_is_asked_at_most_twice(client, fake_db, answered_file):
    app_id, _ = answered_file
    context = fake_db.docs[("applications", app_id, "memo", "context")]
    context["round"] = 2
    client.post(f"/api/applications/{app_id}/findings/0/answer", json={"text": "Ramai."})

    response = client.post(f"/api/applications/{app_id}/reverify")

    assert response.status_code == 409


def test_a_visitor_can_run_only_so_many_analyses_a_day(client, ready_application, monkeypatch):
    from dataclasses import replace

    from app.config import get_settings

    app_id, _, _ = ready_application
    limited = replace(get_settings(), runs_per_user_per_day=2)
    monkeypatch.setattr(analysis, "get_settings", lambda: limited)

    codes = [client.post(f"/api/applications/{app_id}/analyze").status_code for _ in range(3)]

    assert codes == [200, 200, 429]


def test_a_spent_gemini_quota_gets_a_clear_message(client, ready_application, monkeypatch):
    from app.gemini import GeminiQuotaExhausted

    app_id, _, _ = ready_application

    async def exhausted(**_):
        raise GeminiQuotaExhausted("spent")

    monkeypatch.setattr(analysis, "run_pipeline", exhausted)

    response = client.post(f"/api/applications/{app_id}/analyze")

    assert response.status_code == 503
    assert "free daily quota" in response.json()["detail"]


@pytest.fixture
def disputed_file(client, fake_db, ready_application):
    app_id, _, _ = ready_application
    client.post(f"/api/applications/{app_id}/analyze")
    context = fake_db.docs[("applications", app_id, "memo", "context")]
    evidence_id = next(iter(fake_db.docs_in("applications", app_id, "evidence")))
    context["extractions"] = {
        evidence_id: {
            "label": "Notebook page 1",
            "lines": [{"line": 2, "amountRp": 850_000, "confidence": 0.5}],
            "disagreements": [{"line": 2, "first": 850_000, "second": 650_000}],
        }
    }
    return app_id, evidence_id


def test_the_officer_confirms_a_disputed_reading(client, fake_db, disputed_file):
    app_id, evidence_id = disputed_file
    url = f"/api/applications/{app_id}/evidence/{evidence_id}/confirm"

    assert client.post(url, json={"line": 3, "amountRp": 1}).status_code == 404
    confirmed = client.post(url, json={"line": 2, "amountRp": 650_000})

    assert confirmed.json() == {"pending": 0}
    context = fake_db.docs[("applications", app_id, "memo", "context")]
    assert context["confirmed"] == {evidence_id: {"2": 650_000}}
    assert context["pending_confirmations"] is True
    line = fake_db.docs[("applications", app_id, "evidence", evidence_id)]["extraction"]["lines"][0]
    assert (line["amountRp"], line["confirmedByOfficer"]) == (650_000, True)


def test_rechecking_after_a_confirmation_does_not_use_a_question_round(
    client, fake_db, disputed_file, monkeypatch
):
    app_id, evidence_id = disputed_file
    rounds = []

    async def fake_judge(*, gemini, context, progress, answers=None, policy=None):
        rounds.append(context.round)
        result = canned_result([], round_=context.round)
        result.extractions = {}
        result.context = context
        return result

    monkeypatch.setattr(analysis, "judge", fake_judge)
    client.post(
        f"/api/applications/{app_id}/evidence/{evidence_id}/confirm",
        json={"line": 2, "amountRp": 650_000},
    )

    assert client.post(f"/api/applications/{app_id}/reverify").status_code == 200
    assert rounds == [0]
    assert client.post(f"/api/applications/{app_id}/reverify").status_code == 409


def test_only_the_officer_confirms_readings(client_as, fake_db, disputed_file):
    app_id, evidence_id = disputed_file
    fake_db.docs[("applications", app_id)]["ownerUid"] = "owner-9"

    response = client_as("owner-9").post(
        f"/api/applications/{app_id}/evidence/{evidence_id}/confirm",
        json={"line": 2, "amountRp": 650_000},
    )

    assert response.status_code == 404


def test_an_owner_may_decline_and_it_is_recorded_neutrally(client, fake_db, answered_file):
    app_id, _ = answered_file

    response = client.post(f"/api/applications/{app_id}/findings/0/answer", json={"declined": True})

    assert response.status_code == 204
    finding = fake_db.docs[("applications", app_id, "memo", "current")]["findings"][0]
    assert (finding["declined"], finding["answer"]) == (True, "(prefers not to answer)")


def test_a_spoken_answer_is_transcribed(client, fake_db, fake_gemini, answered_file):
    from app.agents.interview_listener import SpokenAnswer

    app_id, _ = answered_file

    class Store:
        async def read(self, path):
            return b"audio", "audio/webm"

    client.app.dependency_overrides[analysis.get_evidence_store] = lambda: Store()
    fake_gemini.reading = SpokenAnswer(
        audible=True, transcript="Ada kue titipan tetangga.", transcript_en="Consignment cakes."
    )

    response = client.post(
        f"/api/applications/{app_id}/findings/0/answer",
        json={"audioPath": f"evidence/{app_id}/judge-1/answer.webm"},
    )

    assert response.status_code == 204
    finding = fake_db.docs[("applications", app_id, "memo", "current")]["findings"][0]
    assert (finding["answer"], finding["answerEn"]) == (
        "Ada kue titipan tetangga.",
        "Consignment cakes.",
    )
