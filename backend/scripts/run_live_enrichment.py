"""Live enrichment: reuses the already-scraped real contractor data in
backend/data/fixtures/contractors.json (no re-scraping GAF) and runs real
Perplexity research + OpenAI insight generation + deterministic scoring
against them, persisting to whatever DATABASE_URL points at.

Validates the Perplexity JSON schema against one contractor first (PRD/
CLAUDE.md requirement — the first request against a new schema can take
10-30s), then processes the rest. One contractor's failure never stops the
batch.

Usage: python -m scripts.run_live_enrichment [--limit N]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.config import get_settings, load_scoring_config
from app.database import create_db_and_tables, engine
from app.models import Contractor, Insight, LeadScore, ResearchFinding, SearchResult, SearchRun
from app.routes.ingestion import _run_insight, _run_research, _score_and_persist
from app.services.gaf_scraper import RESIDENTIAL

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "contractors.json"
SEARCH_ZIP = "10013"
SEARCH_RADIUS = 25


def upsert_contractor(session: Session, fields: dict) -> Contractor:
    contractor = session.exec(
        select(Contractor).where(Contractor.gaf_contractor_id == fields["gaf_contractor_id"])
    ).first()
    if contractor is None:
        contractor = Contractor(gaf_contractor_id=fields["gaf_contractor_id"])
    for key, value in fields.items():
        setattr(contractor, key, value)
    contractor.last_scraped_at = datetime.now(timezone.utc)
    session.add(contractor)
    session.flush()
    return contractor


def clear_derived_rows(session: Session, contractor_id: int) -> None:
    for model in (LeadScore, ResearchFinding, Insight):
        for row in session.exec(select(model).where(model.contractor_id == contractor_id)).all():
            session.delete(row)
    session.flush()


def process_one(session: Session, record: dict, settings, config: dict) -> str:
    contractor = upsert_contractor(session, record["contractor"])
    clear_derived_rows(session, contractor.id)

    research_payload = None
    finding_row = _run_research(session, contractor, settings)
    if finding_row.status == "completed":
        research_payload = finding_row.payload

    score_breakdown = _score_and_persist(session, contractor, record["distance_miles"], research_payload, config)
    _run_insight(session, contractor, research_payload, score_breakdown, config, settings)
    session.commit()
    return finding_row.status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N contractors")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.perplexity_api_key or not settings.openai_api_key:
        raise SystemExit("PERPLEXITY_API_KEY and OPENAI_API_KEY must both be set for a live run.")

    create_db_and_tables()
    config = load_scoring_config()

    with open(FIXTURE_PATH, encoding="utf-8") as f:
        records = json.load(f)
    if args.limit:
        records = records[: args.limit]

    with Session(engine) as session:
        search_run = session.exec(
            select(SearchRun).where(SearchRun.search_zip == SEARCH_ZIP, SearchRun.locator_type == RESIDENTIAL)
        ).first()
        if search_run is None:
            search_run = SearchRun(search_zip=SEARCH_ZIP, search_radius_miles=SEARCH_RADIUS, locator_type=RESIDENTIAL, status="completed")
            session.add(search_run)
            session.flush()

        # Validate the Perplexity schema against one contractor first.
        first = records[0]
        print(f"[1/{len(records)}] validating schema against {first['contractor']['name']}...")
        status = process_one(session, first, settings, config)
        print(f"  -> research status: {status}")

        contractor = session.exec(
            select(Contractor).where(Contractor.gaf_contractor_id == first["contractor"]["gaf_contractor_id"])
        ).first()
        existing_result = session.exec(
            select(SearchResult).where(SearchResult.search_run_id == search_run.id, SearchResult.contractor_id == contractor.id)
        ).first()
        if not existing_result:
            session.add(SearchResult(search_run_id=search_run.id, contractor_id=contractor.id, distance_miles=first["distance_miles"]))
        session.commit()

        completed, failed = 0, 0
        for i, record in enumerate(records[1:], start=2):
            name = record["contractor"]["name"]
            try:
                status = process_one(session, record, settings, config)
                print(f"[{i}/{len(records)}] {name}: research={status}")
                completed += 1 if status == "completed" else 0
                failed += 1 if status == "failed" else 0
            except Exception as exc:  # noqa: BLE001 - one contractor failure must not fail the batch
                session.rollback()
                print(f"[{i}/{len(records)}] {name}: FAILED ({exc})")
                continue

            contractor = session.exec(
                select(Contractor).where(Contractor.gaf_contractor_id == record["contractor"]["gaf_contractor_id"])
            ).first()
            existing_result = session.exec(
                select(SearchResult).where(SearchResult.search_run_id == search_run.id, SearchResult.contractor_id == contractor.id)
            ).first()
            if not existing_result:
                session.add(SearchResult(search_run_id=search_run.id, contractor_id=contractor.id, distance_miles=record["distance_miles"]))
                session.commit()

        print(f"Done. {len(records)} contractors processed under search_run_id={search_run.id}")


if __name__ == "__main__":
    main()
