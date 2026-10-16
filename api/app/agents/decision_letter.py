"""Decision letter: tells the business owner, in plain words, what the lender decided and what next.

It is written once, when a decision becomes final, in English and in Bahasa Indonesia. Every figure
(the amount, the instalment, the total) is a [[key]] that code fills in from the offer, and the
same figure guard as the memo checks every sentence. If Gemini is busy, slow or out of quota, a
fixed template says the same thing, so the owner always hears back.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.writing import FIGURE_RULES, generate_checked, number_tokens
from app.gemini import Gemini
from app.schemas import DecisionAction
from app.tools.facts import FactTable

log = logging.getLogger(__name__)

# The decision request waits for the letter; past this, the template is used instead.
LETTER_TIMEOUT_SECONDS = 25.0


class DecisionLetter(BaseModel):
    en: str = Field(description="Three to five sentences in plain English, figures as [[key]]")
    id: str = Field(description="The same letter in simple, friendly Bahasa Indonesia")


SYSTEM_PROMPT = f"""\
You write a short letter from an Indonesian lender (a rural bank, cooperative or microfinance
lender) to the owner of a micro business, telling them what the lender decided about their loan
request. The owner reads it on a phone. Write three to five short sentences in plain English, and
the same letter in simple, friendly Bahasa Indonesia (use "Anda").

- approve: say the loan is offered, with the amount, the monthly instalment, the number of months
  and the total repaid. If there are conditions, say they must be met before the money is paid out
  and that they are listed below the letter. Tell them to check the schedule, then accept or
  decline in the app.
- decline: say kindly that the lender is not offering a loan now, and explain the officer's reason
  in plain words without internal jargon. Never accuse anyone of fraud. Say the file stays theirs:
  they can add records and share it with this or another lender.
- request_more: say nothing has been decided yet, name the records the lender asks for, and tell
  them to add the records in the app, then tap "Send to my lender".

Mention that two people at the lender checked an approval or a decline. Never mention scores,
ratings, the lender's internal policy or the word "AI". Do not invent conditions, dates or terms.

{FIGURE_RULES}
"""


def letter_facts(offer: dict[str, Any] | None, requested_amount: int) -> FactTable:
    facts = FactTable()
    facts.add("requested_amount", "The amount the owner asked for", "rupiah", requested_amount)
    if offer:
        facts.add("offer_amount", "The amount offered", "rupiah", offer["amountRp"])
        facts.add("offer_months", "Monthly instalments", "count", offer["tenorMonths"])
        facts.add("offer_instalment", "The monthly instalment", "rupiah", offer["instalmentRp"])
        facts.add("offer_total", "Everything repaid over the loan", "rupiah", offer["totalRp"])
    return facts


def template_letter(
    action: DecisionAction, alias: str, reason: str, conditions: list[str]
) -> DecisionLetter:
    """The fallback: the same message in fixed words, figures still as [[keys]]."""
    n = len(conditions)
    if action is DecisionAction.APPROVE:
        before_en = (
            f" Before the money is paid out, your lender asks for {n} "
            f"thing{'s' if n > 1 else ''}, listed below."
            if n
            else ""
        )
        before_id = (
            f" Sebelum dana dicairkan, ada {n} hal yang diminta, tercantum di bawah." if n else ""
        )
        return DecisionLetter(
            en=f"Good news: your lender offers {alias} a loan of [[offer_amount]]. You would repay "
            "[[offer_instalment]] a month for [[offer_months]] months, [[offer_total]] in all."
            f"{before_en} Check the repayment schedule, then accept or decline the offer. Two "
            "people at the lender checked this decision.",
            id=f"Kabar baik: pemberi pinjaman Anda menawarkan pinjaman [[offer_amount]] untuk "
            f"{alias}. Cicilannya [[offer_instalment]] per bulan selama [[offer_months]] bulan, "
            f"total [[offer_total]].{before_id} Periksa jadwal cicilannya, lalu terima atau tolak "
            "tawaran ini. Keputusan ini sudah diperiksa oleh dua orang di pemberi pinjaman.",
        )
    if action is DecisionAction.DECLINE:
        return DecisionLetter(
            en=f"Your lender is not offering {alias} a loan at this time. The reason they gave: "
            f"“{reason}” Two people at the lender checked this decision. Your file stays yours: "
            "you can add records, check it again and share it with this or another lender.",
            id=f"Pemberi pinjaman Anda belum menawarkan pinjaman untuk {alias} saat ini. Alasan "
            f"yang diberikan: “{reason}” Keputusan ini sudah diperiksa oleh dua orang. Berkas "
            "ini tetap milik Anda: Anda bisa menambah catatan, memeriksanya lagi, dan "
            "membagikannya ke pemberi pinjaman ini atau yang lain.",
        )
    asked = "; ".join(conditions)
    return DecisionLetter(
        en=f"Your lender needs a few more records from {alias} before deciding. "
        + (f"They ask for: {asked}. " if asked else f"They explain: “{reason}” ")
        + "Add them under Your records, then tap Send to my lender. Nothing has been decided yet.",
        id=f"Pemberi pinjaman Anda memerlukan beberapa catatan lagi dari {alias} sebelum "
        "memutuskan. "
        + (f"Yang diminta: {asked}. " if asked else f"Penjelasannya: “{reason}” ")
        + "Tambahkan di bagian Catatan Anda, lalu ketuk Kirim ke pemberi pinjaman. Belum ada "
        "keputusan.",
    )


async def write_letter(
    gemini: Gemini,
    *,
    action: DecisionAction,
    alias: str,
    reason: str,
    conditions: list[str],
    offer: dict[str, Any] | None,
    requested_amount: int,
) -> dict[str, Any]:
    """The letter in both languages, figures filled in. Never raises: falls back to the template."""
    facts = letter_facts(offer, requested_amount)
    # The alias and the officer's conditions may contain numbers the letter can repeat exactly.
    quoted = number_tokens([alias, *conditions])
    contents = [
        "Decision:\n"
        + json.dumps(
            {
                "action": action.value,
                "business": alias,
                "officer_reason": reason,
                "conditions" if action is DecisionAction.APPROVE else "records_asked_for": (
                    conditions
                ),
                "facts": facts.for_prompt(),
            },
            ensure_ascii=False,
            indent=1,
        )
    ]
    try:
        letter, model, problems = await asyncio.wait_for(
            generate_checked(
                gemini,
                contents=contents,
                schema=DecisionLetter,
                system=SYSTEM_PROMPT,
                facts=facts,
                quoted=quoted,
            ),
            timeout=LETTER_TIMEOUT_SECONDS,
        )
        if not isinstance(letter, DecisionLetter) or not (letter.en.strip() and letter.id.strip()):
            raise ValueError("the letter came back empty")
        source: dict[str, Any] = {"source": "gemini", "model": model, "figureProblems": problems}
    except Exception as exc:  # busy, slow, out of quota: the owner still gets a letter
        log.warning("decision letter fell back to the template: %r", exc)
        letter = template_letter(action, alias, reason, conditions)
        source = {"source": "template", "model": None, "figureProblems": []}
    return {"en": facts.render(letter.en), "id": facts.render(letter.id), **source}
