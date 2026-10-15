"""Ledger reader: turns a photo of a handwritten notebook page into structured line items.

The model only copies what is written. Amounts come back exactly as written ("1,2jt") and are
converted to rupiah by ``parse_rupiah``, so the model never does arithmetic.
"""

from __future__ import annotations

from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from app.gemini import Gemini
from app.schemas import LedgerLineOut
from app.tools.rupiah import parse_rupiah


class LedgerLine(BaseModel):
    line: int = Field(description="1-based line number on the page, counting from the top")
    date_text: str | None = Field(
        default=None, description="The date exactly as written on this line, or null"
    )
    description: str = Field(description="What the line says, copied as written")
    amount_text: str | None = Field(
        default=None,
        description="The amount exactly as written, including units such as rb or jt; null if none",
    )
    crossed_out_text: str | None = Field(
        default=None,
        description="An amount that was crossed out and rewritten on this line, exactly as written",
    )
    kind: Literal["sale", "purchase", "receivable", "expense", "other"]
    confidence: float = Field(ge=0, le=1, description="How sure you are that you read it correctly")


class LedgerReading(BaseModel):
    legible: bool = Field(description="False if the page cannot be read at all")
    lines: list[LedgerLine]
    notes: str | None = Field(default=None, description="Anything unusual about the page")


SYSTEM_PROMPT = """\
You read photos of handwritten bookkeeping notebooks kept by Indonesian micro businesses.
Your only job is to copy what is written. Never calculate, total, convert or guess.

For every line that has writing on it, return:
- line: its position on the page, counting from 1 at the top.
- date_text: the date as written (for example "12/9"), or null.
- description: the words as written, in the original language and shorthand.
- amount_text: the amount exactly as written, keeping units and separators
  (for example "75rb", "1,2jt", "610.000"). Never convert it to a full number.
  If an amount is crossed out and rewritten, amount_text is only the final amount; put the
  crossed-out one in crossed_out_text.
- kind: sale (jual, laku, omzet, penjualan), purchase (belanja, beli, kulakan, agen),
  receivable (kasbon, utang pelanggan), expense (bayar, listrik, sewa, arisan, gaji) or other.
  A dated line recording a day's takings is a sale, including "Sabtu pasar" or "hari pasar"
  (market-day sales). It is a purchase only if it says what was bought or from whom.
- confidence: lower it whenever a character is unclear. Never invent missing text.

Skip ruled lines with no writing. Set legible to false only if the page cannot be read at all.
"""

# The page is read twice with differently worded instructions. Disagreements between the two
# readings mark a value as low-confidence for the loan officer to confirm.
VARIANT_HINTS = (
    "Read the page from top to bottom, one line at a time.",
    "First find every amount on the page, then read the words on the same line as each amount.",
)


def to_output(line: LedgerLine) -> LedgerLineOut:
    return LedgerLineOut(
        line=line.line,
        date_text=line.date_text,
        description=line.description,
        amount_text=line.amount_text,
        amount_rp=parse_rupiah(line.amount_text),
        crossed_out_text=line.crossed_out_text,
        kind=line.kind,
        confidence=line.confidence,
    )


async def read_ledger_page(
    gemini: Gemini, image: bytes, mime_type: str, *, variant: int = 0
) -> tuple[list[LedgerLineOut], str]:
    """Read one notebook page. Returns the parsed lines and the model that read them."""
    contents = [
        types.Part.from_bytes(data=image, mime_type=mime_type),
        VARIANT_HINTS[variant % len(VARIANT_HINTS)],
    ]
    reading, model = await gemini.generate(
        contents=contents, schema=LedgerReading, system=SYSTEM_PROMPT
    )
    return [to_output(line) for line in reading.lines], model
