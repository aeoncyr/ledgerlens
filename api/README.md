# LedgerLens API

The backend: a FastAPI app on Cloud Run that runs the Gemini agents and writes results to Firestore.

## Run it locally

```bash
cd api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
gcloud auth application-default login   # LedgerLens uses no API keys
uvicorn app.main:app --reload --port 8080
```

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
| `app/gemini.py` | Gemini client: structured output, retries, fallback model |
| `app/agents/` | One module per agent: its prompt and output schema |
| `app/tools/` | Deterministic code: rupiah parsing, scoring. The model never does arithmetic |
| `app/auth.py` | Firebase ID-token verification |
| `app/routers/` | HTTP routes under `/api` |

## Deploy to Cloud Run

```bash
gcloud run deploy ledgerlens-api --source . --region asia-southeast2 \
  --min-instances 1 --no-cpu-throttling --timeout 900 \
  --set-env-vars GOOGLE_GENAI_USE_ENTERPRISE=true,GOOGLE_CLOUD_LOCATION=global
```
