"""The lender's own settings and checks: profile and policy, invites, SLIK, and re-applying."""

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest

from app.agents.memo_writer import MemoDraft
from app.agents.verifier import Verification
from app.analysis.pipeline import run_pipeline
from app.analysis.reapply import reapply_policy
from app.routers import analysis
from app.routers.demo import load_sample
from app.routers.lender import policy_for
from app.tools.camel import camelize
from app.tools.facts import FactTable
from app.tools.policy import LenderPolicy
from app.tools.slik import SlikCheck, slik_findings
from tests.test_analysis_route import canned_result
from tests.test_pipeline import APPLICATION, ITEMS, MEMO, BytesStore, ScriptedGemini

FILE = {
    "alias": "Warung Bu Sari",
    "businessType": "Grocery stall",
    "city": "Bekasi",
    "yearsOperating": 8,
    "amount": 15_000_000,
    "tenorMonths": 12,
}
PROFILE = {
    "name": "BPR Sejahtera",
    "type": "bpr",
    "product": "kur_micro",
    "annualRatePct": 6,
    "maxInstallmentRatioPct": 20,
    "haircutVerifiedPct": 20,
    "haircutPartialPct": 40,
    "maxTenorMonths": 24,
}
TODAY = datetime.now(UTC).date()


@pytest.fixture
def owner(client_as):
    return client_as("owner-1")


@pytest.fixture
def officer(client_as):
    return client_as("officer-1")


def save_profile(client, **changes):
    return client.put("/api/lender/profile", json={**PROFILE, **changes})


def store_checked(fake_db, file_id, sample="bu-sari"):
    """Store a finished credit file on the application, as ``analysis._run`` does."""
    result = load_sample(sample)["analysis"]
    stored = result.model_dump(mode="json", by_alias=True, exclude={"extractions", "context"})
    fake_db.docs[("applications", file_id, "memo", "current")] = camelize(stored)
    fake_db.docs[("applications", file_id, "memo", "context")] = result.context.model_dump(
        mode="json"
    )
    fake_db.docs[("applications", file_id)].update(
        {"status": "ready", "assessment": result.assessment.value}
    )
    return result


def shared_file(owner, officer, fake_db, checked=True):
    """An owner's file, checked, then opened by the officer from the owner's share link."""
    file_id = owner.post("/api/owner/files", json=FILE).json()["applicationId"]
    owner.post(f"/api/applications/{file_id}/consent", json={"consentVersion": "v1", "given": True})
    if checked:
        store_checked(fake_db, file_id)
    code = owner.post(f"/api/applications/{file_id}/share").json()["shareCode"]
    assert officer.post(f"/api/shared/{code}").status_code == 200
    return file_id


def memo(fake_db, file_id):
    return fake_db.docs[("applications", file_id, "memo", "current")]


def audit_actions(fake_db, file_id):
    return [e["action"] for e in fake_db.docs_in("applications", file_id, "audit").values()]


# --- Settings ------------------------------------------------------------------------------------


def test_settings_start_from_todays_policy(officer):
    body = officer.get("/api/lender/profile").json()

    assert body["saved"] is False
    assert (body["maxInstallmentRatioPct"], body["haircutVerifiedPct"]) == (30, 20)
    assert (body["haircutPartialPct"], body["annualRatePct"], body["maxTenorMonths"]) == (40, 6, 60)


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"name": " "}, "lender's name"),
        ({"type": None}, "kind of lender"),
        ({"maxInstallmentRatioPct": 90}, "between 5% and 60%"),
        ({"haircutPartialPct": 10}, "at least as much"),
        ({"maxTenorMonths": 0}, "between 1 and 60 months"),
        ({"product": "own", "annualRatePct": 75}, "between 0% and 60%"),
    ],
)
def test_settings_are_checked_in_plain_words(officer, changes, words):
    response = save_profile(officer, **changes)

    assert response.status_code == 422
    assert words in response.json()["detail"]


def test_saving_settings_keeps_the_integration_settings(officer, fake_db):
    fake_db.docs[("lenders", "officer-1")] = {
        "webhookUrl": "https://example.com/x",
        "kind": "generic",
    }

    saved = save_profile(officer, product="kur_micro", annualRatePct=9).json()

    stored = fake_db.docs[("lenders", "officer-1")]
    assert stored["webhookUrl"] == "https://example.com/x"
    assert saved["saved"] is True
    assert saved["annualRatePct"] == 6  # the KUR micro preset sets the rate
    assert stored["policy"]["maxInstallmentRatio"] == 0.2
    assert policy_for(stored).lender_name == "BPR Sejahtera"


