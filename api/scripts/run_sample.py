"""Run the full analysis on a synthetic sample file and compare it with the true figures.

    python -m scripts.run_sample --sample ../data/samples/bu-sari --out ../eval/out

The folder needs the evidence files and the ``manifest.json`` that ``eval/synth_evidence.py``
writes. Progress is printed as it happens; the full result is saved as JSON, which is also what the
sample files on the landing page are built from. Needs Google Cloud credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from app.analysis.evidence_store import FolderStore
from app.analysis.pipeline import Application, EvidenceItem, run_pipeline
from app.config import get_settings
from app.gemini import Gemini
from app.schemas import EvidenceType


def load(sample: Path) -> tuple[Application, list[EvidenceItem], dict]:
    manifest = json.loads((sample / "manifest.json").read_text())
    app = manifest["application"]
    application = Application(
        alias=app["alias"],
        business_type=app["businessType"],
        city=app["city"],
        years_operating=app["yearsOperating"],
        amount=app["amount"],
        tenor_months=app["tenorMonths"],
    )
    items = [
        EvidenceItem(
            id=Path(e["path"]).stem,
            type=EvidenceType(e["type"]),
            storage_path=e["path"],
            captured_at=datetime.fromisoformat(e["capturedAt"]),
        )
        for e in manifest["evidence"]
    ]
    return application, items, manifest


def compare(result, truth: dict) -> None:
    months = {m.month: m for m in result.cashflow.months}
    print("\nMonth     notebook sales (true / read)   QRIS (true / read)   receipts (true / read)")
    for month, t in truth.items():
        m = months.get(month)
        read = (m.claimed_sales, m.proven_inflows, m.receipt_purchases) if m else (0, 0, 0)
        print(
            f"{month}   {t['claimed_sales']:>12,} / {read[0]:>12,}   "
            f"{t['qris_total'] or 0:>9,} / {read[1]:>9,}   {t['purchases']:>10,} / {read[2]:>10,}"
        )


async def run(sample: Path, out_dir: Path) -> None:
    application, items, manifest = load(sample)
    started = time.monotonic()

    async def progress(agent: str, message: str, state: str) -> None:
        print(f"{time.monotonic() - started:6.1f}s  {agent:<18} {state:<8} {message}")

    settings = get_settings()
    result = await run_pipeline(
        gemini=Gemini(settings),
        store=FolderStore(sample),
        application=application,
        items=items,
        progress=progress,
        max_parallel=settings.max_parallel_calls,
        double_read=settings.ledger_double_read,
    )
    print(f"\nOutcome: {result.assessment.value}   ({time.monotonic() - started:.0f}s)")
    print(f"Policy: {result.policy.model_dump()}")
    compare(result, manifest["truth"])
    print("\nFindings:")
    for f in result.findings:
        print(f"- [{f.severity} {f.kind}, {f.source}] {f.text}")
        if f.follow_up_question:
            print(f"    ask: {f.follow_up_question}")
    print(f"\nHeadline: {result.memo['headline']}")
    print(f"Capacity: {result.memo['capacity']['text']}")
    if result.figure_problems:
        print(f"\nFigure problems: {result.figure_problems}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"sample-{manifest['persona']}.json"
    out_file.write_text(result.model_dump_json(indent=2, by_alias=True))
    print(f"Saved {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("../eval/out"))
    args = parser.parse_args()
    asyncio.run(run(args.sample, args.out))


if __name__ == "__main__":
    main()
