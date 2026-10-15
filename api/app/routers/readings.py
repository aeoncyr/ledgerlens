"""Read a single photo on its own: a notebook page or a receipt, from photo to Gemini to Firestore.

These routes let a reader be tried and checked in isolation. The full assessment flow
(applications, evidence, background runs) builds on the same readers.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from google.cloud import firestore

from app.agents.ledger_reader import read_ledger_page
from app.agents.receipt_reader import read_receipt
from app.auth import User, current_user
from app.gemini import Gemini, get_gemini
from app.schemas import LedgerPageResult, ReceiptResult
from app.store import get_firestore

router = APIRouter(prefix="/api/readings", tags=["readings"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_BYTES = 10 * 1024 * 1024


async def read_photo(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a JPEG, PNG, WebP or HEIC photo"
        )
    image = await file.read()
    if len(image) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Photos must be under 10 MB")
    return image


@router.post("/ledger-page", response_model=LedgerPageResult)
async def read_page(
    file: UploadFile,
    user: Annotated[User, Depends(current_user)],
    gemini: Annotated[Gemini, Depends(get_gemini)],
    db: Annotated[firestore.AsyncClient, Depends(get_firestore)],
) -> LedgerPageResult:
    image = await read_photo(file)
    lines, model = await read_ledger_page(gemini, image, file.content_type)

    doc = db.collection("pageReadings").document()
    await doc.set(
        {
            "uid": user.uid,
            "model": model,
            "lines": [line.model_dump(by_alias=True) for line in lines],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    return LedgerPageResult(reading_id=doc.id, model=model, lines=lines)


@router.post("/receipt", response_model=ReceiptResult)
async def read_one_receipt(
    file: UploadFile,
    user: Annotated[User, Depends(current_user)],
    gemini: Annotated[Gemini, Depends(get_gemini)],
    db: Annotated[firestore.AsyncClient, Depends(get_firestore)],
) -> ReceiptResult:
    image = await read_photo(file)
    receipt, model = await read_receipt(gemini, image, file.content_type)

    doc = db.collection("receiptReadings").document()
    await doc.set(
        {
            "uid": user.uid,
            "model": model,
            "receipt": receipt.model_dump(by_alias=True),
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    return ReceiptResult(reading_id=doc.id, model=model, receipt=receipt)