# --- Policy per lender ---------------------------------------------------------------------------


def test_a_check_uses_the_policy_of_the_lender_holding_the_file(
    owner, officer, fake_db, monkeypatch
):
    seen = []

    async def fake_pipeline(*, policy, slik, **_options):
        seen.append((policy, slik))
        result = canned_result([])
        result.extractions = {}
        return result

    monkeypatch.setattr(analysis, "run_pipeline", fake_pipeline)
    owner.app.dependency_overrides[analysis.get_evidence_store] = lambda: object()
    save_profile(officer)
    file_id = shared_file(owner, officer, fake_db, checked=False)
    owner.post(
        f"/api/applications/{file_id}/evidence",
        json={
            "type": "ledger_page",
            "storagePath": f"evidence/{file_id}/owner-1/p1.jpg",
            "capturedAt": "2026-10-06T09:00:00+07:00",
        },
    )

    assert owner.post(f"/api/applications/{file_id}/analyze").status_code == 200
    policy, slik = seen[0]
    assert (policy.lender_name, policy.max_installment_ratio, policy.max_tenor_months) == (
        "BPR Sejahtera",
        0.2,
        24,
    )
    assert slik is None


def test_opening_a_shared_file_applies_the_officers_policy(owner, officer, fake_db):
    save_profile(officer)

    file_id = shared_file(owner, officer, fake_db)

    policy = memo(fake_db, file_id)["policy"]
    # Bu Sari's net cash flow after a 20% haircut is Rp 4.716.000; 20% of it is Rp 943.200, below
    # the requested Rp 1.290.996, where the starting 30% allowed Rp 1.414.800.
    assert (policy["maxInstallment"], policy["withinPolicy"]) == (943_200, False)
    assert policy["lenderName"] == "BPR Sejahtera"
    assert fake_db.docs[("applications", file_id)]["lenderName"] == "BPR Sejahtera"
    assert "Rp 943.200" in memo(fake_db, file_id)["memo"]["capacity"]["text"]
    assert "BPR Sejahtera's policy" in memo(fake_db, file_id)["memoNote"]
    assert "policy_reapplied" in audit_actions(fake_db, file_id)


def test_reapplying_after_a_change_of_settings_needs_no_gemini(
    owner, officer, fake_db, fake_gemini
):
    file_id = shared_file(owner, officer, fake_db)
    assert memo(fake_db, file_id)["policy"]["maxInstallment"] == 1_414_800

    save_profile(officer, maxInstallmentRatioPct=40)
    response = officer.post(f"/api/applications/{file_id}/policy")

    assert response.status_code == 200
    assert response.json()["maxInstallment"] == 1_886_400
    assert response.json()["memoNote"] is None  # still within policy: only the figures changed
    assert "Rp 1.886.400" in memo(fake_db, file_id)["memo"]["capacity"]["text"]
    assert fake_gemini.calls == []
    assert owner.post(f"/api/applications/{file_id}/policy").status_code == 404


def test_a_term_longer_than_the_lenders_maximum_is_outside_policy(owner, officer, fake_db):
    save_profile(officer, maxInstallmentRatioPct=30, maxTenorMonths=6)

    file_id = shared_file(owner, officer, fake_db)

    policy = memo(fake_db, file_id)["policy"]
    assert policy["withinPolicy"] is False
    assert any("maximum of 6 months" in reason for reason in policy["reasons"])


def test_a_file_waiting_for_sign_off_keeps_its_policy(owner, officer, fake_db):
    file_id = shared_file(owner, officer, fake_db)
    fake_db.docs[("applications", file_id)]["status"] = "awaiting_signoff"

    assert officer.post(f"/api/applications/{file_id}/policy").status_code == 409


# --- SLIK ----------------------------------------------------------------------------------------


def slik(**changes):
    return {
        "checkedOn": TODAY.isoformat(),
        "activeFacilities": 1,
        "monthlyInstalments": 400_000,
        "worstCollectibility": 1,
        **changes,
    }


