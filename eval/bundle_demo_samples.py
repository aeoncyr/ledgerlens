"""Bundle the finished sample files into the API, for the demo story (``api/app/routers/demo.py``).

The demo story copies a finished sample into a new file that one browser plays from end to end, so
no analysis runs. The API's container holds only ``api/``, so it needs its own copy of each sample:
the evidence list the web app publishes (``web/public/samples/<slug>/file.json``, whose photos the
demo file points at) and the analysis exactly as ``run_sample`` saved it
(``eval/out/samples/sample-<slug>.json``), which the API stores the way a real run does.

Writes ``api/app/demo_samples/<slug>.json`` for every sample that has both. Run it after
``export_samples.py``:

    python eval/bundle_demo_samples.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def bundle(slug: str, file: Path, saved: Path, out: Path) -> None:
    published = json.loads(file.read_text())
    result = json.loads(saved.read_text())
    evidence = [
        {k: item[k] for k in ("id", "type", "image", "capturedAt")}
        for item in published["evidence"]
    ]
    missing = [item["id"] for item in evidence if item["id"] not in result["extractions"]]
    if missing:
        raise SystemExit(f"{slug}: the saved analysis has no reading for {', '.join(missing)}")
    sample = {
        "slug": slug,
        "fileNumber": published["fileNumber"],
        "application": published["application"],
        "evidence": evidence,
        "result": result,
    }
    out.write_text(json.dumps(sample, ensure_ascii=False, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Bundle the sample files into the API")
    parser.add_argument("--results", type=Path, default=ROOT / "eval/out/samples")
    args = parser.parse_args()
    out = ROOT / "api/app/demo_samples"
    out.mkdir(exist_ok=True)
    for file in sorted((ROOT / "web/public/samples").glob("*/file.json")):
        slug = file.parent.name
        saved = args.results / f"sample-{slug}.json"
        if not saved.exists():
            print(f"{slug}: skipped, no saved analysis at {saved}")
            continue
        bundle(slug, file, saved, out / f"{slug}.json")
        print(f"{slug}: bundled ({(out / f'{slug}.json').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
