# Roofing Sales Intelligence MVP — PRD

## 1. Goal

Build an AI-assisted sales-intelligence dashboard for a roofing-material distributor.

The application collects residential roofing contractors within 25 miles of ZIP code `10013` from GAF, stores and ranks them, enriches each contractor with source-backed public research, and generates concise account-planning guidance for sales representatives.

The product should answer:

> Which contractors should a sales representative prioritize, why, who should they contact, what product categories may fit, and what should they discuss?

This is a three-hour MVP. Build one complete, reliable vertical slice rather than many unfinished features.

---

## 2. Primary user and workflow

**Primary user:** sales representative at a roofing-material distributor.

1. Open the dashboard.
2. View contractors ranked by deterministic Lead Priority.
3. Search, filter, and sort the list.
4. Open a contractor detail drawer.
5. Review:
   - contractor information;
   - score and score breakdown;
   - source-backed research;
   - decision-makers;
   - potential product fit;
   - outreach recommendations;
   - risks and unknowns.
6. Decide the next sales action.

The system supports sales judgment; it does not replace it.

---

## 3. Technology

### Frontend
- Next.js App Router
- TypeScript
- Tailwind CSS

### Backend
- FastAPI
- Python
- SQLModel
- Pydantic
- Playwright Python

### Data and AI
- Supabase PostgreSQL
- Supavisor Session Pooler through `DATABASE_URL`
- Perplexity API for source-backed public research
- OpenAI API for structured sales insights

Do not add microservices, Redis, queues, authentication, Docker, or other infrastructure to the MVP.

---

## 4. Repository structure

```text
frontend/
  app/
    layout.tsx
    page.tsx
  components/
    lead-table.tsx
    lead-filters.tsx
    lead-detail-drawer.tsx
    score-breakdown.tsx
    source-list.tsx
  lib/
    api.ts
    types.ts

backend/
  app/
    __init__.py
    main.py
    config.py
    database.py
    models.py
    schemas.py
    prompts.py
    routes/
      __init__.py
      leads.py
      ingestion.py
    services/
      __init__.py
      gaf_scraper.py
      research.py
      scoring.py
      insight_generator.py
  data/
    fixtures/
    snapshots/
  scripts/
    ingest.py
    seed.py
  tests/
    test_scoring.py
  pyproject.toml

README.md
.env.example
```

Keep files focused. Do not add repository, manager, controller, provider, factory, generic utility, or one-file-per-model layers unless the existing code genuinely requires them.

---

## 5. MVP pipeline

For every contractor in the limited MVP batch:

```text
GAF listing scrape
→ GAF profile scrape
→ upsert contractor and search context
→ Perplexity research
→ deterministic scoring
→ OpenAI insight generation
→ persist results
→ dashboard reads persisted data
```

Important behavior:

- Attempt every stage for every contractor in the batch.
- One contractor failure must not fail the batch.
- Research or insight failure must not hide the contractor.
- Store `pending`, `completed`, or `failed` status for research and insights.
- Dashboard reads must never trigger Playwright, Perplexity, or OpenAI.
- In production, these stages would become independent asynchronous jobs; they remain synchronous or manually triggered in the MVP.

---

## 6. P0 requirements

### 6.1 GAF ingestion

- Default search: ZIP `10013`, radius `25 miles`, residential locator.
- Use Playwright for the locator interaction.
- Collect and persist at least 10 contractors.
- Scrape the profile page for every collected contractor when available.
- Save raw listing/profile payloads under `backend/data/snapshots/`.
- Provide fixture mode under `backend/data/fixtures/`.
- Fixture mode must contain enough contractor, research, score, and insight data to demonstrate the complete UI without external APIs.
- Rerunning ingestion must update contractors rather than create duplicates.
- Respect reasonable delays and log errors.
- Do not scrape or store individual Google reviews.
- Store the external Google-review URL only when GAF exposes it.

### 6.2 Contractor fields

Store current contractor data:

