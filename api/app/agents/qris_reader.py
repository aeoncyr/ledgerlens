"""QRIS reader: turns a screenshot of a merchant's QRIS or e-wallet history into transactions.

QRIS (Indonesia's national QR payment standard) history is hard evidence: money a payment provider
saw arrive. The model copies rows and printed totals exactly; code parses the amounts, adds up the
rows and checks them against the printed totals. A screenshot whose rows can't add up to its own
total is a sign that it was edited, and that check is pure arithmetic, so it is done here in code.
"""

from __future__ import annotations

from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from app.gemini import Gemini
from app.tools.rupiah import parse_rupiah


class QrisRow(BaseModel):
    row: int = Field(description="1-based position in the list, from the top")
    date_text: str | None = Field(default=None, description="Date as shown, or null")
    time_text: str | None = Field(default=None, description="Time as shown, or null")
    amount_text: str = Field(description="The amount exactly as shown, e.g. 'Rp25.000'")
    direction: Literal["in", "out"] = Field(description="in: money received; out: paid out")
    label: str | None = Field(default=None, description="Payer or reference as shown, or null")
    confidence: float = Field(ge=0, le=1)


class QrisTotal(BaseModel):
    period_text: str = Field(description="The period the total covers, as shown")
    amount_text: str = Field(description="The total exactly as shown")
    count_text: str | None = Field(default=None, description="Number of transactions, if shown")


class QrisReading(BaseModel):
    legible: bool
    app_name: str | None = Field(default=None, description="The app or bank, as shown")
    merchant_name: str | None = Field(default=None, description="Merchant name as shown")
    rows: list[QrisRow]
    totals: list[QrisTotal] = Field(default_factory=list)
    is_screenshot: bool = Field(
        description="True for a phone screenshot; false for a photo of a screen, paper or a note"
    )
    editing_signs: list[str] = Field(
        default_factory=list,
        description="Visual signs of editing: mismatched fonts, misaligned or blurred digits, "
        "inconsistent spacing. Describe what you see; never judge the arithmetic.",
    )


SYSTEM_PROMPT = """\
You read screenshots of QRIS, e-wallet and mobile-banking transaction history from Indonesian
merchant apps. Your only job is to copy what is shown. Never calculate, total, convert or guess.

- rows: every transaction visible, top to bottom. amount_text exactly as shown, with "Rp",
  separators and signs. direction is "in" for money received (payment received, dana masuk,
  terima, kredit, +) and "out" for money paid out (tarik, transfer keluar, debit, -).
- totals: any total the screen prints (for a day, a week or a month), with its period and the
  number of transactions if shown.
- editing_signs: look closely at the digits and text. Report visible signs that the image was
  edited, such as one amount in a different font, size or colour, misaligned digits, smudged areas
  or inconsistent spacing. Leave it empty if you see none. Do not do any arithmetic.
- Lower confidence for any value you cannot read clearly. Never invent missing text.
"""


class QrisRowOut(BaseModel):
    row: int
    date_text: str | None
    time_text: str | None
    amount_text: str
    amount_rp: int | None
    direction: str
    label: str | None
    confidence: float


class QrisTotalOut(BaseModel):
    period_text: str
    amount_text: str
    amount_rp: int | None
    count: int | None


class QrisOut(BaseModel):
    legible: bool
    app_name: str | None
    merchant_name: str | None
    is_screenshot: bool
    editing_signs: list[str]
    rows: list[QrisRowOut]
    totals: list[QrisTotalOut]
    rows_in_sum_rp: int = Field(description="Incoming rows added up by code")
    arithmetic_problems: list[str] = Field(description="Where the rows can't add up to a total")


def _count(text: str | None) -> int | None:
    digits = "".join(ch for ch in text or "" if ch.isdigit())
    return int(digits) if digits else None


def to_output(reading: QrisReading) -> QrisOut:
    rows = [
        QrisRowOut(
            row=row.row,
            date_text=row.date_text,
            time_text=row.time_text,
            amount_text=row.amount_text,
            amount_rp=_unsigned(parse_rupiah(row.amount_text.lstrip("+-").strip())),
            direction=row.direction,
            label=row.label,
            confidence=row.confidence,
        )
        for row in reading.rows
    ]
    totals = [
        QrisTotalOut(
            period_text=total.period_text,
            amount_text=total.amount_text,
            amount_rp=parse_rupiah(total.amount_text),
            count=_count(total.count_text),
        )
        for total in reading.totals
    ]
    incoming = [row for row in rows if row.direction == "in" and row.amount_rp is not None]
    rows_sum = sum(row.amount_rp or 0 for row in incoming)
    problems = []
    for total in totals:
        if total.amount_rp is None:
            continue
        if rows_sum > total.amount_rp:
            problems.append(
                f"The visible incoming rows add up to {_rp(rows_sum)}, more than the printed "
                f"total of {_rp(total.amount_rp)} for {total.period_text}."
            )
        elif total.count == len(incoming) and rows_sum != total.amount_rp:
            problems.append(
                f"All {total.count} transactions for {total.period_text} are visible, but they "
                f"add up to {_rp(rows_sum)}, not the printed total of {_rp(total.amount_rp)}."
            )
    return QrisOut(
        legible=reading.legible,
        app_name=reading.app_name,
        merchant_name=reading.merchant_name,
        is_screenshot=reading.is_screenshot,
        editing_signs=reading.editing_signs,
        rows=rows,
        totals=totals,
        rows_in_sum_rp=rows_sum,
        arithmetic_problems=problems,
    )


def _rp(value: int) -> str:
    return "Rp " + f"{value:,}".replace(",", ".")


def _unsigned(value: int | None) -> int | None:
    return None if value is None else abs(value)


async def read_qris(gemini: Gemini, image: bytes, mime_type: str) -> tuple[QrisOut, str]:
    contents = [types.Part.from_bytes(data=image, mime_type=mime_type), "Read this history."]
    reading, model = await gemini.generate(
        contents=contents, schema=QrisReading, system=SYSTEM_PROMPT
    )
    return to_output(reading), model
