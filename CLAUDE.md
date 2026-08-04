# CLAUDE.md

## Objective

Implement the P0 roofing sales-intelligence MVP in `PRD.md`.

Read the complete PRD before writing code. Follow its exact prompts, schemas, scoring buckets, missing-data rules, API boundaries, and acceptance criteria. Optimize for a polished and dependable three-hour demo with minimal code.

A complete, fixture-backed demo that runs without external keys is the primary deliverable. Live AI integrations are secondary and are attempted only once that demo is working end to end.

## Workflow

1. Inspect the repository.
2. Make a short task list from the PRD.
3. Implement the smallest complete vertical slice.
4. Run checks after each meaningful milestone.
5. Commit whenever the checks pass and the working tree is coherent. Do not commit broken code to match a step boundary, and do not skip a commit because the step is not finished. Never amend, rebase, or force-push.
6. Keep `README.md` current.
7. Stop once P0 acceptance criteria are met.

Resolve minor unspecified choices with the smallest conventional option. Do not ask questions that the PRD or repository already answers. Ask only for missing credentials or truly product-defining ambiguity.

## Implementation sequence

1. **Scrape spike first — maximum 20 minutes.** Hit the GAF locator with Playwright, confirm selectors work, and dump 10–15 raw listing payloads to `backend/data/snapshots/`. Attempt profile-page payloads only if listing extraction is already reliable.
   If automated extraction is still blocked after 20 minutes, save the locator HTML or network response, or manually capture 10 visible GAF contractor records into a snapshot-derived fixture. Document the limitation and continue. Do not keep debugging selectors past the cap.
2. Scaffold Next.js and FastAPI.
3. Configure SQLModel with Supabase `DATABASE_URL`; create tables.
4. Build fixture data. Contractor records must derive from the step 1 snapshots — real GAF data, however it was captured. Fixture research, scores, and insights may be authored, but must match the PRD schemas exactly.
5. Implement the exact deterministic scoring rules, driven by `scoring_config.yaml`.
6. Implement lead list and detail routes.
7. Build the lead table, filters, and detail drawer.
8. Add scoring tests: representative boundaries, missing-data normalization, determinism, and config sensitivity.
9. Verify the complete fixture-mode demo from a clean start. **This is the gate.** Do not proceed past this point until the demo works end to end.
10. Add Perplexity research using the exact PRD prompt and Pydantic output — only if comfortably ahead.
11. Add OpenAI insight generation using the exact PRD prompt and Pydantic output — only if comfortably ahead.
12. Wire the step 1 scraper into live ingestion: parse snapshots into contractor records, upsert by `gaf_contractor_id`, persist search-run provenance — only if comfortably ahead.
13. Add P1 flag/regenerate only after P0 passes and time remains.

## If behind schedule

Use the following degradation order and record every cut under known limitations:

1. Run live Perplexity and OpenAI on **one contractor only**, with fixture research and insights for the rest. This preserves a live end-to-end AI demonstration at minimal cost.
2. Skip live Perplexity integration entirely. Use complete, source-backed fixture research derived from public sources.
3. Skip live OpenAI integration entirely. Use validated fixture insights matching the required schema.
4. Skip live ingestion wiring. Continue using contractor fixtures generated from the initial GAF snapshots.
5. Reduce scoring tests to representative boundaries, missing-data normalization, and determinism.
6. Drop the Account Fit secondary sort.
7. Simplify technical scoring detail presentation without removing the score, coverage, or formula version.

Never cut:

- the initial GAF scrape spike;
- persisted contractor data;
- deterministic scoring;
- the lead dashboard;
- the contractor detail drawer;
- visible research sources;
- clean missing/failure states;
- fixture mode that runs without external keys.

## Design boundaries

### GAF data

`gaf_scraper.py` collects and parses GAF listing/profile information. It does not perform research, scoring, insight generation, or database policy decisions.

### Research

`research.py` uses Perplexity for source-backed public facts. Use the exact prompt and data rules from the PRD. Each finding requires source evidence and confidence. Unknown information remains empty.

When full-batch live research is attempted, process every contractor independently. One contractor failure must not stop the batch. When using the time-constrained demo path, live research may run for one contractor while validated fixture research is used for the remainder.

Never infer unsupported revenue, employee count, pricing, purchasing volume, supplier relationships, private data, or Google-review content.

### Scoring

`scoring.py` contains pure deterministic functions only.

All weights, bucket thresholds, and the `formula_version` string live in `backend/app/scoring_config.yaml`, loaded once at startup and passed into scoring functions as an argument. Scoring functions never read the config file themselves. Tests pass a fixed test config so tuning weights does not break assertions.

