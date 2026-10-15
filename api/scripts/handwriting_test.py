"""Handwriting test: can Gemini read our real notebook pages well enough to build the demo on?

Photograph a few handwritten pages, list their true amounts in a truth file, and run:

    python -m scripts.handwriting_test --pages ../data/handwriting-test

The folder needs the photos plus ``truth.json``, mapping each file name to its amounts in rupiah:

    {"page-1.jpg": [610000, 655000, 2100000, 20000], "page-2.jpg": [75000, 1200000]}

Each page is read with both prompt variants. The test passes when at least 80% of the true amounts
are read correctly. Needs Google Cloud credentials (gcloud auth application-default login).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.agents.ledger_reader import VARIANT_HINTS, read_ledger_page
from app.config import get_settings
from app.gemini import Gemini
from app.tools.scoring import match_amounts

PASS_THRESHOLD = 0.8


async def run(pages_dir: Path, out_dir: Path) -> bool:
    truth: dict[str, list[int]] = json.loads((pages_dir / "truth.json").read_text())
    gemini = Gemini(get_settings())
    report: list[dict] = []
    totals = [0] * len(VARIANT_HINTS)
    expected_total = 0

    for name, amounts in truth.items():
        path = pages_dir / name
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        expected_total += len(amounts)
        page = {"page": name, "expected": len(amounts), "variants": []}
        for variant in range(len(VARIANT_HINTS)):
            lines, model = await read_ledger_page(
                gemini, path.read_bytes(), mime_type, variant=variant
            )
            matched = match_amounts([line.amount_rp for line in lines], amounts)
            totals[variant] += matched
            page["variants"].append(
                {
                    "variant": variant,
                    "model": model,
                    "matched": matched,
                    "read": [line.model_dump(by_alias=True) for line in lines],
                }
            )
            print(f"{name:<24} variant {variant}: {matched}/{len(amounts)} amounts correct")
        report.append(page)

    accuracies = [total / expected_total for total in totals]
    best = max(accuracies)
    print()
    for variant, accuracy in enumerate(accuracies):
        print(f"Variant {variant}: {accuracy:.0%} of {expected_total} amounts read correctly")
    passed = best >= PASS_THRESHOLD
    verdict = "PASS" if passed else "FAIL"
    print(f"\n{verdict}: best accuracy {best:.0%} (threshold {PASS_THRESHOLD:.0%})")

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_file = out_dir / f"handwriting-{stamp}.json"
    out_file.write_text(json.dumps({"accuracies": accuracies, "pages": report}, indent=2))
    print(f"Full report: {out_file}")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--pages", type=Path, required=True, help="Folder with photos and truth.json"
    )
    parser.add_argument(
        "--out", type=Path, default=Path("../eval/out"), help="Where to write the report"
    )
    args = parser.parse_args()
    sys.exit(0 if asyncio.run(run(args.pages, args.out)) else 1)


if __name__ == "__main__":
    main()
