"""Named figures, so the writing agents can talk about numbers without ever producing one.

Code computes every figure and gives it a key ("revenue_low", "receipt_2_total"). The verifier and
the memo writer refer to figures only as ``[[key]]``; code then fills in the value. Text that still
contains a number the model wrote itself is caught by ``stray_numbers`` before it reaches a lender.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

FactKind = Literal["rupiah", "percent", "ratio", "count"]

_PLACEHOLDER = re.compile(r"\[\[([a-z0-9_]+)\]\]")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_UNIT_AFTER = re.compile(r"^\s*(?:%|rb\b|ribu\b|jt\b|juta\b|k\b|x\b|×|million|thousand|billion)")


class Fact(BaseModel):
    key: str
    label: str = Field(description="What the figure is, in plain English")
    kind: FactKind
    value: float
    sources: list[str] = Field(default_factory=list, description="Evidence ids it comes from")

    @property
    def display(self) -> str:
        if self.kind == "rupiah":
            return "Rp " + f"{round(self.value):,}".replace(",", ".")
        if self.kind == "percent":
            return f"{self.value:.0%}"
        if self.kind == "ratio":
            return f"{self.value:.1f}×"
        return f"{round(self.value):,}"


class FactTable:
    def __init__(self) -> None:
        self._facts: dict[str, Fact] = {}

    @classmethod
    def from_facts(cls, facts: list[Fact]) -> FactTable:
        table = cls()
        table._facts = {fact.key: fact for fact in facts}
        return table

    def add(
        self,
        key: str,
        label: str,
        kind: FactKind,
        value: float | None,
        sources: list[str] | None = None,
    ) -> None:
        if value is not None:
            self._facts[key] = Fact(
                key=key, label=label, kind=kind, value=value, sources=sources or []
            )

    def __contains__(self, key: str) -> bool:
        return key in self._facts

    def all(self) -> list[Fact]:
        return list(self._facts.values())

    def for_prompt(self) -> list[dict]:
        """What the writing agents see: the key, what it means and its value, to reason with."""
        return [{"key": f.key, "label": f.label, "value": f.display} for f in self._facts.values()]

    def unknown_keys(self, template: str) -> list[str]:
        return [key for key in _PLACEHOLDER.findall(template) if key not in self._facts]

    def render(self, template: str) -> str:
        def fill(match: re.Match[str]) -> str:
            fact = self._facts.get(match.group(1))
            return fact.display if fact else "[unknown figure]"

        return _PLACEHOLDER.sub(fill, template)


def stray_numbers(template: str) -> list[str]:
    """Numbers the model wrote itself instead of naming a figure.

    Small counts and dates are fine ("two receipts", "line 4", "12/9"), and so is a year. Anything
    that reads as an amount, a percentage or a multiple is not.
    """
    text = _PLACEHOLDER.sub(" ", template)
    stray = []
    for match in _NUMBER.finditer(text):
        token = match.group()
        has_unit = bool(_UNIT_AFTER.match(text[match.end() :]))
        has_separator = bool(re.search(r"[.,]", token))
        digits = int(re.sub(r"[.,]", "", token))
        is_year = not has_separator and 2000 <= digits <= 2099
        if has_unit or (has_separator and digits >= 1000) or (digits >= 100 and not is_year):
            stray.append(token)
    return stray
