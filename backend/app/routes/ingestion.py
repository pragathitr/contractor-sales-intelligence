"""Ingestion route: orchestrates the MVP pipeline (PRD section 5) for one
search. Each stage is attempted for every contractor; one contractor's
failure never fails the batch. Requires a real display for Playwright (see
services/gaf_scraper.py) — not something a dashboard GET route ever triggers.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.config import get_settings, load_scoring_config
from app.database import get_session
from app.models import Contractor, Insight, LeadScore, ResearchFinding, SearchResult, SearchRun
from app.schemas import IngestionRunResponse
from app.services import gaf_scraper, insight_generator, research, research_mapping
from app.services.scoring import AccountFitInputs, OpportunityInputs, score_account_fit, score_lead_priority, score_opportunity

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

DEFAULT_ZIP = "10013"
DEFAULT_RADIUS_MILES = 25


def _upsert_contractor(session: Session, record: dict) -> Contractor:
    gaf_id = record.get("gaf_contractor_id")
    contractor = session.exec(select(Contractor).where(Contractor.gaf_contractor_id == gaf_id)).first()
    if contractor is None:
        contractor = Contractor(gaf_contractor_id=gaf_id)

    contractor.name = record.get("name") or contractor.name
    contractor.phone = record.get("phone")
    contractor.city = record.get("city")
    contractor.state = record.get("state")
    contractor.country = "US"
    contractor.profile_url = record.get("profile_url")
    contractor.rating = record.get("rating")
    contractor.review_count = record.get("review_count")
    contractor.certification_tier = record.get("certification_tier") or contractor.certification_tier
    contractor.distinctions = record.get("distinctions") or contractor.distinctions
    contractor.about_text = record.get("about_text") or contractor.about_text
    contractor.website_url = record.get("website_url") or contractor.website_url
    contractor.last_scraped_at = datetime.now(timezone.utc)

    session.add(contractor)
    session.flush()
    return contractor


def _run_research(session: Session, contractor: Contractor, settings) -> ResearchFinding:
    """Live Perplexity stage. One contractor's failure never stops the batch
    (PRD section 5) — caller persists status="failed" and moves on."""
    finding_row = ResearchFinding(contractor_id=contractor.id, status="pending")
    try:
        output = research.research_contractor(
            name=contractor.name,
            address=contractor.address,
            city=contractor.city,
            state=contractor.state,
            website_url=contractor.website_url,
            gaf_profile_url=contractor.profile_url,
            settings=settings,
        )
        finding_row.status = "completed"
        finding_row.company_identity_confirmed = output.company_identity_confirmed
        finding_row.overall_confidence = output.overall_confidence
        finding_row.payload = output.model_dump(mode="json")
        finding_row.model = settings.perplexity_model
    except research.ResearchError as exc:
        finding_row.status = "failed"
        finding_row.error = str(exc)
    session.add(finding_row)
    session.flush()
    return finding_row


def _score_and_persist(
    session: Session, contractor: Contractor, distance_miles: float | None, research_payload: dict | None, config: dict
) -> dict:
    account_fit_result = score_account_fit(
        AccountFitInputs(
            certification_tier=contractor.certification_tier,
            distinctions=contractor.distinctions,
            rating=contractor.rating,
            review_count=contractor.review_count,
            verified_services=research_mapping.map_verified_services(research_payload) if research_payload else None,
            business_scale_signals=research_mapping.map_business_scale_signals(research_payload) if research_payload else None,
            distance_miles=distance_miles,
            business_start_year=contractor.business_start_year,
        ),
        config,
    )

    if research_payload:
        recent_count, only_older = research_mapping.recent_project_count(research_payload)
        opportunity_inputs = OpportunityInputs(
            research_available=True,
            recent_project_count=recent_count,
            only_older_activity=only_older,
            hiring_expansion_signals=research_mapping.map_hiring_expansion_signals(research_payload),
            most_recent_activity_days=research_mapping.most_recent_activity_days(research_payload),
            product_demand_signals=research_mapping.map_product_demand_signals(research_payload),
            decision_maker_tier=research_mapping.decision_maker_tier(research_payload),
            contactability_signals=research_mapping.contactability_signals(research_payload),
        )
    else:
        opportunity_inputs = OpportunityInputs(research_available=False)

    opportunity_result = score_opportunity(opportunity_inputs, config)
    lead_priority_result = score_lead_priority(account_fit_result, opportunity_result, config)

    breakdown_by_type = {}
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
        breakdown_by_type[result.score_type] = {
            "total": result.total,
            "coverage": result.coverage,
            "breakdown": result.breakdown,
            "formula_version": result.formula_version,
        }
    return breakdown_by_type


def _run_insight(
    session: Session, contractor: Contractor, research_payload: dict | None, score_breakdown: dict, config: dict, settings
) -> None:
    """Live OpenAI stage. One contractor's failure never stops the batch."""
    insight_row = Insight(contractor_id=contractor.id, status="pending", version=1)
    try:
        product_categories = list(config["account_fit"]["product_service_alignment"]["services"].keys())
        output = insight_generator.generate_insight(
            contractor=contractor.model_dump(mode="json"),
            research=research_payload,
            score_breakdown=score_breakdown,
            product_categories=product_categories,
            version=1,
            settings=settings,
        )
        insight_row.status = "completed"
        insight_row.payload = output.model_dump(mode="json")
        insight_row.ai_priority_label = output.ai_priority_label
        insight_row.insight_confidence = output.insight_confidence
        insight_row.model = settings.openai_model
    except insight_generator.InsightError as exc:
        insight_row.status = "failed"
        insight_row.error = str(exc)
    session.add(insight_row)


