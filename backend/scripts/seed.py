"""Seeds fixture-mode data: loads backend/data/fixtures/contractors.json,
computes real deterministic scores via app.services.scoring, and persists
everything through one SearchRun. Safe to rerun — upserts by
gaf_contractor_id rather than duplicating.

Usage: python -m scripts.seed   (run from backend/)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.config import load_scoring_config
from app.database import create_db_and_tables, engine
from app.models import Contractor, Insight, LeadScore, ResearchFinding, SearchResult, SearchRun
from app.services.scoring import (
    AccountFitInputs,
    OpportunityInputs,
    score_account_fit,
    score_lead_priority,
    score_opportunity,
)

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
    """Seeding replaces the fixture snapshot wholesale on rerun rather than
    accumulating versions — real ingestion appends instead (see
    routes/ingestion.py), but fixture data has no meaningful history to keep."""
    for model in (LeadScore, ResearchFinding, Insight):
        for row in session.exec(select(model).where(model.contractor_id == contractor_id)).all():
            session.delete(row)
    session.flush()


def decision_maker_tier(research: dict | None) -> str | None:
    if not research:
        return None
    for dm in research.get("decision_makers", []):
        title = (dm.get("title") or "").lower()
        if any(k in title for k in ["owner", "president", "gm", "general manager", "operations", "production", "purchasing", "procurement"]):
            return "key_contact"
    return "other_management_contact" if research.get("decision_makers") else "none_verified"


def contactability_signals(research: dict | None) -> list[str]:
    if not research:
        return []
    signals = []
    for dm in research.get("decision_makers", []):
        if dm.get("business_email"):
            signals.append("direct_business_email")
        if dm.get("business_phone"):
            signals.append("direct_business_phone")
    if research.get("public_contacts"):
        signals.append("generic_contact")
    return signals


def most_recent_activity_days(research: dict | None) -> int | None:
    if not research:
        return None
    dates = [e.get("published_at") for e in research.get("recent_projects", []) if e.get("published_at")]
    if not dates:
        return None
    latest = max(dates)
    delta = datetime.now(timezone.utc) - datetime.fromisoformat(latest.replace("Z", "+00:00"))
    return delta.days


def seed() -> None:
    create_db_and_tables()
    config = load_scoring_config()

    with open(FIXTURE_PATH, encoding="utf-8") as f:
        records = json.load(f)

    with Session(engine) as session:
        search_run = SearchRun(
            search_zip=SEARCH_ZIP,
            search_radius_miles=SEARCH_RADIUS,
            locator_type="residential",
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
        session.add(search_run)
        session.flush()

        for record in records:
            contractor = upsert_contractor(session, record["contractor"])
            clear_derived_rows(session, contractor.id)

            existing_result = session.exec(
                select(SearchResult).where(
                    SearchResult.search_run_id == search_run.id, SearchResult.contractor_id == contractor.id
                )
            ).first()
            if not existing_result:
                session.add(
                    SearchResult(
                        search_run_id=search_run.id,
                        contractor_id=contractor.id,
                        distance_miles=record["distance_miles"],
                    )
                )

            research = record["research"]
            finding = ResearchFinding(
                contractor_id=contractor.id,
                status=record["research_status"],
                company_identity_confirmed=research.get("company_identity_confirmed") if research else None,
                overall_confidence=research.get("overall_confidence") if research else None,
                payload=research,
                error=record["research_error"],
                model="sonar-pro" if research else None,
            )
            session.add(finding)

            insight_payload = record["insight"]
            insight = Insight(
                contractor_id=contractor.id,
                version=1,
                status=record["insight_status"],
                payload=insight_payload,
                ai_priority_label=insight_payload.get("ai_priority_label") if insight_payload else None,
                insight_confidence=insight_payload.get("insight_confidence") if insight_payload else None,
                error=record["insight_error"],
                model="gpt-4o-mini" if insight_payload else None,
            )
            session.add(insight)

            account_fit_result = score_account_fit(
                AccountFitInputs(
                    certification_tier=contractor.certification_tier,
                    distinctions=contractor.distinctions,
                    rating=contractor.rating,
                    review_count=contractor.review_count,
                    verified_services=record["verified_services"] if research else None,
                    business_scale_signals=record["business_scale_signals"] if research else None,
                    distance_miles=record["distance_miles"],
                    business_start_year=contractor.business_start_year,
                ),
                config,
            )
            opportunity_result = score_opportunity(
                OpportunityInputs(
                    research_available=record["research_status"] == "completed",
                    recent_project_count=0 if research else None,
                    only_older_activity=False,
                    hiring_expansion_signals=research.get("growth_signals", []) if research else None,
                    most_recent_activity_days=most_recent_activity_days(research),
                    product_demand_signals=research.get("product_demand_signals", []) if research else None,
                    decision_maker_tier=decision_maker_tier(research),
                    contactability_signals=contactability_signals(research) if research else None,
                ),
                config,
            )
            lead_priority_result = score_lead_priority(account_fit_result, opportunity_result, config)

            for result in (account_fit_result, opportunity_result, lead_priority_result):
                session.add(
                    LeadScore(
                        contractor_id=contractor.id,
                        score_type=result.score_type,
                        total=result.total,
                        coverage=result.coverage,
                        breakdown=result.breakdown,
                        formula_version=result.formula_version,
                    )
                )

        session.commit()
        print(f"Seeded {len(records)} contractors under search_run_id={search_run.id}")


if __name__ == "__main__":
    seed()
