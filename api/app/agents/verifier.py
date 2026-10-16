"""Verifier: cross-checks every source against the others, like a careful credit analyst.

It receives the case file: the business, the request, every reading with its locators, the figures
code computed, and the arithmetic checks code already ran. It returns findings, each cited to the
evidence, with a polite follow-up question for the owner where an answer could resolve it, and the
points where the sources agree. Severity drives the outcome, so the rules for it are explicit.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.writing import FIGURE_RULES, generate_checked
from app.gemini import Gemini
from app.tools.facts import FactTable


class CitationOut(BaseModel):
    evidence_id: str
    locator: str = Field(description="Where in that evidence, copied from the case file")


class VerifierFinding(BaseModel):
    check_id: str | None = Field(
        default=None, description="The id of the arithmetic check this finding explains, if any"
    )
    kind: Literal["discrepancy", "low_confidence", "missing_evidence", "fraud_signal"]
    severity: Literal["low", "medium", "high"]
    text: str = Field(description="One or two sentences in English, figures as [[key]]")
    citations: list[CitationOut]
    follow_up_question: str | None = Field(
        default=None, description="A polite question for the owner, in Bahasa Indonesia"
    )
    follow_up_question_en: str | None = Field(default=None, description="The question in English")


class Confirmation(BaseModel):
    text: str = Field(description="Something the sources agree on, figures as [[key]]")
    citations: list[CitationOut]


class Verification(BaseModel):
    findings: list[VerifierFinding]
    confirmations: list[Confirmation]


SYSTEM_PROMPT = f"""\
You are a careful credit analyst at an Indonesian rural bank, reviewing the evidence a loan
officer collected about a micro business. Your job is to cross-check the sources against each
other. You do not decide the loan and you never give a score.

Evidence tiers: QRIS and e-wallet history is hard evidence (a payment provider saw the money).
Supplier receipts are medium. The notebook and the owner's interview are soft: they are what is
being checked. Shop photos are physical: they test plausibility only.

What is normal, and not a finding: most warung sales are cash, so QRIS covering a fifth to a half of
the notebook's sales is expected. Code already checks the share of sales seen in QRIS and the
ratio of sales to purchases against the lender's limits; if those checks did not fire, the
figures are within limits, so do not raise them again. Photos and an interview are optional; their
absence is at most a low-severity point. Raise a finding only when it changes how far the figures
can be relied on: sources that contradict each other, entries that look misread or misfiled,
dates or amounts that don't line up, or documents that look altered.

Return findings, each with:
- kind: discrepancy (sources disagree), low_confidence (a reading is uncertain), missing_evidence
  (something needed is absent) or fraud_signal (signs that evidence was altered or staged).
- severity: high only when sources clearly contradict each other on a material figure or a
  document looks altered; medium when an answer or more evidence is needed before relying on a
  figure; low for minor points.
- citations: the evidence_id and a locator for every source involved. A locator is "line N" or
  "row N" as the reading lists it, "total" or "items" for a receipt, the m:ss time for the
  interview, or "whole item". Never use a field name as a locator.
- follow_up_question: when the owner could explain it, a short, polite question in Bahasa
  Indonesia, using "Bapak/Ibu", that does not accuse; plus its English translation.

The case file lists arithmetic checks that code has already run. Each one is true: include a
finding for every check, with its check_id and its severity unchanged, adding citations, context
and a follow-up question. Then add any other findings the evidence supports. Do not repeat the
same point twice. Most files have between one and six findings.

Also list confirmations: the main points where the sources agree, with citations.

{FIGURE_RULES}
Write plainly, in short sentences. Explain each finding so an officer could act on it.
"""


async def verify(
    gemini: Gemini, case_file: dict[str, Any], facts: FactTable, quoted: set[str]
) -> tuple[Verification, str, list[str]]:
    contents = ["Case file:\n" + json.dumps(case_file, ensure_ascii=False, indent=1)]
    return await generate_checked(
        gemini,
        contents=contents,
        schema=Verification,
        system=SYSTEM_PROMPT,
        facts=facts,
        quoted=quoted,
    )