```text
gaf_contractor_id
name
phone
address
city
state
country
zip_code
profile_url
website_url
external_reviews_url
rating
review_count
certification_tier
distinctions
about_text
business_start_year
last_scraped_at
```

Use `business_start_year`, not a stored `years_in_business` value.

Store search provenance separately:

```text
search_run_id
contractor_id
search_zip
search_radius_miles
locator_type
distance_miles
```

`locator_type` describes which locator produced the result. It is not treated as a permanent contractor classification.

---

## 7. Perplexity research

### 7.1 Purpose

Perplexity adds verifiable public facts not reliably available on GAF.

Research:

- verified owner, president, general manager, operations, production, procurement, or purchasing contacts;
- services and roofing-system categories;
- service territory and verified business locations;
- projects, permits, portfolio updates, or announcements within the last 18 months;
- hiring, expansion, new-location, new-crew, or new-service signals;
- public business contact information;
- source-backed product-demand signals;
- conflicting information, risks, and unknowns.

Do not research or infer:

- private personal information;
- unsupported revenue or employee count;
- pricing or purchasing volume;
- supplier relationships or dissatisfaction;
- individual Google review content.

### 7.2 Inputs

```text
contractor name
address
city and state
website URL
GAF profile URL
```

### 7.3 Prompt template

Store this template in `backend/app/prompts.py`:

```text
Research the roofing contractor below for a roofing-material distributor's
sales account-planning workflow.

Contractor:
- Name: {name}
- Address: {address}
- City/State: {city}, {state}
- Website: {website_url}
- GAF profile: {gaf_profile_url}

First confirm that every source refers to this exact contractor. Use the
address, location, website domain, and business description to avoid confusing
it with another company.

Research:
1. Verified decision-makers involved in ownership, operations, production,
   purchasing, or procurement.
2. Roofing services and roofing-system categories offered.
3. Geographic service territory and verified business locations.
4. Relevant projects, permits, portfolio updates, or announcements from the
   last 18 months.
5. Hiring, expansion, new-location, new-crew, or new-service signals.
6. Public business contact information.
7. Evidence indicating potential roofing-product demand.
8. Important risks, conflicting information, or missing information.

Rules:
- Return only facts supported by public sources.
- Do not infer revenue, employee count, pricing, purchasing volume, supplier
  relationships, or private information.
- Do not use or reproduce individual Google review content.
- Return null or an empty list when information cannot be verified.
- Include source URL, source title, supporting evidence, publication date when
  available, and confidence for every finding.
- Separate observed facts from interpretations.
- Return valid JSON matching the supplied schema.
```

### 7.4 Validated output

Use Pydantic models representing:

```text
company_identity_confirmed: boolean

decision_makers[]
  name
  title
  business_email
  business_phone
  evidence[]

services[]
service_territories[]
recent_projects[]
growth_signals[]
product_demand_signals[]
public_contacts[]

each evidence item:
  source_url
  source_title
  evidence
  published_at
  confidence: high | medium | low

risks_and_unknowns[]
overall_confidence: high | medium | low
researched_at
```

Validate before saving. Invalid results become `failed` or `unavailable`; never save malformed or fabricated fallback data.

### 7.5 Utilization

Validated research is:

1. displayed with sources in the contractor detail drawer;
2. converted into deterministic score inputs by Python;
3. passed to OpenAI for sales-guidance generation.

Perplexity extracts evidence. It does not assign the official score.

---

## 8. Deterministic scoring

All official numeric scores are calculated by pure Python functions in `scoring.py`.

Store:

```text
score_type
total
breakdown
coverage
formula_version
scored_at
```

Place configurable thresholds and weights together in `scoring.py` or one small scoring configuration object. Use formula versions:

```text
account-fit-v1
opportunity-v1
lead-priority-v1
```

### 8.1 Missing-data rule

Missing information is unknown, not negative.

Calculate at the subcomponent level:

```text
score = earned points across available subcomponents
        / maximum points across available subcomponents
        × 100

coverage = maximum points across available subcomponents
           / maximum possible points
           × 100
```

