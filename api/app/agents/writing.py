"""Shared plumbing for the agents that write prose: the verifier and the memo writer.

They may only mention a figure as a ``[[key]]`` from the fact table, or quote an amount exactly as
it is written in the evidence. ``generate_checked`` enforces that: it finds numbers the model made
up and unknown keys, asks once more with the problems spelled out, and if they persist replaces the
offending numbers so they never reach a lender.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel

from app.gemini import Gemini
from app.tools.facts import FactTable, stray_numbers

log = logging.getLogger(__name__)

# Fields that hold identifiers or locators rather than prose; they are never checked or rendered.
NOT_PROSE = {"evidence_id", "locator", "check_id", "time_text"}

FIGURE_RULES = """\
Figures: you never write a number for an amount of money, a percentage, a ratio or a total. To
mention a figure, write its key in double square brackets exactly as listed under "facts", for
example [[revenue_low]]; code fills in the value. You may also quote an amount exactly as it is
written in the evidence (for example "2,1jt") when you cite where it is written. Small counts,
dates and line numbers are fine.
"""


def _strings(value: Any, path: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, BaseModel):
        value = {name: getattr(value, name) for name in type(value).model_fields}
    if isinstance(value, dict):
        return [
            item
            for key, inner in value.items()
            if key not in NOT_PROSE
            for item in _strings(inner, f"{path}.{key}")
        ]
    if isinstance(value, list):
        return [item for i, inner in enumerate(value) for item in _strings(inner, f"{path}[{i}]")]
    return []


def problems(output: BaseModel, facts: FactTable, quoted: set[str]) -> list[str]:
    found = []
    for path, text in _strings(output):
        stray = [n for n in stray_numbers(text) if n not in quoted]
        if stray:
            found.append(f"{path}: wrote {', '.join(stray)} instead of a [[key]]")
        unknown = facts.unknown_keys(text)
        if unknown:
            found.append(f"{path}: unknown keys {', '.join(unknown)}")
    return found


def _scrub(text: str, quoted: set[str]) -> str:
    for number in stray_numbers(text):
        if number not in quoted:
            text = re.sub(rf"(?<![\d.,]){re.escape(number)}(?![\d.,])", "[figure removed]", text)
    return text


def scrub[T: BaseModel](output: T, quoted: set[str]) -> T:
    """Last resort: remove numbers the model wrote itself, leaving everything else intact."""

    def walk(value: Any, key: str = "") -> Any:
        if isinstance(value, str):
            return value if key in NOT_PROSE else _scrub(value, quoted)
        if isinstance(value, dict):
            return {k: walk(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, key) for v in value]
        return value

    return type(output).model_validate(walk(output.model_dump()))


async def generate_checked[T: BaseModel](
    gemini: Gemini,
    *,
    contents: list[Any],
    schema: type[T],
    system: str,
    facts: FactTable,
    quoted: set[str],
) -> tuple[T, str, list[str]]:
    """Generate, check the figures, retry once with feedback. Returns output, model, problems."""
    output, model = await gemini.generate(
        contents=contents, schema=schema, system=system, role="write"
    )
    issues = problems(output, facts, quoted)
    if not issues:
        return output, model, []
    log.warning("%s broke the figure rules: %s", schema.__name__, issues)
    retry = [
        *contents,
        "Your previous answer broke the figure rules:\n- "
        + "\n- ".join(issues)
        + "\nAnswer again, using [[key]] for every figure.",
    ]
    output, model = await gemini.generate(
        contents=retry, schema=schema, system=system, role="write"
    )
    issues = problems(output, facts, quoted)
    if issues:
        log.warning("%s still broke the figure rules; scrubbing: %s", schema.__name__, issues)
        output = scrub(output, quoted)
    return output, model, issues


def number_tokens(texts: list[str]) -> set[str]:
    """Every number as written in the evidence, which the writers may quote with a citation."""
    return {token for text in texts for token in re.findall(r"\d+(?:[.,]\d+)*", text)}


def render(value: Any, facts: FactTable) -> Any:
    """Fill every [[key]] in a dumped model with its value, leaving identifiers alone."""
    if isinstance(value, str):
        return facts.render(value)
    if isinstance(value, dict):
        return {k: v if k in NOT_PROSE else render(v, facts) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, facts) for v in value]
    return value
