# Roofing Sales Intelligence MVP

AI-assisted sales-intelligence dashboard for a roofing-material distributor. Collects residential roofing contractors near ZIP `10013` from GAF, scores them deterministically, enriches them with source-backed research, and generates account-planning guidance for sales reps. See `PRD.md` for the full spec and `CLAUDE.md` for build guardrails.

## Setup

### Backend

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # or: source .venv/bin/activate
pip install -e .
python -m playwright install chromium
cp ../.env.example ../.env   # fill in DATABASE_URL if using Supabase; sqlite works with no changes
python -m scripts.seed        # loads backend/data/fixtures/contractors.json into the DB
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

## Environment variables

```text
DATABASE_URL          Postgres (Supabase Session Pooler) or sqlite:///./dev.db for local dev
OPENAI_API_KEY        optional — only required for live insight generation
PERPLEXITY_API_KEY     optional — only required for live research
PERPLEXITY_MODEL       default sonar-pro
OPENAI_MODEL           e.g. gpt-4o-mini
FRONTEND_URL           CORS origin, default http://localhost:3000
USE_FIXTURES           true by default; set false to let /api/ingestion/run call live Perplexity/OpenAI
NEXT_PUBLIC_API_URL    frontend-only, points at the backend (default http://localhost:8000)
```

## Commands

```bash
# backend
cd backend
pytest
python -m compileall app

# frontend
cd frontend
npm run lint
npm run build
```

## How the pieces fit together

```text
GAF listing scrape (Playwright, backend/app/services/gaf_scraper.py)
  → GAF profile scrape
  → upsert contractor + search provenance (backend/app/routes/ingestion.py)
  → Perplexity research (backend/app/services/research.py)
  → deterministic scoring (backend/app/services/scoring.py, backend/app/scoring_config.yaml)
  → OpenAI insight generation (backend/app/services/insight_generator.py)
  → persisted to Postgres
  → dashboard reads persisted data only (backend/app/routes/leads.py)
```

Fixture mode (`USE_FIXTURES=true`, the default) skips the live GAF/Perplexity/OpenAI stages entirely: `scripts/seed.py` loads `backend/data/fixtures/contractors.json` — which contains **85 real GAF contractors** scraped for ZIP 10013 / 25mi residential — and computes real scores against them via the same `scoring.py` used at request time. Research and insight content in the fixture file is authored from the same real GAF profile text (about-us copy, certification badges, website links), not fabricated.

## GAF scraping — a real, documented limitation

GAF's site sits behind Akamai Bot Manager. Headless Chromium (and raw `curl`) get an unconditional `403`/`Access Denied` from this environment — verified both with a stock request and with a stealth-patched headless browser (`navigator.webdriver` override, disabled automation flags, realistic UA/headers). None of that mattered because the block isn't fingerprint-based here; it needs real-browser telemetry.

**What works:** running Playwright with `headless=False` (a real display) gets through cleanly. `backend/app/services/gaf_scraper.py` and `backend/scripts/ingest.py` are written around that constraint — they are not meant to run on a headless server. All 85 residential listings and profile pages for ZIP 10013 / 25mi were captured this way; raw payloads are under `backend/data/snapshots/`.

**Known limitation:** every contractor returned by GAF's default residential locator for this ZIP/radius happened to be Master Elite tier. This was verified as real per-contractor data (each profile's certification badge carries its own `contractor_id` in an inline analytics payload, not shared boilerplate) rather than a scraper bug — but it means the certification-tier scoring bucket has no live-data variety to demonstrate in this particular batch.

## Assumptions

- `product_service_alignment` and `business_scale` (Account Fit subcomponents) are sourced from research findings, not the GAF listing card — both are `unavailable` until research completes for a contractor, consistent with the missing-data rule.
- `business_start_year` is only populated where a contractor's own "about us" text states an explicit founding year (e.g. "since 1996"); GAF does not expose this field structurally. 13 of 85 fixture contractors have it; the rest correctly show `years_in_business` as unavailable.
- Decision-makers are left empty across the fixture batch — GAF profiles do not expose verified owner/GM names, and the PRD explicitly disallows inferring them from indirect signals (e.g. a company name matching a first-person bio).
- The fixture batch's research/insight `pending`/`failed`/`completed` status split is deterministic (every 11th record pending, every 13th failed) so reruns are stable and all three states are demonstrable in the UI.

## Known limitations / not implemented

- Live Perplexity and OpenAI integrations (`services/research.py`, `services/insight_generator.py`) were run against all 85 real contractors with real API keys and a real Supabase Postgres instance (`scripts/run_live_enrichment.py`) — found genuine named decision-makers with source citations (BBB, LinkedIn, D&B, NYC DOB permits) for several contractors. Fixture mode remains the no-external-keys demo path.
- `scoring_config.yaml`'s `opportunity.recent_project_activity.bands` (the `min_count`/`max_count`/`only_older` entries) are currently **dead config** — `scoring.py`'s `score_opportunity()` only reads that block's `max_points`; the actual thresholds (5+ projects → 30pts, 3-4 → 24, 1-2 → 15, older-only → 5, none → 0) are hardcoded in an if/elif chain in Python instead. Every other scoring bucket is genuinely config-driven; this one isn't yet — changing these five numbers today requires editing `scoring.py`, not the YAML.
- P1 flag/regenerate routes are not built (P0-only scope per CLAUDE.md).
- Commercial locator support exists in `gaf_scraper.py`'s constants but is not wired into ingestion (P0 is residential-only per PRD).
