"""Database models for the roofing sales-intelligence MVP.

Six P0 tables + one P1 table. Contractor is current-state (upsert on rescrape).
LeadScore and Insight are versioned — the API returns the latest by default.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


# --------------------------------------------------------------------------
# Contractor — stable identity. Upsert key is gaf_contractor_id.
# --------------------------------------------------------------------------

class Contractor(SQLModel, table=True):
    __tablename__ = "contractor"

    id: Optional[int] = Field(default=None, primary_key=True)
    gaf_contractor_id: str = Field(unique=True, index=True)

    name: str = Field(index=True)
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None

    profile_url: Optional[str] = None
    website_url: Optional[str] = None
    external_reviews_url: Optional[str] = None  # link only, never review content

    rating: Optional[float] = None
    review_count: Optional[int] = None
    certification_tier: Optional[str] = Field(default=None, index=True)
    distinctions: Optional[list] = Field(default=None, sa_column=Column(JSON))

    about_text: Optional[str] = None
    business_start_year: Optional[int] = None  # not years_in_business; compute on read

    last_scraped_at: Optional[datetime] = None


# --------------------------------------------------------------------------
# Search provenance — one contractor can appear in many runs / locator types.
# --------------------------------------------------------------------------

class SearchRun(SQLModel, table=True):
    __tablename__ = "search_run"

    id: Optional[int] = Field(default=None, primary_key=True)
    search_zip: str
    search_radius_miles: int
    locator_type: str  # "residential" | "commercial"
    status: str = Field(default="pending")  # pending | completed | failed
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class SearchResult(SQLModel, table=True):
    __tablename__ = "search_result"
    __table_args__ = (UniqueConstraint("search_run_id", "contractor_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    search_run_id: int = Field(foreign_key="search_run.id", index=True)
    contractor_id: int = Field(foreign_key="contractor.id", index=True)
    distance_miles: Optional[float] = None  # as displayed by GAF, not computed


# --------------------------------------------------------------------------
# Research — validated Perplexity output. Payload is the Pydantic model dumped
# to JSON. Assign a stable `id` to every evidence item BEFORE persisting so
# Insight.supporting_source_ids can reference them.
# --------------------------------------------------------------------------

class ResearchFinding(SQLModel, table=True):
    __tablename__ = "research_finding"

    id: Optional[int] = Field(default=None, primary_key=True)
    contractor_id: int = Field(foreign_key="contractor.id", index=True)

    status: str = Field(default="pending", index=True)  # pending | completed | failed
    company_identity_confirmed: Optional[bool] = None
    overall_confidence: Optional[str] = None  # high | medium | low

    payload: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    error: Optional[str] = None

    model: Optional[str] = None  # e.g. sonar-pro
    researched_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------
# Scores — versioned. One row per score_type per scoring run.
# --------------------------------------------------------------------------

class LeadScore(SQLModel, table=True):
    __tablename__ = "lead_score"

    id: Optional[int] = Field(default=None, primary_key=True)
    contractor_id: int = Field(foreign_key="contractor.id", index=True)

    score_type: str = Field(index=True)  # account_fit | opportunity | lead_priority
    total: float
    coverage: float  # 0-100; <60 renders as Provisional
    breakdown: dict = Field(sa_column=Column(JSON))
    formula_version: str  # from scoring_config.yaml, e.g. lead-priority-v1

    scored_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------
# Insights — versioned. Never overwrite; API returns max(version).
# --------------------------------------------------------------------------

class Insight(SQLModel, table=True):
    __tablename__ = "insight"
    __table_args__ = (UniqueConstraint("contractor_id", "version"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    contractor_id: int = Field(foreign_key="contractor.id", index=True)
    version: int = Field(default=1)

    status: str = Field(default="pending", index=True)  # pending | completed | failed
    payload: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # surfaced separately from the deterministic score — never merged into it
    ai_priority_label: Optional[str] = None   # high | medium | low
    insight_confidence: Optional[str] = None  # high | medium | low

    trigger: str = Field(default="initial_run")  # initial_run | flag_regeneration
    triggering_flag_id: Optional[int] = None
    model: Optional[str] = None
    error: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------
# P1 only — build after P0 acceptance criteria pass.
# --------------------------------------------------------------------------

class InsightFlag(SQLModel, table=True):
    __tablename__ = "insight_flag"

    id: Optional[int] = Field(default=None, primary_key=True)
    contractor_id: int = Field(foreign_key="contractor.id", index=True)
    insight_id: int = Field(foreign_key="insight.id")

    reason: Optional[str] = None
    status: str = Field(default="open")  # open | pending_review | resolved
    created_at: datetime = Field(default_factory=datetime.utcnow)
