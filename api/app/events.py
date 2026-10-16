"""Events other parts of LedgerLens can react to (webhooks, notifications), without the decision
code knowing about them. Listeners must never raise into the caller."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger(__name__)

Listener = Callable[[str, dict[str, Any]], Awaitable[None]]
LISTENERS: list[Listener] = []


async def emit(event: str, payload: dict[str, Any]) -> None:
    for listener in LISTENERS:
        try:
            await listener(event, payload)
        except Exception:  # a broken integration must never break the loan flow
            log.exception("listener failed for %s", event)