@router.post("/run", response_model=IngestionRunResponse)
def run_ingestion(
    zip_code: str = DEFAULT_ZIP,
    radius_miles: int = DEFAULT_RADIUS_MILES,
    session: Session = Depends(get_session),
):
    settings = get_settings()
    config = load_scoring_config()

    search_run = SearchRun(
        search_zip=zip_code,
        search_radius_miles=radius_miles,
        locator_type=gaf_scraper.RESIDENTIAL,
        status="pending",
    )
    session.add(search_run)
    session.flush()

    try:
        records = gaf_scraper.run_ingestion(zip_code, radius_miles)
    except Exception as exc:  # noqa: BLE001 - the whole run failed, not one contractor
        search_run.status = "failed"
        search_run.error = str(exc)
        search_run.completed_at = datetime.now(timezone.utc)
        session.add(search_run)
        session.commit()
        raise HTTPException(status_code=502, detail=f"GAF ingestion failed: {exc}") from exc

    found = 0
    for record in records:
        try:
            contractor = _upsert_contractor(session, record)
            session.add(
                SearchResult(
                    search_run_id=search_run.id,
                    contractor_id=contractor.id,
                    distance_miles=record.get("distance_miles"),
                )
            )
            research_payload = None
            if not settings.use_fixtures and settings.perplexity_api_key:
                finding_row = _run_research(session, contractor, settings)
                if finding_row.status == "completed":
                    research_payload = finding_row.payload

            score_breakdown = _score_and_persist(session, contractor, record.get("distance_miles"), research_payload, config)

            if not settings.use_fixtures and settings.openai_api_key:
                _run_insight(session, contractor, research_payload, score_breakdown, config, settings)

            found += 1
        except Exception:  # noqa: BLE001 - one contractor failure must not fail the batch
            session.rollback()
            continue

    search_run.status = "completed"
    search_run.completed_at = datetime.now(timezone.utc)
    session.add(search_run)
    session.commit()

    return IngestionRunResponse(
        run_id=search_run.id,
        status=search_run.status,
        started_at=search_run.started_at,
        completed_at=search_run.completed_at,
        contractors_found=found,
    )


@router.get("/runs/{run_id}", response_model=IngestionRunResponse)
def get_ingestion_run(run_id: int, session: Session = Depends(get_session)):
    search_run = session.get(SearchRun, run_id)
    if not search_run:
        raise HTTPException(status_code=404, detail="Search run not found")
    contractors_found = len(session.exec(select(SearchResult).where(SearchResult.search_run_id == run_id)).all())
    return IngestionRunResponse(
        run_id=search_run.id,
        status=search_run.status,
        started_at=search_run.started_at,
        completed_at=search_run.completed_at,
        contractors_found=contractors_found,
        error=search_run.error,
    )
