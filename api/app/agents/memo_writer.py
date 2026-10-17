"""Memo writer: the credit memo in the 5C format lenders already use, and a summary for the owner.

The 5Cs are Character, Capacity, Capital, Collateral and Conditions. Every figure is a [[key]]
computed by code, and every claim is cited, so the memo can be checked line by line. The outcome
and the suggested instalment come from the policy tool; the writer explains them, it doesn't set
them. The owner's summary is in Bahasa Indonesia: what was verified, what is missing, and how to
make the file stronger.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.agents.verifier import CitationOut
from app.agents.writing import FIGURE_RULES, generate_checked
from app.gemini import Gemini
from app.tools.facts import FactTable


class MemoSection(BaseModel):
    text: str = Field(description="Two to four sentences in English, figures as [[key]]")
    citations: list[CitationOut]


class OwnerSummary(BaseModel):
    verified: str = Field(description="What the evidence confirmed, in Bahasa Indonesia")
    missing: str = Field(description="What is missing or unclear, in Bahasa Indonesia")
    tips: list[str] = Field(description="Three practical ways to strengthen the file, in Bahasa")
    verified_en: str = Field(description="The same as verified, in plain English")
    missing_en: str = Field(description="The same as missing, in plain English")
    tips_en: list[str] = Field(description="The same tips, in plain English")


class MemoDraft(BaseModel):
    headline: str = Field(description="One sentence: the outcome and the main reason")
    character: MemoSection
    capacity: MemoSection
    capital: MemoSection
    collateral: MemoSection
    conditions: MemoSection
    officer_next_steps: list[str] = Field(description="Two to four concrete next steps")
    owner_summary: OwnerSummary


SYSTEM_PROMPT = f"""\
You write credit memos for loan officers at Indonesian rural banks, cooperatives and microfinance
lenders, about informal micro businesses. You receive the case file, the cross-check findings and
the outcome that the lender's policy produced. You explain; you never change the outcome, never
give a score and never recommend approving or declining. The officer decides.

Write the five Cs:
- character: how long the business has run, how consistent the owner's account is with the
  evidence, and any open questions.
- capacity: cash flow. The low end rests on hard evidence only; the high end includes the notebook.
  Explain the suggested maximum instalment and how it compares with the requested one. Mention
  the other loan instalments a month the application declares; when the case file has a
  slik_check, which the lender ran and recorded, the policy used its instalments instead, so say
  so. When the facts list
  stress_drop_pct (code's stress test, which assumes costs move with sales), say how far sales
  could fall before the request is above the policy's limit.
- capital: stock and assets visible in the photos, and what the business reinvests in purchases.
- collateral: for KUR loans up to [[kur_collateral_free_limit]], extra collateral may not be
  required; say what is visible and that the decision rests on cash flow.
- conditions: the loan's purpose and amount, and the business's market as far as the evidence shows.

Cite the evidence for every claim. If evidence for a C is missing, say so plainly instead of
guessing. Then give the officer two to four next steps, and write the owner's summary in simple,
friendly Bahasa Indonesia with three practical tips (for example "minta nota dari agen setiap
belanja"), and the same summary in plain English. The owner reads this summary themselves: speak to
them directly and kindly, never mention scores, outcomes or the lender's policy, and never accuse.

{FIGURE_RULES}
"""


async def write_memo(
    gemini: Gemini,
    case_file: dict[str, Any],
    findings: list[dict[str, Any]],
    outcome: dict[str, Any],
    facts: FactTable,
    quoted: set[str],
) -> tuple[MemoDraft, str, list[str]]:
    contents = [
        "Case file:\n" + json.dumps(case_file, ensure_ascii=False, indent=1),
        "Findings:\n" + json.dumps(findings, ensure_ascii=False, indent=1),
        "Outcome from the lender's policy:\n" + json.dumps(outcome, ensure_ascii=False, indent=1),
    ]
    return await generate_checked(
        gemini,
        contents=contents,
        schema=MemoDraft,
        system=SYSTEM_PROMPT,
        facts=facts,
        quoted=quoted,
    )