A completed search that found no verified signal is an available zero. A stage that did not run or failed is unavailable and excluded from the denominator.

Display low-coverage scores as provisional.

### 8.2 Account Fit Score — 0 to 100

Answers:

> Is this generally a valuable potential account?

#### Certification and distinctions — 25

Certification tier, maximum 20:

```text
Master Elite                         20
Certified Plus                       14
Certified                             8
Other verified GAF certification      5
Missing                               unavailable
```

Distinctions, maximum 5:

```text
President's Club                     +5
Other verified GAF distinctions     +2 each
Cap distinction points at             5
```

#### Rating and review volume — 20

Rating, maximum 10:

```text
4.80–5.00                            10
4.50–4.79                             8
4.00–4.49                             5
Below 4.00                            2
Missing                         unavailable
```

Review volume, maximum 10:

```text
100+                                  10
50–99                                  8
20–49                                  6
5–19                                   3
1–4                                    1
0                                      0
Missing                         unavailable
```

Use only aggregate rating and review count displayed by GAF. Do not use individual Google reviews.

#### Product/service alignment — 20

Award points for distinct verified services, capped at 20:

```text
Residential replacement or shingles   6
Repair or maintenance                  3
Ventilation or roofing accessories     3
Solar roofing                          3
Metal roofing                          3
Commercial roofing or coatings         2
```

The categories are initial assumptions and should later be mapped to the distributor's actual catalog.

#### Business scale signals — 15

Award verified signals, capped at 15:

```text
Two or more verified locations         5
Serves multiple counties/boroughs      3
Multiple crews or capacity stated      4
Five or more recent projects/permits   3
```

Do not invent company size, employees, or revenue.

#### Territory fit — 10

Use distance from the search or assigned branch:

```text
0–5 miles                             10
>5–10 miles                            8
>10–15 miles                           6
>15–20 miles                           4
>20–25 miles                           2
Over 25 miles                          0
Missing                         unavailable
```

#### Years in business — 10

Compute from `business_start_year`:

```text
15+ years                             10
8–14 years                             8
3–7 years                              5
Under 3 years                          3
Missing                         unavailable
```

### 8.3 Opportunity Score — 0 to 100

Answers:

> Is there a credible reason to contact this contractor now?

Only use validated research signals from the last 18 months unless otherwise stated.

#### Recent project or permit activity — 30

```text
5+ verified recent projects/permits   30
3–4                                   24
1–2                                   15
Only older verified activity           5
Research completed, none found         0
Research unavailable             unavailable
```

#### Hiring or expansion signals — 20

Award verified signals, capped at 20:

```text
New location or territory expansion    8
Relevant active hiring                  6
New roofing service/category            4
Additional crews or capacity            2
```

#### Recent public business activity — 15

Use the most recent verified project, portfolio update, announcement, or business post:

```text
Within 90 days                         15
91–180 days                            10
181–365 days                            6
366–540 days                            3
Research completed, none found          0
Research unavailable             unavailable
```

#### Product-demand trigger — 15

Award verified signals, capped at 15:

```text
Recent project tied to a product category       6
Newly added roofing service/category            5
Expansion or promotion implying material demand 4
```

#### Verified decision-maker — 10

```text
Verified owner, president, GM, operations,
production, procurement, or purchasing contact 10

Verified other relevant management contact       6
No verified decision-maker                       0
Research unavailable                       unavailable
```

#### Contactability — 10

Award verified public business contact options, capped at 10:

```text
Direct business email for decision-maker         5
Direct business phone for decision-maker         3
Generic business email or contact page           2
No usable public contact                          0
Research unavailable                       unavailable
```

### 8.4 Lead Priority

When both component scores have data:

```text
Lead Priority = 65% Account Fit + 35% Opportunity
```

When some subcomponents are unavailable, calculate Lead Priority from the available globally weighted subcomponents and normalize to 0–100. Also store combined coverage.

The dashboard defaults to deterministic Lead Priority sorting. Account Fit remains separately sortable.

### 8.5 Sales-team calibration

