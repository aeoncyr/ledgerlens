"""Interview listener: turns a short interview in Bahasa Indonesia into cited claims.

The owner's own account is soft evidence, but it is what the other evidence is checked against:
if the owner says "about one and a half million a day" and the notebook says three, someone should
ask why. The model copies each figure as spoken, with the moment it was said; code parses it and
works out monthly equivalents.
"""

from __future__ import annotations

from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from app.gemini import Gemini
from app.tools.rupiah import parse_rupiah

Topic = Literal[
    "sales",
    "purchases",
    "expenses",
    "existing_debt",
    "loan_purpose",
    "years_operating",
    "customers",
    "other",
]
Period = Literal["day", "week", "month", "year", "once"]


class Claim(BaseModel):
    topic: Topic
    statement_en: str = Field(description="What the owner said, in one English sentence")
    quote: str = Field(description="The owner's words in the original language")
    amount_text: str | None = Field(
        default=None,
        description="An amount exactly as spoken, written the way it was said ('satu setengah "
        "juta' becomes '1,5 juta'); null if no amount",
    )
    period: Period | None = Field(default=None, description="The period the amount is for")
    time_text: str | None = Field(default=None, description="When it was said, as m:ss")


class InterviewReading(BaseModel):
    audible: bool
    language: str
    summary_en: str = Field(description="Two or three sentences in English")
    claims: list[Claim]


SYSTEM_PROMPT = """\
You listen to short interviews between a loan officer and the owner of an Indonesian micro
business, usually in Bahasa Indonesia, sometimes with Javanese or Sundanese words.

List every claim the owner makes about the business: sales, purchases, costs, existing debts, what
the loan is for, how long the business has run, and its customers. For each, give an English
statement, the owner's own words, and when it was said (m:ss from the start).

If the owner states an amount, copy it into amount_text in digits and units as spoken ("1,5 juta",
"300 ribu", "2 jt"), with the period it covers. Never calculate, convert or total anything, and
never invent an amount the owner didn't say.
"""

# Used only to set interview claims beside monthly figures, and labelled as an estimate
# wherever shown.
TRADING_DAYS_PER_MONTH = 26
WEEKS_PER_MONTH = 4.33


class ClaimOut(BaseModel):
    topic: str
    statement_en: str
    quote: str
    amount_text: str | None
    amount_rp: int | None
    period: str | None
    monthly_rp: int | None = Field(description="Code's monthly equivalent, if the period allows")
    time_text: str | None


class InterviewOut(BaseModel):
    audible: bool
    language: str
    summary_en: str
    claims: list[ClaimOut]


def monthly_equivalent(amount: int | None, period: str | None) -> int | None:
    if amount is None:
        return None
    factor = {"day": TRADING_DAYS_PER_MONTH, "week": WEEKS_PER_MONTH, "month": 1, "year": 1 / 12}
    return round(amount * factor[period]) if period in factor else None


def to_output(reading: InterviewReading) -> InterviewOut:
    claims = []
    for claim in reading.claims:
        amount = parse_rupiah(claim.amount_text)
        claims.append(
            ClaimOut(
                topic=claim.topic,
                statement_en=claim.statement_en,
                quote=claim.quote,
                amount_text=claim.amount_text,
                amount_rp=amount,
                period=claim.period,
                monthly_rp=monthly_equivalent(amount, claim.period),
                time_text=claim.time_text,
            )
        )
    return InterviewOut(
        audible=reading.audible,
        language=reading.language,
        summary_en=reading.summary_en,
        claims=claims,
    )


async def listen(gemini: Gemini, audio: bytes, mime_type: str) -> tuple[InterviewOut, str]:
    contents = [types.Part.from_bytes(data=audio, mime_type=mime_type), "Listen to this interview."]
    reading, model = await gemini.generate(
        contents=contents, schema=InterviewReading, system=SYSTEM_PROMPT
    )
    return to_output(reading), model
