"""Pydantic schemas for external-data boundaries: Perplexity/OpenAI validated
output, and API request/response shapes. Routes and services never pass raw
dicts across these boundaries.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

Confidence = Literal["high", "medium", "low"]
Status = Literal["pending", "completed", "failed"]


# --------------------------------------------------------------------------
# Perplexity research — validated output (PRD 7.4)
# --------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    source_url: str
    source_title: Optional[str] = None
    evidence: str
    published_at: Optional[str] = None
    confidence: Confidence


class DecisionMaker(BaseModel):
    name: str
    title: Optional[str] = None
    business_email: Optional[str] = None
    business_phone: Optional[str] = None
    evidence: list[EvidenceItem] = []


class ResearchOutput(BaseModel):
    company_identity_confirmed: bool
    decision_makers: list[DecisionMaker] = []
    services: list[EvidenceItem] = []
    service_territories: list[EvidenceItem] = []
    recent_projects: list[EvidenceItem] = []
    growth_signals: list[EvidenceItem] = []
    product_demand_signals: list[EvidenceItem] = []
    public_contacts: list[EvidenceItem] = []
    risks_and_unknowns: list[str] = []
    overall_confidence: Confidence
    researched_at: datetime


# --------------------------------------------------------------------------
# OpenAI insight generation — validated output (PRD 9.3)
# --------------------------------------------------------------------------

class WhyThisLead(BaseModel):
    text: str
    basis: Literal["observed", "inferred"]


class ProductFit(BaseModel):
    category: str
    reason: str
    confidence: Confidence
    supporting_source_ids: list[int] = []


class InsightOutput(BaseModel):
    account_summary: str
    why_this_lead: list[WhyThisLead] = []
    potential_product_fit: list[ProductFit] = []
    why_contact_now: list[str] = []
    decision_makers: list[str] = []
    outreach_angle: str
    discovery_questions: list[str] = []
    risks_and_unknowns: list[str] = []
    recommended_next_action: str

    ai_priority_label: Literal["high", "medium", "low"]
    ai_priority_rationale: str
    insight_confidence: Confidence

    created_at: datetime
    version: int


# --------------------------------------------------------------------------
# API responses
# --------------------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    score_type: str
    total: float
    coverage: float
    breakdown: dict
    formula_version: str
    scored_at: datetime


class LeadListItem(BaseModel):
    contractor_id: int
    name: str
    lead_priority: Optional[float] = None
    account_fit: Optional[float] = None
    lead_priority_coverage: Optional[float] = None
    certification_tier: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    distance_miles: Optional[float] = None
    years_in_business: Optional[int] = None
    research_status: Status
    insight_status: Status
    outreach_angle: Optional[str] = None
    provisional: bool


class LeadListResponse(BaseModel):
    items: list[LeadListItem]
    total: int
    limit: int
    offset: int


class ContractorDetail(BaseModel):
    id: int
    gaf_contractor_id: str
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None
    profile_url: Optional[str] = None
    website_url: Optional[str] = None
    external_reviews_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    certification_tier: Optional[str] = None
    distinctions: Optional[list] = None
    about_text: Optional[str] = None
    business_start_year: Optional[int] = None
    years_in_business: Optional[int] = None
    last_scraped_at: Optional[datetime] = None
    distance_miles: Optional[float] = None


class LeadDetailResponse(BaseModel):
    contractor: ContractorDetail
    scores: list[ScoreBreakdown]
    research: Optional[ResearchOutput] = None
    research_status: Status
    research_error: Optional[str] = None
    insight: Optional[InsightOutput] = None
    insight_status: Status
    insight_error: Optional[str] = None
    provisional: bool


class IngestionRunResponse(BaseModel):
    run_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    contractors_found: int = 0
    error: Optional[str] = None
