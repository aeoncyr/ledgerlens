"""Publish a real agent trace for each sample file, so the web app can replay how it was checked.

The sample files open finished, so the work behind them is invisible. Each time someone ran the
analysis on a sample business in the live app, its steps were written to Firestore
(``applications/<id>/runs/<id>``). This reads those runs, read-only, picks the best complete one
per sample and writes it to ``web/public/samples/<slug>/run.json`` with each step's time relative
to the start of the run. Who ran it is left out. A sample with no complete run gets no file, and
the replay is hidden. Gemini's readings vary a little between runs, so the run's own outcome is
kept too: the web app says so when it differs from the published file.

Needs read access to Firestore (``GOOGLE_APPLICATION_CREDENTIALS`` and ``GOOGLE_CLOUD_PROJECT``,
as set by ``.config/env.sh``). It never writes to Firestore.

    python eval/export_runs.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from google.cloud import firestore

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "web/public/samples"


def _seconds(at: datetime, start: datetime) -> float:
    return round(max(0.0, (at - start).total_seconds()), 1)


def _plain(value: Any) -> Any:
    """Timestamps inside a step's detail become ISO strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def outcome(run: dict[str, Any]) -> str | None:
    """The run's outcome as its policy step reported it, e.g. "partially_verified"."""
    for step in run.get("steps") or []:
        if step["agent"] == "policy" and step["message"].startswith("Outcome: "):
            return step["message"].removeprefix("Outcome: ").strip().replace(" ", "_")
    return None


def _rank(run: dict[str, Any], assessment: str) -> tuple:
    """A full analysis beats a re-check, one with the published file's outcome beats one without,
    one with Gemini's output excerpts beats one without, and among equals the most recent wins."""
    steps = run.get("steps") or []
    full = any(step["agent"] == "intake" for step in steps)
    detailed = any(step.get("detail") for step in steps)
    return (full, outcome(run) == assessment, detailed, run["startedAt"])


def best_runs(
    db: firestore.Client, samples: dict[str, tuple[str, str]]
) -> dict[str, tuple[str, dict]]:
    """For each sample slug, the id and document of its best complete run. ``samples`` maps each
    business alias to its slug and the published file's outcome."""
    best: dict[str, tuple[str, dict]] = {}
    query = db.collection("applications").where(
        filter=firestore.FieldFilter("business.alias", "in", list(samples))
    )
    for application in query.stream():
        data = application.to_dict()
        slug, assessment = samples[data["business"]["alias"]]
        for snapshot in application.reference.collection("runs").stream():
            run = snapshot.to_dict()
            # A file the owner started counts the QRIS screenshots they send as weaker evidence.
            run["ownerLed"] = bool(data.get("ownerUid"))
            if run.get("state") != "done" or not run.get("steps") or not run.get("startedAt"):
                continue
            if slug not in best or _rank(run, assessment) > _rank(best[slug][1], assessment):
                best[slug] = (snapshot.id, run)
    return best


def export(run_id: str, run: dict[str, Any]) -> dict[str, Any]:
    start = run["startedAt"]
    steps = []
    for step in run["steps"]:
        out = {
            "agent": step["agent"],
            "message": step["message"],
            "state": step["state"],
            "t": _seconds(step["at"], start),
        }
        if step.get("detail"):
            out["detail"] = _plain(step["detail"])
        steps.append(out)
    return {
        "id": run_id,
        "recordedAt": start.date().isoformat(),
        "latencyMs": run.get("latencyMs"),
        "models": run.get("models") or [],
        "outcome": outcome(run),
        "ownerLed": run.get("ownerLed", False),
        "steps": steps,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a real agent trace for each sample")
    parser.add_argument("--project", default=None, help="Defaults to GOOGLE_CLOUD_PROJECT")
    args = parser.parse_args()
    samples = {}
    for file in sorted(SAMPLES.glob("*/file.json")):
        published = json.loads(file.read_text())
        samples[published["application"]["alias"]] = (file.parent.name, published["assessment"])
    best = best_runs(firestore.Client(project=args.project), samples)
    for slug, _ in samples.values():
        if slug not in best:
            print(f"{slug}: no complete run found; the replay stays hidden")
            continue
        run_id, run = best[slug]
        trace = export(run_id, run)
        (SAMPLES / slug / "run.json").write_text(json.dumps(trace, ensure_ascii=False, indent=1))
        print(
            f"{slug}: run {run_id[:8]} of {trace['recordedAt']}, {len(trace['steps'])} steps, "
            f"{(trace['latencyMs'] or 0) / 1000:.0f}s, outcome {trace['outcome']}"
        )


if __name__ == "__main__":
    main()
