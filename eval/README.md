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

These pages are fonts, not real handwriting. They test robustness to layout, shorthand and photo quality.
Only pages written by a real hand test real handwriting, and those results will be added here when the
team's photographed pages are in.
