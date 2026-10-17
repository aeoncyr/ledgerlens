"""The lender's own settings: who they are and the credit policy LedgerLens applies for them.

Each officer keeps one profile in ``lenders/{uid}``, the document that also holds their
integration settings (``app.integrations``): the lender's name and type, and the policy terms
``app.tools.policy`` uses: the share of net cash flow that may go to repayments, the haircut by
outcome, the longest term and the rate the lender's product is priced at. Until an officer saves
their own, the starting values apply, and the credit file says so.

Every number here is the lender's choice, checked by code; none of it is written by a model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore
from pydantic import Field

from app.auth import User, current_user
from app.schemas import CamelModel
from app.store import get_firestore
from app.tools.policy import LenderPolicy
from app.tools.slik import SlikCheck

router = APIRouter(prefix="/api/lender", tags=["lender"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

LenderType = Literal["bpr", "bprs", "cooperative", "microfinance", "other"]
Product = Literal["kur_micro", "own"]

# The rate each product preset prices a loan at, in percent a year. KUR micro loans carry a
# government-set rate; "own" is the lender's own product, at the rate they type.
PRODUCT_RATE: dict[str, float] = {"kur_micro": 6.0}

_DEFAULT = LenderPolicy()


class LenderProfile(CamelModel):
    """The settings form, in whole percent where the policy keeps a fraction."""

    name: str | None = Field(default=None, description="The lender's name, shown to owners")
    type: LenderType | None = None
    product: Product = "kur_micro"
    annual_rate_pct: float = Field(default=round(_DEFAULT.monthly_rate * 1200, 4))
    max_installment_ratio_pct: float = Field(default=round(_DEFAULT.max_installment_ratio * 100, 2))
    haircut_verified_pct: float = Field(default=round(_DEFAULT.haircut_verified * 100, 2))
    haircut_partial_pct: float = Field(default=round(_DEFAULT.haircut_partial * 100, 2))
    max_tenor_months: int = Field(default=_DEFAULT.max_tenor_months)


class LenderProfileOut(LenderProfile):
    saved: bool = Field(description="False until the officer saves their own settings")
    updated_at: str | None = None
    defaults: LenderProfile = Field(default_factory=LenderProfile)


def problems(profile: LenderProfile) -> str | None:
    """What is wrong with the settings, in plain words, or None."""
    name = (profile.name or "").strip()
    if len(name) < 2:
        return "Enter your lender's name, as owners know it (for example BPR Sejahtera)."
    if len(name) > 80:
        return "Keep the lender's name under 80 characters."
    if profile.type is None:
        return "Choose what kind of lender you are."
    if not 0 <= profile.annual_rate_pct <= 60:
        return "The rate should be between 0% and 60% a year."
    if not 5 <= profile.max_installment_ratio_pct <= 60:
        return "The share of cash flow for repayments should be between 5% and 60%."
    if not 0 <= profile.haircut_verified_pct <= 90:
        return "The haircut for a verified file should be between 0% and 90%."
    if not 0 <= profile.haircut_partial_pct <= 90:
        return "The haircut for a partly verified file should be between 0% and 90%."
    if profile.haircut_partial_pct < profile.haircut_verified_pct:
        return (
            "A partly verified file should be discounted at least as much as a verified one: "
            "make its haircut the same or larger."
        )
    if not 1 <= profile.max_tenor_months <= 60:
        return "The longest term should be between 1 and 60 months."
    return None


def policy_for(stored: dict[str, Any] | None) -> LenderPolicy:
    """The policy a lender's saved profile sets; the starting values if they have none."""
    saved = (stored or {}).get("policy")
    if not saved:
        return LenderPolicy()
    return LenderPolicy(
        lender_name=(stored or {}).get("name"),
        max_installment_ratio=saved["maxInstallmentRatio"],
        monthly_rate=saved["annualRatePct"] / 100 / 12,
        haircut_verified=saved["haircutVerified"],
        haircut_partial=saved["haircutPartial"],
        max_tenor_months=saved["maxTenorMonths"],
    )


async def lender_profile(db: firestore.AsyncClient, uid: str | None) -> dict[str, Any] | None:
    """The officer's ``lenders/{uid}`` document, if they have one."""
    if not uid:
        return None
    snapshot = await db.collection("lenders").document(uid).get()
    return (snapshot.to_dict() or {}) if snapshot.exists else None


async def lender_policy(db: firestore.AsyncClient, uid: str | None) -> LenderPolicy:
    return policy_for(await lender_profile(db, uid))


async def slik_of(ref: Any) -> SlikCheck | None:
    """The SLIK check the lender recorded on a file (``applications/{id}/lender/slik``), if any.
    It lives under the file, so it goes when the owner deletes the file, and only the lender's
    people can read it (the rules' catch-all for the file's lender-only documents)."""
    snapshot = await ref.collection("lender").document("slik").get()
    data = (snapshot.to_dict() or {}) if snapshot.exists else None
    return SlikCheck.model_validate(data) if data else None


def _out(stored: dict[str, Any] | None) -> LenderProfileOut:
    stored = stored or {}
    saved = stored.get("policy")
    if not saved:
        return LenderProfileOut(
            name=stored.get("name"), type=stored.get("type"), saved=False, updated_at=None
        )
    return LenderProfileOut(
        name=stored.get("name"),
        type=stored.get("type"),
        product=saved.get("product", "own"),
        annual_rate_pct=saved["annualRatePct"],
        max_installment_ratio_pct=round(saved["maxInstallmentRatio"] * 100, 2),
        haircut_verified_pct=round(saved["haircutVerified"] * 100, 2),
        haircut_partial_pct=round(saved["haircutPartial"] * 100, 2),
        max_tenor_months=saved["maxTenorMonths"],
        saved=True,
        updated_at=saved.get("updatedAt"),
    )


@router.get("/profile", response_model=LenderProfileOut)
async def get_profile(user: CurrentUser, db: Db) -> LenderProfileOut:
    return _out(await lender_profile(db, user.uid))


@router.put("/profile", response_model=LenderProfileOut)
async def put_profile(body: LenderProfile, user: CurrentUser, db: Db) -> LenderProfileOut:
    """Save the lender's name, type and policy. Files already checked keep the policy they were
    checked with until the officer re-applies it on the file."""
    if body.product in PRODUCT_RATE:
        body.annual_rate_pct = PRODUCT_RATE[body.product]
    problem = problems(body)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    ref = db.collection("lenders").document(user.uid)
    snapshot = await ref.get()
    data = (snapshot.to_dict() or {}) if snapshot.exists else {}
    # The integration settings in the same document are kept as they are.
    data.update(
        {
            "name": (body.name or "").strip(),
            "type": body.type,
            "policy": {
                "product": body.product,
                "annualRatePct": body.annual_rate_pct,
                "maxInstallmentRatio": round(body.max_installment_ratio_pct / 100, 4),
                "haircutVerified": round(body.haircut_verified_pct / 100, 4),
                "haircutPartial": round(body.haircut_partial_pct / 100, 4),
                "maxTenorMonths": body.max_tenor_months,
                "updatedAt": datetime.now(UTC).isoformat(),
            },
        }
    )
    await ref.set(data)
    return _out(data)