Changing a weight requires bumping `formula_version` in the config. Scores persist under the version that produced them; earlier versions are retained, never overwritten.

Implement:

- exact Account Fit buckets;
- exact Opportunity buckets;
- missing-data normalization;
- score coverage;
- Lead Priority weighting;
- formula versions.

No database access, network calls, LLM calls, or alternate score formulas. Do not build a configuration editor UI — the YAML file is the configuration surface for the MVP.

### Insights

`insight_generator.py` transforms only scraped data, validated research, deterministic scores, and known product categories into guidance.

Use the exact PRD prompt. Do not conduct web research or introduce new facts. The AI priority label remains separate from official scoring.

### Routes

Routes validate HTTP input, obtain a database session, invoke focused operations, and return response schemas.

Dashboard GET routes read persisted PostgreSQL data only. Never run scraping or AI calls during dashboard reads.

## Simplicity

Prefer:

- small named functions;
- direct SQLModel queries;
- explicit Pydantic schemas;
- nullable values;
- visible status/error states;
- a small number of focused UI components;
- meaningful deterministic tests.

Avoid:

- microservices;
- queues;
- Redis;
- authentication;
- Docker unless already present;
- repository/controller/manager/provider/factory layers;
- generic abstractions;
- one-file-per-model fragmentation;
- speculative future features;
- unnecessary packages.

Do not create code merely to look production-grade.

## UI

The primary audience is a non-technical sales representative. Default to plain language; keep the technical view one click away.

Required:

- responsive lead table;
- search;
- certification filter;
- minimum-rating filter;
- deterministic sorting;
- contractor detail drawer;
- score breakdown, coverage, and formula version;
- research sources and confidence;
- separate AI assessment;
- loading, empty, missing-data, pending, and failure states.

### Progressive disclosure

Render the same data in two registers. A single "Show scoring detail" toggle in the detail drawer flips the whole panel between them. No data is hidden — only relabelled.

| Rep-facing (default) | Technical view (toggled) |
| --- | --- |
| `Priority: High · 82` | `Lead Priority 82 · lead-priority-v1` |
| "Based on 8 of 12 available signals" | `coverage 67%` plus the full subcomponent breakdown table |
| Verified / Needs checking | `confidence: high \| medium \| low` with source URL |
| "We found this" / "We think this" | `basis: observed \| inferred` |

### Provisional leads

Sort by deterministic Lead Priority as specified in the PRD, but badge any lead below 60% combined coverage as **Provisional**. A contractor whose research failed has its Opportunity subcomponents excluded from the denominator and would otherwise outrank a contractor whose research succeeded and found nothing. The badge makes that visible rather than silently inflating the rank.

Do not add unrelated pages or a design system.

## Environment and safety

Use environment variables including:

```text
DATABASE_URL
OPENAI_API_KEY
PERPLEXITY_API_KEY
PERPLEXITY_MODEL=sonar-pro
OPENAI_MODEL
FRONTEND_URL
USE_FIXTURES
```

Never guess or hardcode model identifiers. Read both model strings from the environment. Use `sonar-pro` rather than `sonar` for research: it returns richer citation metadata including publication dates, which the "Recent public business activity" scoring bucket depends on.

Perplexity's first request with a new JSON schema can take 10–30 seconds to prepare and may time out. Set a generous client timeout. If live Perplexity integration is attempted, validate the schema against one contractor before processing the batch. Do not make a separate throwaway request, and do not make any Perplexity call in fixture mode.

Never commit real credentials.

Use the Supabase Session Pooler for the persistent MVP FastAPI backend with a small SQLAlchemy application pool as specified in the PRD.

## Verification

Expected backend checks:

```bash
cd backend
pytest
python -m compileall app
```

Expected frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

Scoring tests must include a config-sensitivity case: pass two different scoring configs to the same pure function and assert that the resulting ranking differs and that each result carries its own formula version. This substantiates the configurable-scoring claim without requiring a live configuration migration.

Also run the application in fixture mode and manually verify:

- 10 or more leads render;
- no duplicate contractors after rerun;
- every lead shows complete or explicit pending/failed status;
- filters and sorting work;
- detail drawer opens;
- exact scores, coverage, and versions display;
- the active scoring configuration and formula version are persisted and displayed;
- sources display;
- missing AI data does not break the UI;
- the scoring detail toggle switches between rep-facing and technical views.

At completion, summarize:

- implementation;
- checks run;
- assumptions;
- known limitations;
- unmet P0 requirements.

Do not claim success if required checks fail.
