"""Receipt test: how well does the receipt reader read real Indonesian receipts?

Uses CORD, a public dataset of receipts photographed in Indonesian shops and restaurants, labelled
by hand (Park et al., 2019; CC BY 4.0; https://huggingface.co/datasets/naver-clova-ix/cord-v2). The
first ``--count`` receipts of its test split are downloaded once into a local cache and read by the
receipt reader. We score two things against the labels:

- the total: the amount the customer paid, read exactly;
- item amounts: every labelled item price that the reader also found on the receipt.

    python -m scripts.receipt_eval --count 30

Needs Google Cloud credentials, like the handwriting test.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from app.agents.receipt_reader import read_receipt
from app.config import get_settings
from app.gemini import Gemini
from app.tools.rupiah import parse_rupiah
from app.tools.scoring import match_amounts

ROWS_API = "https://datasets-server.huggingface.co/rows"
DATASET = "naver-clova-ix/cord-v2"
CONCURRENCY = 4


def _first(value):
    """CORD stores a field as a string, or as a list when it was split across lines."""
    return value[0] if isinstance(value, list) and value else value


def truth_of(ground_truth: dict) -> dict:
    parse = ground_truth["gt_parse"]
    menu = parse.get("menu", [])
    menu = menu if isinstance(menu, list) else [menu]
    items = [parse_rupiah(_first(item.get("price"))) for item in menu if item.get("price")]
    total = parse_rupiah(_first((parse.get("total") or {}).get("total_price")))
    return {"total": total, "items": [amount for amount in items if amount is not None]}


def download(count: int, cache: Path) -> list[Path]:
    """Fetch the first ``count`` test receipts and their labels, skipping any already cached."""
    cache.mkdir(parents=True, exist_ok=True)
    wanted = [cache / f"{index:03d}.jpg" for index in range(count)]
    missing = [path for path in wanted if not path.exists()]
    if missing:
        offset = int(missing[0].stem)
        for start in range(offset, count, 100):
            url = (
                f"{ROWS_API}?dataset={DATASET}&config=default&split=test"
                f"&offset={start}&length={min(100, count - start)}"
            )
            rows = json.load(urllib.request.urlopen(url, timeout=60))["rows"]
            for row in rows:
                index = row["row_idx"]
                image = urllib.request.urlopen(row["row"]["image"]["src"], timeout=60).read()
                (cache / f"{index:03d}.jpg").write_bytes(image)
                labels = json.loads(row["row"]["ground_truth"])
                (cache / f"{index:03d}.json").write_text(json.dumps(labels, indent=1))
    return wanted


async def score(gemini: Gemini, path: Path, limit: asyncio.Semaphore) -> dict:
    truth = truth_of(json.loads(path.with_suffix(".json").read_text()))
    async with limit:
        receipt, model = await read_receipt(gemini, path.read_bytes(), "image/jpeg")
    read_items = [item.amount_rp for item in receipt.items]
    result = {
        "receipt": path.name,
        "model": model,
        "true_total": truth["total"],
        "read_total": receipt.total_rp,
        "total_correct": truth["total"] is not None and receipt.total_rp == truth["total"],
        "true_items": len(truth["items"]),
        "items_matched": match_amounts(read_items, truth["items"], tolerance=0),
        "read": receipt.model_dump(by_alias=True),
    }
    mark = "ok " if result["total_correct"] else "MISS"
    print(
        f"{path.name}  total {mark} ({receipt.total_rp} vs {truth['total']})  "
        f"items {result['items_matched']}/{result['true_items']}"
    )
    return result


async def run(count: int, cache: Path, out_dir: Path) -> None:
    paths = download(count, cache)
    gemini = Gemini(get_settings())
    limit = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(score(gemini, path, limit) for path in paths))

    with_total = [r for r in results if r["true_total"] is not None]
    totals_right = sum(r["total_correct"] for r in with_total)
    items_true = sum(r["true_items"] for r in results)
    items_right = sum(r["items_matched"] for r in results)
    summary = {
        "dataset": f"{DATASET} (test split, first {count})",
        "receipts": len(results),
        "total_accuracy": totals_right / len(with_total),
        "item_amount_recall": items_right / items_true,
    }
    print(
        f"\nTotals read exactly: {totals_right}/{len(with_total)} ({summary['total_accuracy']:.0%})"
    )
    print(f"Item amounts found:  {items_right}/{items_true} ({summary['item_amount_recall']:.0%})")

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_file = out_dir / f"receipts-{stamp}.json"
    out_file.write_text(json.dumps({"summary": summary, "receipts": results}, indent=2))
    print(f"Full report: {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=30, help="How many test receipts to read")
    parser.add_argument("--cache", type=Path, default=Path("../eval/.cache/cord"))
    parser.add_argument("--out", type=Path, default=Path("../eval/out"))
    args = parser.parse_args()
    asyncio.run(run(args.count, args.cache, args.out))


if __name__ == "__main__":
    main()
