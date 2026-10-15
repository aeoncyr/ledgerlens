"""The API contract shared with the web app.

Every model serialises to camelCase JSON (``businessType``, ``tenorMonths``) because that is what
the TypeScript frontend expects, while Python code keeps snake_case attributes.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# --- Shared vocabularies -------------------------------------------------------------------------


class EvidenceType(StrEnum):
    LEDGER_PAGE = "ledger_page"
    QRIS_HISTORY = "qris_history"
    RECEIPT = "receipt"
    SHOP_PHOTO = "shop_photo"
    INTERVIEW_AUDIO = "interview_audio"


class EvidenceTier(StrEnum):
    """How hard a piece of evidence is to fake. Only hard evidence sets the low end of cash flow."""

    HARD = "hard"
    MEDIUM = "medium"
    SOFT = "soft"
    PHYSICAL = "physical"


TIER_BY_TYPE: dict[EvidenceType, EvidenceTier] = {
    EvidenceType.QRIS_HISTORY: EvidenceTier.HARD,
    EvidenceType.RECEIPT: EvidenceTier.MEDIUM,
    EvidenceType.LEDGER_PAGE: EvidenceTier.SOFT,
    EvidenceType.INTERVIEW_AUDIO: EvidenceTier.SOFT,
    EvidenceType.SHOP_PHOTO: EvidenceTier.PHYSICAL,
}


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    NEEDS_FOLLOW_UP = "needs_follow_up"
    READY = "ready"
    IN_REVIEW = "in_review"
    DECIDED = "decided"


class Assessment(StrEnum):
    """The four honest outcomes. There is deliberately no automatic rejection."""

    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INCONSISTENT = "inconsistent"


class DecisionAction(StrEnum):
    APPROVE = "approve"
    REQUEST_MORE = "request_more"
    DECLINE = "decline"


# --- Requests and responses ----------------------------------------------------------------------


class HealthResponse(CamelModel):
    ok: bool
    version: str
    model: str


class CreateApplicationRequest(CamelModel):
    alias: str = Field(
        min_length=1,
        max_length=80,
        description="Business alias. Never the owner's legal name or national ID number.",
    )
    business_type: str = Field(min_length=1, max_length=80)
    city: str = Field(min_length=1, max_length=80)
    years_operating: int = Field(ge=0, le=80)
    amount: int = Field(gt=0, description="Requested loan amount in rupiah")
    tenor_months: int = Field(ge=1, le=60)


class CreateApplicationResponse(CamelModel):
    application_id: str


class ConsentRequest(CamelModel):
    consent_version: str
    given: bool


class GeoPoint(CamelModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RegisterEvidenceRequest(CamelModel):
    type: EvidenceType
    storage_path: str = Field(min_length=1)
    captured_at: datetime
    gps: GeoPoint | None = None


class RegisterEvidenceResponse(CamelModel):
    evidence_id: str


class RunStartedResponse(CamelModel):
    """Returned at once by /analyze and /reverify; the work continues in the background."""

    run_id: str


class FollowUpAnswerRequest(CamelModel):
    text: str | None = None
    audio_path: str | None = None

    @model_validator(mode="after")
    def _needs_an_answer(self) -> FollowUpAnswerRequest:
        if not (self.text or self.audio_path):
            raise ValueError("Provide the owner's answer as text or as an audio path")
        return self


class DecisionRequest(CamelModel):
    action: DecisionAction
    reason: str = Field(min_length=5, description="Every decision needs a written reason")


class ShareRequest(CamelModel):
    lender_id: str


# --- Documents the app reads from Firestore ------------------------------------------------------


class RunStep(CamelModel):
    agent: str
    message: str
    state: Literal["pending", "running", "done", "failed"]
    at: datetime


class Citation(CamelModel):
    evidence_id: str
    locator: str = Field(description="Where in the evidence, e.g. 'page 2, line 4' or 'audio 0:34'")


class Finding(CamelModel):
    kind: Literal["discrepancy", "low_confidence", "missing_evidence", "fraud_signal"]
    severity: Literal["low", "medium", "high"]
    text: str
    citations: list[Citation] = Field(default_factory=list)
    follow_up_question: str | None = None
    answer: str | None = None


class LedgerLineOut(CamelModel):
    line: int
    date_text: str | None
    description: str
    amount_text: str | None
    amount_rp: int | None = Field(description="Parsed by code from amount_text, never by the model")
    kind: str
    confidence: float


class LedgerPageResult(CamelModel):
    reading_id: str
    model: str
    lines: list[LedgerLineOut]
