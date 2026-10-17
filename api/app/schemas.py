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
    AWAITING_SIGNOFF = "awaiting_signoff"
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
    existing_monthly_debt: int = Field(
        default=0,
        ge=0,
        le=1_000_000_000,
        description="Other loan instalments the business pays a month, in rupiah, including "
        "online loans (pinjol). Optional; the policy subtracts it from the instalment allowed.",
    )


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


class AnalyzeResponse(CamelModel):
    """Returned when the analysis has finished; progress streams through Firestore meanwhile."""

    run_id: str
    assessment: Assessment
    status: ApplicationStatus
    latency_ms: int


class FollowUpAnswerRequest(CamelModel):
    text: str | None = None
    audio_path: str | None = Field(
        default=None, description="A recorded answer in Storage, under the caller's own folder"
    )
    declined: bool = Field(default=False, description="The owner prefers not to answer")

    @model_validator(mode="after")
    def _needs_an_answer(self) -> FollowUpAnswerRequest:
        if not (self.text or self.audio_path or self.declined):
            raise ValueError("Give the answer as text or a recording, or record that they declined")
        return self


class ConfirmReadingRequest(CamelModel):
    line: int = Field(ge=1, description="The disputed line on the notebook page")
    amount_rp: int = Field(ge=0, description="The amount the officer read on the photo")


class ConfirmReadingResponse(CamelModel):
    pending: int = Field(description="Disputed lines on this file still to confirm")


class OfferIn(CamelModel):
    """The loan the officer offers. Code computes the instalment and the schedule from it."""

    amount_rp: int = Field(gt=0, le=10_000_000_000)
    tenor_months: int = Field(ge=1, le=60)
    annual_rate_pct: float = Field(ge=0, le=60, description="Annual interest rate, in percent")


class ConditionIn(CamelModel):
    text: str = Field(min_length=5, max_length=200)
    evidence_type: EvidenceType | None = Field(
        default=None, description="The kind of record that meets it, if a record does"
    )


class DecisionRequest(CamelModel):
    action: DecisionAction
    reason: str = Field(min_length=5, description="Every decision needs a written reason")
    offer: OfferIn | None = Field(default=None, description="Required to approve")
    conditions: list[ConditionIn] = Field(
        default_factory=list,
        max_length=10,
        description="To approve: what must happen before the money is paid out. To ask for more "
        "evidence: the records asked for.",
    )
    assessment_agreed: bool | None = Field(
        default=None,
        description="Whether the officer agrees with LedgerLens's assessment of the file. The "
        "pilot dashboard counts how often they do.",
    )
    disagreement_reason: str | None = Field(
        default=None, max_length=500, description="Why the officer disagrees, when they do"
    )

    @model_validator(mode="after")
    def _offer_only_to_approve(self) -> DecisionRequest:
        if self.action is DecisionAction.APPROVE and self.offer is None:
            raise ValueError("Approving needs an offer: the amount, the months and the rate")
        if self.assessment_agreed is False:
            if len((self.disagreement_reason or "").strip()) < 5:
                raise ValueError("Say why you disagree with LedgerLens's assessment")
            self.disagreement_reason = self.disagreement_reason.strip()
        else:
            self.disagreement_reason = None
        if self.action is DecisionAction.DECLINE:
            self.conditions = []
        if self.action is not DecisionAction.APPROVE:
            self.offer = None
        return self


class DecisionResponse(CamelModel):
    state: Literal["recommended", "final"]
    signoff_code: str | None = Field(
        default=None, description="Given to a second person, who signs off the recommendation"
    )
    path: str | None = Field(default=None, description="Where they open it: /app/signoff/CODE")


class SignoffRequest(CamelModel):
    approve: bool
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _a_return_says_why(self) -> SignoffRequest:
        if not self.approve and len(self.note.strip()) < 5:
            raise ValueError("Say why you are sending it back, so the officer knows what to change")
        return self


class OfferAnswerRequest(CamelModel):
    accept: bool


class ShareRequest(CamelModel):
    lender_id: str


class ShareResponse(CamelModel):
    share_code: str
    path: str = Field(description="Where the lender opens the file, e.g. /app/shared/ABCD2345")


class ClaimResponse(CamelModel):
    application_id: str


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
    # credit_history comes only from the SLIK check a lender records (``tools.slik``), never from
    # the evidence or the verifier.
    kind: Literal[
        "discrepancy", "low_confidence", "missing_evidence", "fraud_signal", "credit_history"
    ]
    severity: Literal["low", "medium", "high"]
    text: str
    citations: list[Citation] = Field(default_factory=list)
    follow_up_question: str | None = Field(
        default=None, description="A question for the owner, in Bahasa Indonesia"
    )
    follow_up_question_en: str | None = None
    figures: list[str] = Field(
        default_factory=list, description="Keys of the computed figures the text mentions"
    )
    source: Literal["code", "verifier"] = Field(
        default="verifier", description="Found by an arithmetic check in code, or by the verifier"
    )
    answer: str | None = None
    resolved: bool = Field(
        default=False, description="True once the owner's answer explains the finding"
    )


class LedgerLineOut(CamelModel):
    line: int
    date_text: str | None
    description: str
    amount_text: str | None
    amount_rp: int | None = Field(description="Parsed by code from amount_text, never by the model")
    crossed_out_text: str | None = Field(
        default=None, description="A crossed-out earlier amount on the same line, if any"
    )
    kind: str
    confidence: float


class LedgerPageResult(CamelModel):
    reading_id: str
    model: str
    lines: list[LedgerLineOut]


class ReceiptItemOut(CamelModel):
    name: str
    quantity_text: str | None
    amount_text: str | None
    amount_rp: int | None = Field(description="Parsed by code from amount_text, never by the model")
    confidence: float


class ReceiptOut(CamelModel):
    legible: bool
    merchant: str | None
    date_text: str | None
    handwritten: bool
    items: list[ReceiptItemOut]
    items_sum_rp: int | None = Field(
        description="The item amounts added up by code; null if any amount could not be parsed"
    )
    subtotal_rp: int | None
    tax_rp: int | None
    discount_rp: int | None
    total_text: str | None
    total_rp: int | None = Field(description="Parsed by code from total_text, never by the model")


class ReceiptResult(CamelModel):
    reading_id: str
    model: str
    receipt: ReceiptOut
