# Evaluation

LedgerLens claims to read informal evidence accurately, so we measure it instead of asserting it. This
folder holds the tools that make test data with known true values and score the readers against it.

## Synthetic notebook pages

`synth_notebooks.py` writes pages of a fictional business's notebook in the shorthand Indonesian micro
businesses really use ("610rb", "2,1jt", "kasbon Bu Tini"). Each page is two weeks of daily sales, a
weekly supplier purchase, small customer credit (*kasbon*) and the odd fixed cost. It is rendered in one of
eight handwriting-style fonts on ruled paper, and some lines carry a crossed-out first attempt. The page is
then degraded like a phone photo: tilt, perspective, uneven light, blur and JPEG compression.

Because the generator writes the page, it knows every true amount exactly. It saves them next to the
images as `truth.json` (file name to amounts, the format the handwriting test reads) and
`truth-lines.json` (every line with its text, kind and amount).

```bash
python -m venv .venv && .venv/bin/pip install -r eval/requirements.txt
.venv/bin/python eval/synth_notebooks.py --persona bu-sari --pages 3 --out data/synthetic/bu-sari
```

The fonts are downloaded once from Google Fonts into `eval/.cache/` (ignored by git). All of them are
under the SIL Open Font License.

The three personas in `personas.py` are fictional: a grocery stall whose evidence agrees, a tailor with no
QRIS (Indonesia's national QR payment standard) history, and a food stall whose notebook claims far more
than its purchases could support.

## Complete sample files

`synth_evidence.py` goes further and writes everything an officer would capture for one fictional
business over two months: three notebook pages a month, a handwritten supplier receipt (*nota*) for
every purchase the notebook records, and a screenshot of each month's QRIS history from a fictional
merchant app. `manifest.json` lists the evidence the way the API registers it and holds the true
monthly figures. Where a persona inflates its notebook, its QRIS payments follow true sales, not the
notebook, and its purchases stay true, as they would in real life.

```bash
.venv/bin/python eval/synth_evidence.py --persona pak-hendra --out data/samples/pak-hendra
cd api && .venv/bin/python -m scripts.run_sample --sample ../data/samples/pak-hendra
```

`run_sample` runs the whole analysis and prints each figure it read next to the truth.

### Owner interviews

`synth_interview.py` writes a short conversation in Bahasa Indonesia between the officer and the
owner, reads it aloud with Gemini's text-to-speech (two voices) and adds the recording to the
sample's manifest. Bu Sari's and Pak Joko's answers fit their books; Pak Hendra's own figure for his
daily sales is a third of what his notebook claims, which the verifier reports with the moment he
said it.

```bash
GEMINI_API_KEY=... .venv/bin/python eval/synth_interview.py --sample data/samples/pak-hendra
```

## Running the reader against them

The handwriting test in `api/scripts/` sends every page to the ledger reader twice, once with each prompt
variant, and compares the amounts it reads with the truth:

```bash
cd api
.venv/bin/python -m scripts.handwriting_test --pages ../data/synthetic/bu-sari --out ../eval/out/bu-sari
```

## Results so far

| Data | Amounts | Prompt variant 0 | Prompt variant 1 |
|---|---|---|---|
| Synthetic pages, 3 personas × 3 pages (`gemini-3.8-flash`) | 162 | 99% | 100% |
| The same food-stall pages after the crossed-out fix | 54 | 100% | 100% |

The two misses in variant 0 were both crossed-out corrections, where the reader returned the struck
amount and the final one together. The reader now returns the final amount and keeps any crossed-out one
in a separate field.

### The three sample files

Each sample covers two months: 6 notebook pages, 8 supplier receipts and, for the businesses that
have QRIS, 2 QRIS screenshots. `run_sample` read every monthly notebook, QRIS and receipt total
exactly, and each file got the outcome its evidence supports:

| Sample | Business | Outcome | Why |
|---|---|---|---|
| `bu-sari` | Warung Bu Sari, grocery stall, Bekasi | Verified | Evidence strength 90/100; the requested instalment of Rp 1.290.996 is within the policy maximum of Rp 1.414.800 |
| `pak-joko` | Penjahit Pak Joko, tailor, Yogyakarta | Partially verified | No QRIS history; evidence strength 55/100 |
| `pak-hendra` | Warung Makan Hendra, food stall, Bandung | Inconsistent | The notebook claims 5.6× what supplier purchases support; QRIS shows 13% of claimed sales; no instalment suggested; in the interview the owner himself puts daily sales at Rp 500.000, a third of what the notebook says |

On the Gemini free tier a full analysis of 14 to 16 items took 30 to 220 seconds, depending on load.
`export_samples.py` publishes these analysed files to the web app, where anyone can open them at
`/samples/<slug>` without spending quota.

Two more scripts serve the demo for a visitor trying LedgerLens alone. `bundle_demo_samples.py`
copies each analysed sample into the API (`api/app/demo_samples/`), so the demo story can make a
copy of a finished file without running the analysis. `export_runs.py` reads, never writes, the real
runs on the sample businesses from Firestore and publishes the best one per sample as
`web/public/samples/<slug>/run.json`, which the sample page replays at six to ten times the speed.

```bash
.venv/bin/python eval/bundle_demo_samples.py   # after export_samples.py
source .config/env.sh && api/.venv/bin/python eval/export_runs.py
```

### Real handwriting

These pages are fonts, not real handwriting. They test robustness to layout, shorthand and photo quality.
Only pages written by a real hand test real handwriting, and those results will be added here when the
team's photographed pages are in.
