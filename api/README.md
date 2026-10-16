# LedgerLens API

The backend: a FastAPI app on Cloud Run that runs the Gemini agents and writes results to Firestore.

## Run it locally

```bash
cd api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
gcloud auth application-default login   # for Firestore and Cloud Storage
export GEMINI_API_KEY=...                # a Google AI Studio key; never commit it
uvicorn app.main:app --reload --port 8080
```

Gemini is reached in one of two ways. With `GEMINI_API_KEY` set, the API uses the Gemini Developer
API (Google AI Studio), and the prototype runs on its free tier. Without a key it uses Vertex AI
through the service account, which is what a lender deployment would use: paid, and its inputs are
not used to train Google's models.

On the free tier every model has its own small quota, so the work is split by role. The readers,
which make most of the calls and only transcribe, use the Flash-Lite models (15 requests a minute
and 500 a day each). The verifier and memo writer, two calls an analysis that do the reasoning, use
a chain of four Flash models (5 a minute and 20 a day each) with low thinking. The client paces
every model under its per-minute limit and moves down the chain when a model's day is spent.

Configuration comes from environment variables; see [`../.env.example`](../.env.example).
Interactive API docs are served at `http://localhost:8080/api/docs`.

## Test

```bash
ruff check . && ruff format --check .
pytest -q
```

The tests replace Gemini, Firestore and Firebase Auth with fakes, so they run offline.

## Handwriting test

Before building on notebook reading, we check that Gemini reads real handwriting well enough.
Put a few photographed pages and a `truth.json` (file name → list of true amounts in rupiah) in a
folder, then run:

```bash
python -m scripts.handwriting_test --pages ../data/handwriting-test
```

It reads every page with both prompt variants and passes when at least 80% of amounts are correct.

## Layout

| Path | What it holds |
| --- | --- |
| `app/main.py` | App factory and route registration |
| `app/config.py` | Settings from environment variables |
| `app/schemas.py` | The API contract shared with the web app (camelCase JSON) |
| `app/gemini.py` | Gemini client: structured output, retries, per-model pacing and the model chains |
| `app/agents/` | One module per agent: its prompt and output schema |
| `app/agents/writing.py` | The `[[key]]` figure guard for the verifier and memo writer |
| `app/analysis/` | The pipeline (readers, calculator, verifier, policy, memo writer) and where evidence files come from |
| `app/tools/` | Deterministic code: rupiah parsing, cash flow, lender policy, the fact table, scoring. The model never does arithmetic |
| `app/store.py` | Firestore access; only the backend writes |
| `app/auth.py` | Firebase ID-token verification |
| `app/routers/` | HTTP routes under `/api` |
| `scripts/` | Handwriting test, receipt evaluation on CORD, and `run_sample` for a whole sample file |

## Deploy to Cloud Run

```bash
gcloud run deploy ledgerlens-api --source . --region asia-southeast2 \
  --memory 512Mi --max-instances 2 --timeout 900 --cpu-throttling \
  --update-env-vars STORAGE_BUCKET=your-project.firebasestorage.app,GEMINI_API_KEY=your-key
```

The service bills only while it serves a request and scales to zero when idle. An analysis runs
inside its request, so the web app calls this service's URL directly for `/analyze`.
