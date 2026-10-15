"""Receipt reader: turns a photo of a supplier receipt (nota) into structured items and totals.

Receipts are medium-tier evidence: printed by a till or written by a supplier, they show what the
business really bought. As with the ledger reader, the model only copies text. Amounts are parsed
by ``parse_rupiah`` and the items are added up in code, so the check that the items match the
printed total never depends on the model's arithmetic.
"""

from __future__ import annotations

from google.genai import types
from pydantic import BaseModel, Field

from app.gemini import Gemini
from app.schemas import ReceiptItemOut, ReceiptOut
from app.tools.rupiah import parse_rupiah


class ReceiptItem(BaseModel):
    name: str = Field(description="The item as printed or written")
    quantity_text: str | None = Field(default=None, description="The quantity as written, or null")
    amount_text: str | None = Field(
        default=None,
        description="The line's amount (quantity times unit price) exactly as written, or null",
    )
    confidence: float = Field(ge=0, le=1, description="How sure you are that you read it correctly")


class ReceiptReading(BaseModel):
    legible: bool = Field(description="False if the receipt cannot be read at all")
    merchant: str | None = Field(default=None, description="The seller's name as printed, or null")
    date_text: str | None = Field(default=None, description="The date exactly as written, or null")
    items: list[ReceiptItem]
    subtotal_text: str | None = Field(default=None, description="The subtotal as written, or null")
    tax_text: str | None = Field(default=None, description="Tax or service charge, or null")
    discount_text: str | None = Field(default=None, description="Any discount, or null")
    total_text: str | None = Field(
        default=None, description="The amount the buyer had to pay, exactly as written, or null"
    )
    handwritten: bool = Field(description="True if the receipt is written by hand")


SYSTEM_PROMPT = """\
You read photos of receipts from Indonesian shops, restaurants and suppliers, printed or handwritten
(a handwritten one is often called a nota). Your only job is to copy what is written. Never
calculate, total, convert or guess.

Return:
- merchant: the seller's name as printed, or null.
- date_text: the date as written, or null.
- items: one entry per purchased item, top to bottom. name as written; quantity_text as written;
  amount_text is the amount printed on that item's line, which is usually quantity times unit price.
  Skip lines that are only notes, modifiers with no price, or totals.
- subtotal_text, tax_text, discount_text: as written, or null if absent.
- total_text: the final amount the buyer had to pay (total, grand total, jumlah), not the cash
  handed over and not the change (kembali).
- Copy every amount exactly as written, keeping separators and units
  (for example "60.000", "1,250,000", "75rb"). Never convert it to a full number.
- confidence: lower it whenever a character is unclear. Never invent missing text.

Set legible to false only if the receipt cannot be read at all.
"""


def to_output(reading: ReceiptReading) -> ReceiptOut:
    items = [
        ReceiptItemOut(
            name=item.name,
            quantity_text=item.quantity_text,
            amount_text=item.amount_text,
            amount_rp=parse_rupiah(item.amount_text),
            confidence=item.confidence,
        )
        for item in reading.items
    ]
    parsed = [item.amount_rp for item in items]
    return ReceiptOut(
        legible=reading.legible,
        merchant=reading.merchant,
        date_text=reading.date_text,
        handwritten=reading.handwritten,
        items=items,
        items_sum_rp=sum(parsed) if parsed and None not in parsed else None,
        subtotal_rp=parse_rupiah(reading.subtotal_text),
        tax_rp=parse_rupiah(reading.tax_text),
        discount_rp=_discount(reading.discount_text),
        total_text=reading.total_text,
        total_rp=parse_rupiah(reading.total_text),
    )


def _discount(text: str | None) -> int | None:
    """Discounts are often printed negative ("-5.000" or "(5.000)"); keep the size only."""
    return parse_rupiah(text.strip().lstrip("-(").rstrip(")")) if text else None


async def read_receipt(gemini: Gemini, image: bytes, mime_type: str) -> tuple[ReceiptOut, str]:
    """Read one receipt. Returns the parsed receipt and the model that read it."""
    contents = [types.Part.from_bytes(data=image, mime_type=mime_type), "Read this receipt."]
    reading, model = await gemini.generate(
        contents=contents, schema=ReceiptReading, system=SYSTEM_PROMPT
    )
    return to_output(reading), model
