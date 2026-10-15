"""Compare amounts read from a page with the true amounts, for evaluation."""

from __future__ import annotations

from collections.abc import Iterable


def match_amounts(read: Iterable[int | None], truth: Iterable[int], tolerance: float = 0.01) -> int:
    """Count true amounts that were read correctly (within ``tolerance``), each used at most once.

    Order on the page doesn't matter: a correct amount read on the wrong line still counts, because
    this score is about reading the handwriting, not about line segmentation.
    """
    remaining = [amount for amount in read if amount is not None]
    matched = 0
    for expected in truth:
        for index, got in enumerate(remaining):
            if abs(got - expected) <= tolerance * expected:
                matched += 1
                del remaining[index]
                break
    return matched
