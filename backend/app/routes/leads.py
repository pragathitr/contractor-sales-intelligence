"""Lead list and detail routes. Read persisted PostgreSQL data only — never
scrape or call an LLM during a dashboard read.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.config import load_scoring_config
from app.database import get_session
from app.models import Contractor, Insight, LeadScore, ResearchFinding, SearchResult
from app.schemas import (
    ContractorDetail,
    LeadDetailResponse,
    LeadListItem,
    LeadListResponse,
    ScoreBreakdown,
)
from app.services.scoring import is_provisional

router = APIRouter(prefix="/api/leads", tags=["leads"])


def _latest_scores(session: Session, contractor_id: int) -> dict[str, LeadScore]:
    rows = session.exec(
        select(LeadScore).where(LeadScore.contractor_id == contractor_id).order_by(LeadScore.scored_at.desc())
    ).all()
    latest: dict[str, LeadScore] = {}
    for row in rows:
        latest.setdefault(row.score_type, row)
    return latest


def _latest_research(session: Session, contractor_id: int) -> Optional[ResearchFinding]:
    return session.exec(
        select(ResearchFinding)
        .where(ResearchFinding.contractor_id == contractor_id)
        .order_by(ResearchFinding.researched_at.desc())
    ).first()


def _latest_insight(session: Session, contractor_id: int) -> Optional[Insight]:
    return session.exec(
        select(Insight).where(Insight.contractor_id == contractor_id).order_by(Insight.version.desc())
    ).first()


def _latest_distance(session: Session, contractor_id: int) -> Optional[float]:
    result = session.exec(
        select(SearchResult).where(SearchResult.contractor_id == contractor_id).order_by(SearchResult.id.desc())
    ).first()
    return result.distance_miles if result else None


def _years_in_business(business_start_year: Optional[int]) -> Optional[int]:
    if business_start_year is None:
        return None
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).year - business_start_year


@router.get("", response_model=LeadListResponse)
def list_leads(
    search: Optional[str] = None,
    certification: Optional[str] = None,
    minimum_rating: Optional[float] = None,
    sort: str = Query("lead_priority", pattern="^(lead_priority|account_fit)$"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    session: Session = Depends(get_session),
):
    config = load_scoring_config()

    query = select(Contractor)
    if search:
        query = query.where(Contractor.name.ilike(f"%{search}%"))
    if certification:
        query = query.where(Contractor.certification_tier == certification)
    if minimum_rating is not None:
        query = query.where(Contractor.rating >= minimum_rating)

    contractors = session.exec(query).all()

    items: list[LeadListItem] = []
    for contractor in contractors:
        scores = _latest_scores(session, contractor.id)
        lead_priority = scores.get("lead_priority")
        account_fit = scores.get("account_fit")
        research = _latest_research(session, contractor.id)
        insight = _latest_insight(session, contractor.id)

        coverage = lead_priority.coverage if lead_priority else 0.0
        items.append(
            LeadListItem(
                contractor_id=contractor.id,
                name=contractor.name,
                lead_priority=lead_priority.total if lead_priority else None,
                account_fit=account_fit.total if account_fit else None,
                lead_priority_coverage=coverage,
                certification_tier=contractor.certification_tier,
                rating=contractor.rating,
                review_count=contractor.review_count,
                distance_miles=_latest_distance(session, contractor.id),
                years_in_business=_years_in_business(contractor.business_start_year),
                research_status=research.status if research else "pending",
                insight_status=insight.status if insight else "pending",
                outreach_angle=(insight.payload or {}).get("outreach_angle") if insight and insight.payload else None,
                provisional=is_provisional(coverage, config),
            )
        )

    sort_key = (lambda i: i.lead_priority or 0) if sort == "lead_priority" else (lambda i: i.account_fit or 0)
    items.sort(key=sort_key, reverse=True)

    total = len(items)
    page = items[offset : offset + limit]
    return LeadListResponse(items=page, total=total, limit=limit, offset=offset)


@router.get("/{contractor_id}", response_model=LeadDetailResponse)
def get_lead_detail(contractor_id: int, session: Session = Depends(get_session)):
    config = load_scoring_config()
    contractor = session.get(Contractor, contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Contractor not found")

    scores = _latest_scores(session, contractor_id)
    lead_priority = scores.get("lead_priority")
    coverage = lead_priority.coverage if lead_priority else 0.0

    research = _latest_research(session, contractor_id)
    insight = _latest_insight(session, contractor_id)

    contractor_detail = ContractorDetail(
        id=contractor.id,
        gaf_contractor_id=contractor.gaf_contractor_id,
        name=contractor.name,
        phone=contractor.phone,
        address=contractor.address,
        city=contractor.city,
        state=contractor.state,
        country=contractor.country,
        zip_code=contractor.zip_code,
        profile_url=contractor.profile_url,
        website_url=contractor.website_url,
        external_reviews_url=contractor.external_reviews_url,
        rating=contractor.rating,
        review_count=contractor.review_count,
        certification_tier=contractor.certification_tier,
        distinctions=contractor.distinctions,
        about_text=contractor.about_text,
        business_start_year=contractor.business_start_year,
        years_in_business=_years_in_business(contractor.business_start_year),
        last_scraped_at=contractor.last_scraped_at,
        distance_miles=_latest_distance(session, contractor_id),
    )

    return LeadDetailResponse(
        contractor=contractor_detail,
        scores=[
            ScoreBreakdown(
                score_type=s.score_type,
                total=s.total,
                coverage=s.coverage,
                breakdown=s.breakdown,
                formula_version=s.formula_version,
                scored_at=s.scored_at,
            )
            for s in scores.values()
        ],
        research=research.payload if research and research.status == "completed" else None,
        research_status=research.status if research else "pending",
        research_error=research.error if research else None,
        insight=insight.payload if insight and insight.status == "completed" else None,
        insight_status=insight.status if insight else "pending",
        insight_error=insight.error if insight else None,
        provisional=is_provisional(coverage, config),
    )