These weights are an interpretable starting hypothesis, not universal truth.

Future production work must:

- review criteria with sales representatives and managers;
- incorporate their proven qualification methodology;
- backtest against CRM outcomes such as conversion, order value, repeat purchase, and sales-cycle length;
- version scoring configurations as they change.

---

## 9. OpenAI insight generation

### 9.1 Purpose

Research answers:

> What do we know?

Insights answer:

> What should the sales representative do with it?

OpenAI receives only:

- scraped GAF data;
- validated Perplexity research;
- deterministic score and breakdown;
- known distributor product categories.

It must not perform new web research.

### 9.2 Prompt template

Store this template in `backend/app/prompts.py`:

```text
You are helping a roofing-material distributor prepare for sales outreach.

Using only the supplied contractor data, validated research findings, score
breakdown, and evidence, generate concise and practical account-planning
insights.

Rules:
- Do not introduce facts absent from the supplied data.
- Do not claim the contractor definitely needs a product.
- Use "potential product fit" and explain the supporting evidence.
- Clearly distinguish observed facts from inferences and suggested actions.
- If information is unavailable, say it requires verification.
- Do not infer revenue, purchasing volume, employee count, pricing, or supplier
  dissatisfaction.
- Do not use generic sales language.
- Recommend specific discovery questions that help the representative verify
  assumptions.
- Return valid JSON matching the supplied schema.
```

### 9.3 Validated output

```text
account_summary

why_this_lead[]
  text
  basis: observed | inferred

potential_product_fit[]
  category
  reason
  confidence
  supporting_source_ids[]

why_contact_now[]
decision_makers[]
outreach_angle
discovery_questions[]
risks_and_unknowns[]
recommended_next_action

ai_priority_label: high | medium | low
ai_priority_rationale
insight_confidence: high | medium | low

created_at
version
```

The LLM's `ai_priority_label` is displayed as a separate assessment. It must never alter the official deterministic score or default sort.

Persist each regeneration as a new version. Return the latest version by default.

---

## 10. Data model

Required tables:

```text
Contractor
SearchRun
SearchResult
ResearchFinding
LeadScore
Insight
```

Optional P1 table:

```text
InsightFlag
```

Relationships:

- A contractor may appear in many search runs.
- A contractor may have many research findings.
- A contractor may have many score versions.
- A contractor may have many insight versions.
- The API returns latest versions by default.

Use `gaf_contractor_id` as the unique contractor upsert key.

---

## 11. API routes

Routes are thin HTTP entry points. They validate inputs, obtain a database session, call focused service functions, and return response schemas.

### P0 routes

```text
GET  /health
GET  /api/leads
GET  /api/leads/{contractor_id}
POST /api/ingestion/run
GET  /api/ingestion/runs/{run_id}
```

`GET /api/leads` supports:

```text
search
certification
minimum_rating
sort: lead_priority | account_fit
limit
offset
```

Dashboard routes read persisted PostgreSQL data only.

### P1 routes, only after P0 is complete

```text
POST /api/leads/{contractor_id}/flags
POST /api/leads/{contractor_id}/regenerate
```

Regeneration:

- affects only the flagged contractor;
- creates a new versioned insight;
- preserves the previous version;
- links the new version to the flag/trigger;
- marks the flag `pending_review`, not automatically resolved.

No role gating is required for the MVP because authentication is out of scope.

---

## 12. UI

### Lead table

Show:

- contractor name;
- Lead Priority;
- Account Fit;
- score coverage;
- certification;
- rating and review count;
- distance;
- computed experience;
- research status;
- short outreach angle.

Support:

- contractor search;
- certification filter;
- minimum-rating filter;
- deterministic sorting;
- opening contractor details.

### Detail drawer

Show:

- contractor profile;
- score breakdown and formula version;
- why this lead;
- researched facts and source links;
- potential product fit;
- why contact now;
- decision-makers;
- outreach angle;
- discovery questions;
- risks and unknowns;
- recommended next action;
- separate AI priority assessment;
- last researched time.

