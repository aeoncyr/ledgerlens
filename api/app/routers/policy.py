"""The lender's own checks on a file: re-apply their policy, and record the SLIK check they ran.

Both are Python only. Re-applying recomputes the policy section of the stored credit file with the
officer's saved settings (``routers/lender.py``) and the SLIK check, if one is recorded; it runs
when the officer asks, when they open a file an owner shared, and when they record or remove a SLIK
check. A file waiting for sign-off, or with a loan on offer, keeps the policy it was decided on.

LedgerLens never queries SLIK. The lender runs the check in its own system, with the owner's
consent, and the officer types four figures here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.analysis.pipeline import Context
from app.analysis.reapply import reapply_policy
from app.auth import User, current_user
from app.routers.analysis import _check_not_settled, _is_running
from app.routers.applications import OFFICER, _audit, _owned_application
from app.routers.lender import lender_policy, slik_of
from app.schemas import CamelModel
from app.store import get_firestore
from app.tools.slik import SlikCheck, problems

router = APIRouter(prefix="/api/applications", tags=["policy"])

Db = Annotated[firestore.AsyncClient, Depends(get_firestore)]
CurrentUser = Annotated[User, Depends(current_user)]

RUNNING = "A check is running on this file. Wait for it to finish, then try again."


class PolicyAppliedResponse(CamelModel):
    applied: bool
    lender_name: str | None = None
    max_installment: int | None = None
    within_policy: bool | None = None
    memo_note: str | None = None


async def apply_lender_policy(
    db: firestore.AsyncClient, ref: Any, data: dict[str, Any], user: User, *, trigger: str
) -> PolicyAppliedResponse:
    """Re-apply the policy of the file's officer, and its SLIK check, to the stored credit file."""
    memo_ref = ref.collection("memo").document("current")
    memo = await memo_ref.get()
    saved = await ref.collection("memo").document("context").get()
    if not (memo.exists and saved.exists):
        return PolicyAppliedResponse(applied=False)
    policy = await lender_policy(db, data.get("officerUid"))
    updates = reapply_policy(
        memo.to_dict() or {}, Context.model_validate(saved.to_dict()), policy, await slik_of(ref)
    )
    await memo_ref.update(updates)
    await ref.update(
        {
            "assessment": updates["assessment"],
            "evidenceStrength": updates["policy"]["evidenceStrength"],
            "flagCount": len(updates["findings"]),
        }
    )
    await _audit(
        ref,
        user,
        "policy_reapplied",
        trigger=trigger,
        lender=policy.lender_name,
        maxInstallment=updates["policy"]["maxInstallment"],
        withinPolicy=updates["policy"]["withinPolicy"],
    )
    return PolicyAppliedResponse(
        applied=True,
        lender_name=policy.lender_name,
        max_installment=updates["policy"]["maxInstallment"],
        within_policy=updates["policy"]["withinPolicy"],
        memo_note=updates["memoNote"],
    )


async def apply_if_open(
    db: firestore.AsyncClient, ref: Any, data: dict[str, Any], user: User, *, trigger: str
) -> None:
    """Re-apply the policy unless a decision rests on the file or a check is running."""
    if _is_running(data):
        return
    try:
        _check_not_settled(data)
    except HTTPException:
        return
    await apply_lender_policy(db, ref, data, user, trigger=trigger)


def _open_for_changes(data: dict[str, Any]) -> None:
    _check_not_settled(data)
    if _is_running(data):
        raise HTTPException(status.HTTP_409_CONFLICT, RUNNING)


@router.post("/{application_id}/policy", response_model=PolicyAppliedResponse)
async def reapply(application_id: str, user: CurrentUser, db: Db) -> PolicyAppliedResponse:
    """Apply the officer's current settings to this file again. No Gemini call is made."""
    ref, data = await _owned_application(db, application_id, user, (OFFICER,))
    _open_for_changes(data)
    result = await apply_lender_policy(db, ref, data, user, trigger="officer")
    if not result.applied:
        raise HTTPException(status.HTTP_409_CONFLICT, "Check the evidence first.")
    return result


@router.put("/{application_id}/slik", response_model=PolicyAppliedResponse)
async def record_slik(
    application_id: str, body: SlikCheck, user: CurrentUser, db: Db
) -> PolicyAppliedResponse:
    """Record the SLIK check the lender ran, then re-apply the policy with its instalments."""
    ref, data = await _owned_application(db, application_id, user, (OFFICER,))
    _open_for_changes(data)
    problem = problems(body, datetime.now(UTC).date())
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    await (
        ref.collection("lender")
        .document("slik")
        .set(
            {
                **body.model_dump(mode="json", by_alias=True),
                "recordedBy": user.uid,
                "recordedAt": datetime.now(UTC).isoformat(),
            }
        )
    )
    await _audit(
        ref,
        user,
        "slik_recorded",
        checkedOn=body.checked_on.isoformat(),
        activeFacilities=body.active_facilities,
        monthlyInstalments=body.monthly_instalments,
        worstCollectibility=body.worst_collectibility,
    )
    return await apply_lender_policy(db, ref, data, user, trigger="slik")


@router.delete("/{application_id}/slik", response_model=PolicyAppliedResponse)
async def remove_slik(application_id: str, user: CurrentUser, db: Db) -> PolicyAppliedResponse:
    """Remove a SLIK check recorded by mistake; the policy goes back to the declared figure."""
    ref, data = await _owned_application(db, application_id, user, (OFFICER,))
    _open_for_changes(data)
    await ref.collection("lender").document("slik").delete()
    await _audit(ref, user, "slik_removed")
    return await apply_lender_policy(db, ref, data, user, trigger="slik_removed")