def test_slik_instalments_replace_the_declared_ones(owner, officer, fake_db):
    file_id = shared_file(owner, officer, fake_db)

    response = officer.put(f"/api/applications/{file_id}/slik", json=slik())

    assert response.status_code == 200
    stored = memo(fake_db, file_id)
    policy = stored["policy"]
    assert (policy["maxInstallment"], policy["debtSource"]) == (1_014_800, "slik")
    assert policy["existingMonthlyDebt"] == 400_000
    assert stored["assessment"] == "verified"  # SLIK never changes how well evidence is verified
    finding = stored["findings"][-1]
    assert (finding["kind"], finding["severity"]) == ("credit_history", "medium")
    assert "Rp 400.000" in finding["text"] and "Rp 0" in finding["text"]
    assert fake_db.docs[("applications", file_id, "lender", "slik")]["recordedBy"] == "officer-1"
    assert "slik_recorded" in audit_actions(fake_db, file_id)


def test_a_facility_in_arrears_is_listed_for_the_officer(owner, officer, fake_db):
    file_id = shared_file(owner, officer, fake_db)
    before = len(memo(fake_db, file_id)["findings"])

    officer.put(
        f"/api/applications/{file_id}/slik",
        json=slik(monthlyInstalments=0, activeFacilities=1, worstCollectibility=5),
    )
    officer.put(
        f"/api/applications/{file_id}/slik",
        json=slik(monthlyInstalments=0, activeFacilities=1, worstCollectibility=4),
    )

    findings = memo(fake_db, file_id)["findings"]
    assert len(findings) == before + 1  # recording again replaces the earlier SLIK findings
    assert findings[-1]["severity"] == "high"
    assert "collectibility 4, doubtful (diragukan)" in findings[-1]["text"]
    assert memo(fake_db, file_id)["assessment"] == "verified"


def test_removing_a_slik_check_goes_back_to_the_declared_figure(owner, officer, fake_db):
    file_id = shared_file(owner, officer, fake_db)
    officer.put(f"/api/applications/{file_id}/slik", json=slik())

    assert officer.delete(f"/api/applications/{file_id}/slik").status_code == 200

    stored = memo(fake_db, file_id)
    assert stored["policy"]["maxInstallment"] == 1_414_800
    assert all(f["kind"] != "credit_history" for f in stored["findings"])


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"checkedOn": (TODAY + timedelta(days=1)).isoformat()}, "future"),
        ({"checkedOn": (TODAY - timedelta(days=400)).isoformat()}, "more than a year old"),
        ({"worstCollectibility": 6}, "from 1 (current) to 5"),
        ({"activeFacilities": 0}, "no active facilities"),
    ],
)
def test_a_slik_check_is_checked_in_plain_words(owner, officer, fake_db, changes, words):
    file_id = shared_file(owner, officer, fake_db)

    response = officer.put(f"/api/applications/{file_id}/slik", json=slik(**changes))

    assert response.status_code == 422
    assert words in response.json()["detail"]


def test_only_the_lender_records_a_slik_check(owner, officer, fake_db):
    file_id = shared_file(owner, officer, fake_db)

    assert owner.put(f"/api/applications/{file_id}/slik", json=slik()).status_code == 404


def test_small_gaps_between_slik_and_the_declared_debt_are_not_findings():
    check = SlikCheck(
        checked_on=date(2026, 10, 1),
        active_facilities=1,
        monthly_instalments=550_000,
        worst_collectibility=2,
    )

    assert slik_findings(check, 500_000, FactTable()) == []


def test_reapplying_with_the_same_policy_changes_nothing():
    result = load_sample("bu-sari")["analysis"]
    stored = camelize(
        result.model_dump(mode="json", by_alias=True, exclude={"extractions", "context"})
    )

    updates = reapply_policy(stored, result.context, policy_for(None))

    assert updates["memo"] == stored["memo"]
    assert updates["findings"] == stored["findings"]
    assert updates["memoNote"] is None
    assert updates["policy"]["maxInstallment"] == stored["policy"]["maxInstallment"]


# --- Invites -------------------------------------------------------------------------------------


@pytest.fixture
def invite(officer):
    save_profile(officer)
    created = officer.post("/api/invites")
    assert created.status_code == 201
    return created.json()


def test_an_invite_needs_the_lenders_name(officer):
    response = officer.post("/api/invites")

    assert response.status_code == 409
    assert "Settings" in response.json()["detail"]