Handle loading, empty, missing-data, and failure states cleanly.

---

## 13. Code quality

- Prefer small, direct functions.
- Keep routes thin.
- Keep scoring pure: no database or network calls in `scoring.py`.
- Keep research separate from insight generation.
- Use Pydantic at all external-data boundaries.
- Avoid duplicate types and business logic.
- Add comments only for non-obvious reasoning.
- Do not add unused abstractions or speculative features.
- Never commit secrets.
- Provide `.env.example`.
- Add focused score tests for:
  - exact category boundaries;
  - missing-data normalization;
  - coverage;
  - combined Lead Priority;
  - deterministic repeatability.

Suggested Supabase Session Pooler configuration for one persistent FastAPI backend:

```python
engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    pool_pre_ping=True,
)
```

---

## 14. P0 acceptance criteria

P0 is complete when:

1. At least 10 contractors are persisted and visible.
2. Fixture mode demonstrates the complete dashboard without external keys.
3. Every contractor in the demo batch has either completed or explicit failed/pending research and insight status.
4. Rerunning ingestion does not create duplicate contractors.
5. Leads have deterministic scores, breakdowns, coverage, and formula versions.
6. The dashboard supports search, filter, sort, and detail viewing.
7. Source-backed research and generated insights are visible for the fixture batch.
8. Missing or failed AI data does not break the dashboard.
9. Source URLs and confidence are visible.
10. Individual Google reviews are not scraped or stored.
11. Core scoring tests pass.
12. README documents setup, environment variables, commands, assumptions, and limitations.

---

## 15. Build order

1. Scaffold frontend and backend.
2. Configure Supabase and create models.
3. Seed fixture contractor, research, score, and insight data.
4. Implement deterministic scoring and tests.
5. Implement lead-list and lead-detail routes.
6. Build dashboard and detail drawer.
7. Implement validated Perplexity research.
8. Implement validated OpenAI insight generation.
9. Implement live GAF ingestion.
10. Add P1 flag/regenerate only if time remains.
11. Verify fixture mode from a clean start.

Do not sacrifice the complete fixture-backed vertical slice for optional live integrations.

---

## 16. Future work for the presentation

### Pipeline scale and reliability

- Move scraping, research, scoring, and insight generation into asynchronous jobs.
- Add a queue, worker scaling, per-contractor retries, idempotency keys, and rate limiting.
- Refresh research only when stale, source data changes, or a user explicitly requests it.
- Separate services only when workload scale or team ownership justifies it.

### Concurrent dashboard access

- Run stateless FastAPI replicas behind a load balancer.
- Use Supavisor Transaction Pooler for horizontally autoscaling/serverless runtime patterns.
- Add server-side pagination, indexes, caching, load testing, and read replicas when measurements justify them.

### Sales methodology

- Conduct scoring workshops with sales representatives and managers.
- Backtest scores using CRM outcomes.
- Make weights configurable and versioned.
- Add rep feedback and outcome tracking.

### Territory and data expansion

- Support multiple ZIP codes, branches, and assigned rep territories.
- Add geocoding and distance from the assigned distributor branch.
- Add commercial locator support and Canadian postal codes.
- Track certification-tier changes as events rather than overwriting history.

### Governance and cost control

- Add authentication and role-based access.
- Admin-gate regeneration and expensive research actions.
- Add configurable retention policies.
- Keep current insights hot and archive older versions and audit history to lower-cost storage.

### Integrations and signals

- Integrate with CRM account ownership, notes, tasks, and outcomes.
- Add official permit datasets and other licensed data sources.
- Evaluate third-party APIs only after licensing and legal review.
- Do not scrape restricted review content.

---

## 17. Non-goals for P0

Do not build:

- authentication or roles;
- microservices;
- background queues;
- Redis;
- read replicas;
- CRM integration;
- email sequencing;
- predictive machine learning;
- commercial or Canadian locator support;
- cold-storage infrastructure;
- Google-review scraping;
- advanced review workflows.

These are production-evolution topics, not requirements for the three-hour build.
