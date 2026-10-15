"""Photo assessor: does the shop in the photo look like the business described?

Shop and stock photos are physical evidence. They can't prove a figure, but they can make one
implausible: a stall with a nearly empty shelf is unlikely to sell millions a day. The assessor
describes what it sees and never estimates money.
"""

from __future__ import annotations

from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from app.gemini import Gemini


class PhotoAssessment(BaseModel):
    shows_a_business: bool = Field(description="A real shop, stall or workshop is visible")
    business_seen: str = Field(description="What kind of business the photo shows, in a phrase")
    matches_claimed_type: bool = Field(description="Consistent with the business type given")
    stock_level: Literal["empty", "low", "moderate", "full", "not_visible"]
    observations: list[str] = Field(description="Short, concrete things visible in the photo")
    concerns: list[str] = Field(
        default_factory=list,
        description="Signs the photo is not a live capture of this business: a photo of a "
        "screen or print, a watermark, a stock image look, or a different kind of business",
    )
    confidence: float = Field(ge=0, le=1)


SYSTEM_PROMPT = """\
You look at photos a loan officer took of an Indonesian micro business: a warung, food stall,
tailor, workshop or similar. Describe only what is visible. Never estimate sales, income, prices
or any amount of money.

Say whether a real business is visible, what kind, whether it matches the business type you are
given, and how well stocked it looks. List short, concrete observations (for example "two
shelves of rice sacks", "sewing machine in use"). List concerns only if the photo looks like a
picture of a screen or printout, has a watermark, looks like a stock photo, or shows a different
kind of business than claimed.
"""


async def assess_photo(
    gemini: Gemini, image: bytes, mime_type: str, *, business_type: str
) -> tuple[PhotoAssessment, str]:
    contents = [
        types.Part.from_bytes(data=image, mime_type=mime_type),
        f"The business is described as: {business_type}.",
    ]
    return await gemini.generate(contents=contents, schema=PhotoAssessment, system=SYSTEM_PROMPT)