def test_the_owner_sees_who_is_asking_but_not_who_the_officer_is(owner, invite):
    assert invite["path"] == f"/owner/invite/{invite['code']}"

    seen = owner.get(f"/api/invites/{invite['code'].lower()}").json()

    assert (seen["lenderName"], seen["lenderType"], seen["state"]) == (
        "BPR Sejahtera",
        "bpr",
        "open",
    )
    assert "officer-1" not in str(seen)


def test_accepting_an_invite_starts_a_file_shared_with_that_officer(
    owner, officer, fake_db, invite
):
    accepted = owner.post(f"/api/invites/{invite['code']}/accept", json=FILE)

    assert accepted.status_code == 201
    file_id = accepted.json()["applicationId"]
    stored = fake_db.docs[("applications", file_id)]
    assert (stored["ownerUid"], stored["officerUid"], stored["origin"]) == (
        "owner-1",
        "officer-1",
        "owner",
    )
    assert stored["lenderName"] == "BPR Sejahtera"
    assert fake_db.docs[("shares", stored["shareCode"])]["applicationId"] == file_id
    assert audit_actions(fake_db, file_id) == [
        "created_by_owner",
        "invite_created",
        "invite_opened",
    ]
    # Asking twice returns the same file; the invite is used up for anyone else.
    again = owner.post(f"/api/invites/{invite['code']}/accept", json=FILE)
    assert again.json()["applicationId"] == file_id
    listed = officer.get("/api/invites").json()
    assert (listed[0]["state"], listed[0]["applicationId"]) == ("used", file_id)
    assert owner.get(f"/api/invites/{invite['code']}").json()["applicationId"] == file_id


def test_an_invite_works_once(client_as, owner, invite):
    owner.post(f"/api/invites/{invite['code']}/accept", json=FILE)

    response = client_as("owner-2").post(f"/api/invites/{invite['code']}/accept", json=FILE)

    assert response.status_code == 409
    assert "already been used" in response.json()["detail"]


def test_an_invite_expires(owner, fake_db, invite):
    fake_db.docs[("invites", invite["code"])]["expiresAt"] = datetime.now(UTC) - timedelta(days=1)

    assert owner.get(f"/api/invites/{invite['code']}").json()["state"] == "expired"
    assert owner.post(f"/api/invites/{invite['code']}/accept", json=FILE).status_code == 410


def test_an_officer_cant_accept_their_own_invite(officer, invite):
    response = officer.post(f"/api/invites/{invite['code']}/accept", json=FILE)

    assert response.status_code == 409
    assert "private window" in response.json()["detail"]


def test_the_owner_can_stop_sharing_an_invited_file(owner, officer, fake_db, invite):
    file_id = owner.post(f"/api/invites/{invite['code']}/accept", json=FILE).json()["applicationId"]

    assert owner.delete(f"/api/applications/{file_id}/share").status_code == 204

    stored = fake_db.docs[("applications", file_id)]
    assert (stored["officerUid"], stored["lenderName"]) == (None, None)
    assert officer.post(f"/api/applications/{file_id}/policy").status_code == 404


def test_unknown_invites_say_so(owner):
    response = owner.get("/api/invites/NOPE2345")

    assert response.status_code == 404
    assert "ask your lender" in response.json()["detail"]


# --- The pipeline --------------------------------------------------------------------------------


def test_a_check_with_slik_uses_its_instalments_and_lists_its_findings_last():
    async def progress(*_args, **_kwargs):
        pass

    def check(**options):
        gemini = ScriptedGemini(Verification(findings=[], confirmations=[]), MEMO)
        result = asyncio.run(
            run_pipeline(
                gemini=gemini,
                store=BytesStore(),
                application=APPLICATION,
                items=list(ITEMS),
                progress=progress,
                **options,
            )
        )
        return result, gemini

    plain, _ = check()
    record = SlikCheck(
        checked_on=TODAY, active_facilities=2, monthly_instalments=300_000, worst_collectibility=3
    )
    result, gemini = check(slik=record, policy=LenderPolicy(lender_name="BPR Sejahtera"))

    assert result.assessment == plain.assessment
    assert result.policy.max_installment == plain.policy.max_installment - 300_000
    assert (result.policy.debt_source, result.policy.lender_name) == ("slik", "BPR Sejahtera")
    assert [f.kind for f in result.findings[-2:]] == ["credit_history", "credit_history"]
    memo_case = gemini.contents[MemoDraft][0]
    assert '"monthly_instalments": "[[slik_monthly_instalments]]"' in memo_case
