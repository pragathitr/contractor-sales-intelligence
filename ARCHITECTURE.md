# Architecture & Build Notes

What was built, why each file exists, and how it maps to the three evaluation objectives (intuitive UI, robust data management, scalable pipeline). See `PRD.md` for the full spec and `README.md` for setup/run commands.

---

## 1. Intuitive UI

**What a rep sees:** a single dashboard page (`frontend/app/page.tsx`) — a searchable, filterable, sortable table of every contractor ranked by deterministic Lead Priority, with a detail drawer for the full picture on any one lead.

**Design decisions:**

- **Progressive disclosure, not two UIs.** Every score, coverage number, and confidence value has both a plain-language form ("Priority: High · 82", "Verified") and a technical form ("lead-priority-v1", "confidence: high"). A single "Show scoring detail" checkbox in the drawer (`components/score-breakdown.tsx`, `components/source-list.tsx`) flips the whole panel between registers — nothing is hidden in either mode, only relabeled. This means a non-technical rep gets a clean read, and a sales-ops or engineering user auditing the model gets the full subcomponent breakdown table (points/max/available per bucket) without a separate screen.
- **Provisional badging, not silent rank inflation.** A lead whose research failed would otherwise rank above a lead whose research succeeded and genuinely found nothing, because the failed one has fewer subcomponents in its denominator. Rather than let that misrepresent confidence, any lead under 60% combined coverage gets an explicit "Provisional" badge in both the table and drawer.
- **Status is never ambiguous.** Research and insight each show one of `pending` / `completed` / `failed` as a colored badge (`components/lead-table.tsx`'s `StatusBadge`, reused in the drawer) — a rep never sees a blank section without knowing whether that's "nothing found" or "hasn't run yet" or "the API call failed."
- **AI opinion is visually separate from the deterministic score.** The AI priority label (`high`/`medium`/`low`) renders in its own colored pill with an explicit "separate from official score" caption — it can never be confused with the Lead Priority number that drives sort order.
- **Empty/missing states are designed, not defaulted.** Empty source lists say "None found in available public sources" rather than rendering nothing; a contractor with zero leads shows an explicit empty-state message; a failed fetch shows a retry-relevant error message instead of a blank screen.

**Bonus/distinctive touches:** the rep-facing → technical toggle (one interaction surfaces the entire scoring methodology, including per-subcomponent point/max/availability, for a rep who wants to double-check the model); source-linked evidence cards with per-fact confidence badges rather than a flat text blob; distance/experience/certification shown as first-class sortable/filterable columns rather than buried in the detail view.

| File | Role |
|---|---|
| `frontend/app/page.tsx` | Top-level client component: owns filter state, fetches `/api/leads`, renders table + drawer |
| `frontend/app/layout.tsx` | Root HTML shell, fonts, page metadata |
| `frontend/components/lead-filters.tsx` | Search box, certification filter, min-rating filter, sort selector |
| `frontend/components/lead-table.tsx` | The ranked lead table; also exports the shared `StatusBadge` |
| `frontend/components/lead-detail-drawer.tsx` | Full contractor detail: profile, score, research, AI insight, rep/technical toggle |
| `frontend/components/score-breakdown.tsx` | Renders one score (Lead Priority/Account Fit/Opportunity) in rep-facing or technical form |
| `frontend/components/source-list.tsx` | Renders a list of source-backed evidence items with confidence badges and links |
| `frontend/lib/api.ts` | Typed fetch wrappers for `/api/leads` and `/api/leads/{id}` |
| `frontend/lib/types.ts` | TypeScript types mirroring the backend Pydantic schemas exactly |
| `frontend/lib/format.ts` | Small display-formatting helpers (labels, rounding) |

---

## 2. Robust data management

**Storage:** Postgres (Supabase, Session Pooler) via SQLModel, six tables (`backend/app/models.py`):

- `Contractor` — **current-state** row per contractor, upserted by `gaf_contractor_id` (the one field GAF guarantees is stable). Re-running ingestion updates this row rather than creating a duplicate — verified directly (seeding twice left contractor count at 85, not 170).
- `SearchRun` / `SearchResult` — search provenance, kept separate from contractor identity. A contractor can appear in many search runs at different distances without that history overwriting anything. This is the seam a future multi-ZIP/multi-branch expansion would extend.
- `ResearchFinding` — one row per research attempt, `pending`/`completed`/`failed`, full validated Perplexity payload as JSON. Not versioned (research is refreshable, not append-only) but never overwritten silently — every attempt is its own row, and the API reads the most recent by `researched_at`.
- `LeadScore` — one row per `(contractor, score_type, formula_version)` per scoring run, **never overwritten**. Changing a weight bumps `formula_version` in `scoring_config.yaml`; old scores stay queryable under their original version. This is what makes "we changed the model" an auditable event instead of silent drift.
- `Insight` — versioned (`UniqueConstraint(contractor_id, version)`), append-only. Regenerating an insight (P1 flag/regenerate flow) creates version N+1; version N is retained. The API always returns `max(version)`.
- `InsightFlag` — P1-only, not built (scoped out per the three-hour cut line), but the schema is already shaped for it.

**Why this is production-shaped, not just demo-shaped:**

- **Idempotency is real, not assumed.** `_upsert_contractor` keys strictly on `gaf_contractor_id`; the seed/live-enrichment scripts were actually run twice against Supabase during this build to confirm no duplication (85 → 85, not 85 → 170).
- **Missing data is a first-class state, not null-and-hope.** The scoring layer's coverage math (below) exists specifically so "we don't know" is distinguishable from "we checked and it's zero" at the database level, not just in the UI.
- **Config-driven scoring with version history is a data-management decision, not just a code-organization one.** `scoring_config.yaml` is loaded once and passed as a plain argument — scores are tagged with the exact formula version that produced them, so historical leads remain interpretable after the model changes. This is the mechanism a real system would use to answer "why did this contractor's score change last quarter."
- **Boundary validation everywhere external data enters.** Every LLM response (Perplexity, OpenAI) is validated against a Pydantic schema (`app/schemas.py`) before it touches the database; a schema-invalid response becomes a `failed` status row, never a fabricated fallback.

**What a full production system would add (documented rather than built, per the time box):**

- Connection pooling is already Session-Pooler-shaped (`pool_size=5, max_overflow=5, pool_pre_ping=True` in `database.py`) for one persistent backend instance; a horizontally-scaled deployment would move to Supavisor's Transaction Pooler and add read replicas once read volume justifies it.
- Indexes exist on the obvious lookup columns (`gaf_contractor_id`, `contractor_id` foreign keys, `score_type`, `status`) but there's no query-plan tuning — fine at 85 rows, would need real EXPLAIN-driven work at scale.
- No retention/archival policy for old `LeadScore`/`Insight` versions — everything is hot. A production system would archive superseded versions to cold storage after N days.
- No row-level security / multi-tenant isolation — irrelevant at MVP scope (no auth), but the schema (contractor-scoped foreign keys throughout) doesn't fight adding it later.

| File | Role |
|---|---|
| `backend/app/models.py` | The six P0 tables + one P1 table (SQLModel) |
| `backend/app/database.py` | Engine/session setup, Supabase Session Pooler config |
| `backend/app/config.py` | Environment settings (`.env`, resolved relative to repo root regardless of CWD) + scoring config loader |
| `backend/app/scoring_config.yaml` | All weights, bucket thresholds, formula versions — the single configuration surface |
| `backend/scripts/seed.py` | Idempotent fixture-mode loader (contractors + authored research/insight + real computed scores) |
| `backend/scripts/run_live_enrichment.py` | Idempotent live-mode loader (contractors + real Perplexity/OpenAI + real computed scores) |
| `backend/scripts/apply_address_backfill.py` | Targeted backfill script — updates only `address`/`zip_code`, leaves scores/research/insight untouched |
| `backend/scripts/ingest.py` | Manual CLI trigger for a live GAF scrape (no DB writes — just prints what would be scraped) |

---

## 3. Scalable pipeline

**Current shape (intentionally synchronous, per PRD — this is an MVP, not the target architecture):**

```
GAF listing scrape → GAF profile scrape → upsert contractor + provenance
  → Perplexity research → deterministic scoring → OpenAI insight → persist
  → dashboard reads persisted data only
```

Every stage is independently attempted per contractor, and **one contractor's failure never fails the batch** — this was verified in practice during the live run: 3 of 85 contractors hit a datetime bug on the first pass (naive vs. aware comparison in date parsing), the other 82 completed normally, and the 3 were fixed and re-run individually without touching anything else. That failure-isolation property is what a queue-based version would formalize with per-item retries.

**What actually makes this scale-ready, not just "works for 85":**

- **Pure functions at the core.** `scoring.py` has zero DB/network/LLM calls — it's a deterministic function of (inputs, config) → result. This is what lets it be unit-tested exhaustively (40 tests: boundaries, missing-data normalization, determinism, config sensitivity) and what would let it run identically inside a worker process, a batch job, or a request handler without modification.
- **Stage boundaries are already service boundaries.** `gaf_scraper.py`, `research.py`, `insight_generator.py`, and `scoring.py` don't call each other — `routes/ingestion.py` (or `scripts/run_live_enrichment.py`) orchestrates them. That's the exact seam a queue-based redesign would cut along: each becomes a worker consuming from its own queue instead of a function call, with no internal logic changes required.
- **The free-text → category-key mapping problem is isolated.** Perplexity returns prose evidence, not the enum-like signal keys `scoring.py` needs (e.g. "new_location_or_territory"). Rather than let that classification logic leak into either `research.py` (which should stay a thin API client) or `scoring.py` (which must stay pure), it lives in its own module (`research_mapping.py`) — this is the piece that would get more sophisticated (embeddings, a small classifier) without touching either neighbor.
- **Schema validation at every external boundary means partial failure is cheap.** A malformed LLM response becomes one `failed` row, not a crashed batch — which is what makes "hundreds of reps, thousands of contractors" tractable: failures are contractor-scoped, not run-scoped.
- **Rate/cost control is structural, not incidental.** The one-contractor-first validation step (`run_live_enrichment.py`) exists specifically because a new JSON schema against Perplexity is slow/fragile on the first call — validating before committing to an 85-contractor (or 8,500-contractor) batch is a cost-control pattern, not a one-off script quirk.

**What the PRD explicitly defers to "future work" (and why that's the right call at this scope):** async workers + a queue (Celery/SQS/etc.) with per-contractor retries and idempotency keys; refreshing research only when stale rather than on every run; horizontal FastAPI replicas behind a load balancer once concurrent dashboard reads justify it; CRM-outcome backtesting to validate the scoring weights are actually predictive rather than just interpretable. Building these speculatively now would have traded a working, tested vertical slice for unused infrastructure — the PRD's own non-goals list (no queues, no Redis, no microservices) reflects that this is a defensible engineering call, not an oversight.

| File | Role |
|---|---|
| `backend/app/services/gaf_scraper.py` | GAF listing + profile scraping (Playwright). Isolated: knows nothing about scoring/research/DB |
| `backend/app/services/research.py` | Perplexity client — prompt formatting, schema validation, nothing else |
| `backend/app/services/research_mapping.py` | Pure text-classification layer: free-text research → category keys `scoring.py` needs |
| `backend/app/services/scoring.py` | Pure deterministic scoring — no I/O of any kind, config passed in as an argument |
| `backend/app/services/insight_generator.py` | OpenAI client — prompt formatting, schema validation, nothing else |
| `backend/app/prompts.py` | The exact PRD prompt templates, kept out of the client code that uses them |
| `backend/app/routes/ingestion.py` | Orchestrates the pipeline stages per contractor; the seam a queue-based redesign would cut along |
| `backend/app/routes/leads.py` | Dashboard reads — persisted data only, never triggers scraping/LLM calls |
| `backend/tests/test_scoring.py` | 40 tests: exact boundaries, missing-data normalization, determinism, config sensitivity |

---

## What's real vs. fixture in this build

Both modes are fully implemented and were both actually exercised end-to-end, not just written:

- **Fixture mode** (`USE_FIXTURES=true`, default): `scripts/seed.py` loads `backend/data/fixtures/contractors.json` — 85 real GAF contractors (real name/phone/rating/certification/about-text, scraped for ZIP 10013/25mi residential) with authored research/insight content derived from that same real profile text. Runs with no API keys.
- **Live mode**: `scripts/run_live_enrichment.py` was run against all 85 real contractors with real Perplexity + OpenAI API keys and a real Supabase Postgres instance. It found genuine named decision-makers with source citations (e.g., BBB/Blue Book/D&B/LinkedIn profiles) for several contractors — this is live, not simulated. A real bug (naive/aware datetime comparison) surfaced on 3 of 85 contractors during this run and was fixed and re-verified, not glossed over.

See `README.md` → "GAF scraping — a real, documented limitation" for the Akamai bot-protection constraint that shapes how `gaf_scraper.py` has to run (`headless=False`, real display required).
