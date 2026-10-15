import pytest
from pydantic import ValidationError

from app.schemas import (
    TIER_BY_TYPE,
    CreateApplicationRequest,
    DecisionRequest,
    EvidenceTier,
    EvidenceType,
    FollowUpAnswerRequest,
)


def test_requests_accept_and_emit_camel_case():
    request = CreateApplicationRequest.model_validate(
        {
            "alias": "Warung Bu Sari",
            "businessType": "grocery stall",
            "city": "Bekasi",
            "yearsOperating": 6,
            "amount": 10_000_000,
            "tenorMonths": 12,
        }
    )

    assert request.business_type == "grocery stall"
    assert request.model_dump(by_alias=True)["tenorMonths"] == 12


def test_loan_amount_must_be_positive():
    with pytest.raises(ValidationError):
        CreateApplicationRequest(
            alias="Warung",
            business_type="stall",
            city="Bekasi",
            years_operating=1,
            amount=0,
            tenor_months=12,
        )


def test_follow_up_answer_needs_text_or_audio():
    with pytest.raises(ValidationError):
        FollowUpAnswerRequest()
    assert FollowUpAnswerRequest(text="Pembeli pasar bayar tunai").text


def test_every_decision_needs_a_reason():
    with pytest.raises(ValidationError):
        DecisionRequest(action="approve", reason="")


def test_every_evidence_type_has_a_tier():
    assert set(TIER_BY_TYPE) == set(EvidenceType)
    assert TIER_BY_TYPE[EvidenceType.QRIS_HISTORY] is EvidenceTier.HARD
    assert TIER_BY_TYPE[EvidenceType.LEDGER_PAGE] is EvidenceTier.SOFT
