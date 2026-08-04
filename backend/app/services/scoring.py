"""Pure deterministic scoring functions.

No database access, network calls, LLM calls, or alternate score formulas
live here. All weights, bucket thresholds, and formula versions come from
`scoring_config.yaml`, loaded once at startup and passed in as `config` by
the caller — these functions never read the file themselves.

Missing-data rule (subcomponent level):
    score    = earned points across available subcomponents
               / maximum points across available subcomponents * 100
    coverage = maximum points across available subcomponents
               / maximum possible points * 100

A subcomponent is "available" when its input is not None. `None` means the
stage that would supply it did not run or failed. An empty list/zero count
is a completed search that found nothing — an available zero, not missing.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Subcomponent:
    name: str
    points: Optional[float]  # None => unavailable, excluded from both sums
    max_points: float


@dataclass
class ScoreResult:
    score_type: str
    total: float
    coverage: float
    breakdown: dict
    formula_version: str


def _combine(score_type: str, formula_version: str, subs: list[Subcomponent]) -> ScoreResult:
    available = [s for s in subs if s.points is not None]
    max_possible = sum(s.max_points for s in subs)
    earned = sum(s.points for s in available)
    max_available = sum(s.max_points for s in available)

    total = round(earned / max_available * 100, 2) if max_available > 0 else 0.0
    coverage = round(max_available / max_possible * 100, 2) if max_possible > 0 else 0.0

    breakdown = {
        s.name: {
            "points": s.points,
            "max_points": s.max_points,
            "available": s.points is not None,
        }
        for s in subs
    }
    return ScoreResult(
        score_type=score_type,
        total=total,
        coverage=coverage,
        breakdown=breakdown,
        formula_version=formula_version,
    )


def _band_by_value(value: float, bands: list[dict], lo_key: str = "min", hi_key: str = "max") -> Optional[float]:
    for band in bands:
        lo, hi = band.get(lo_key), band.get(hi_key)
        if lo is not None and value < lo:
            continue
        if hi is not None and value >= hi:
            continue
        return band["points"]
    return None


# --------------------------------------------------------------------------
# Account Fit — PRD 8.2
# --------------------------------------------------------------------------

@dataclass
class AccountFitInputs:
    certification_tier: Optional[str] = None  # master_elite | certified_plus | certified | other_verified
    distinctions: Optional[list[str]] = None  # presidents_club, other_distinction (repeatable)
    rating: Optional[float] = None
    review_count: Optional[int] = None
    verified_services: Optional[list[str]] = None  # keys from config.product_service_alignment.services
    business_scale_signals: Optional[list[str]] = None  # keys from config.business_scale.signals
    distance_miles: Optional[float] = None
    business_start_year: Optional[int] = None
    as_of_year: Optional[int] = None  # override for deterministic tests; defaults to current year


def score_account_fit(inputs: AccountFitInputs, config: dict) -> ScoreResult:
    cfg = config["account_fit"]
    subs: list[Subcomponent] = []

    cert_cfg = cfg["certification_tier"]
    cert_points = cert_cfg["points"].get(inputs.certification_tier) if inputs.certification_tier else None
    subs.append(Subcomponent("certification_tier", cert_points, cert_cfg["max_points"]))

    dist_cfg = cfg["distinctions"]
    distinctions = inputs.distinctions if inputs.distinctions is not None else []
    dist_points = 0
    for d in distinctions:
        dist_points += dist_cfg["presidents_club"] if d == "presidents_club" else dist_cfg["other_distinction"]
    dist_points = min(dist_points, dist_cfg["max_points"])
    subs.append(Subcomponent("distinctions", dist_points, dist_cfg["max_points"]))

    rating_cfg = cfg["rating"]
    rating_points = _band_by_value(inputs.rating, rating_cfg["bands"]) if inputs.rating is not None else None
    subs.append(Subcomponent("rating", rating_points, rating_cfg["max_points"]))

    review_cfg = cfg["review_volume"]
    review_points = (
        _band_by_value(inputs.review_count, review_cfg["bands"]) if inputs.review_count is not None else None
    )
    subs.append(Subcomponent("review_volume", review_points, review_cfg["max_points"]))

    align_cfg = cfg["product_service_alignment"]
    if inputs.verified_services is not None:
        align_points = min(
            sum(align_cfg["services"].get(s, 0) for s in inputs.verified_services),
            align_cfg["max_points"],
        )
    else:
        align_points = None
    subs.append(Subcomponent("product_service_alignment", align_points, align_cfg["max_points"]))

    scale_cfg = cfg["business_scale"]
    if inputs.business_scale_signals is not None:
        scale_points = min(
            sum(scale_cfg["signals"].get(s, 0) for s in inputs.business_scale_signals),
            scale_cfg["max_points"],
        )
    else:
        scale_points = None
    subs.append(Subcomponent("business_scale", scale_points, scale_cfg["max_points"]))

    territory_cfg = cfg["territory_fit"]
    territory_points = (
        _band_by_value(inputs.distance_miles, territory_cfg["bands"]) if inputs.distance_miles is not None else None
    )
    subs.append(Subcomponent("territory_fit", territory_points, territory_cfg["max_points"]))

    years_cfg = cfg["years_in_business"]
    if inputs.business_start_year is not None:
        as_of_year = inputs.as_of_year or datetime.now(timezone.utc).year
        years = as_of_year - inputs.business_start_year
        years_points = _band_by_value(years, years_cfg["bands"])
    else:
        years_points = None
    subs.append(Subcomponent("years_in_business", years_points, years_cfg["max_points"]))

    return _combine("account_fit", cfg["formula_version"], subs)


# --------------------------------------------------------------------------
# Opportunity — PRD 8.3
# --------------------------------------------------------------------------

@dataclass
class OpportunityInputs:
    research_available: bool = False  # research status == completed
    recent_project_count: Optional[int] = None  # verified projects/permits in last 18mo
    only_older_activity: bool = False  # activity exists but all older than 18mo
    hiring_expansion_signals: Optional[list[str]] = None
    most_recent_activity_days: Optional[int] = None  # None when no activity found at all
    product_demand_signals: Optional[list[str]] = None
    decision_maker_tier: Optional[str] = None  # key_contact | other_management_contact | none_verified
    contactability_signals: Optional[list[str]] = None


def score_opportunity(inputs: OpportunityInputs, config: dict) -> ScoreResult:
    cfg = config["opportunity"]
    subs: list[Subcomponent] = []
    avail = inputs.research_available

    proj_cfg = cfg["recent_project_activity"]
    if not avail:
        proj_points = None
    elif inputs.recent_project_count and inputs.recent_project_count >= 5:
        proj_points = 30
    elif inputs.recent_project_count and inputs.recent_project_count >= 3:
        proj_points = 24
    elif inputs.recent_project_count and inputs.recent_project_count >= 1:
        proj_points = 15
    elif inputs.only_older_activity:
        proj_points = 5
    else:
        proj_points = 0
    subs.append(Subcomponent("recent_project_activity", proj_points, proj_cfg["max_points"]))

    hiring_cfg = cfg["hiring_or_expansion"]
    if not avail:
        hiring_points = None
    else:
        signals = inputs.hiring_expansion_signals or []
        hiring_points = min(sum(hiring_cfg["signals"].get(s, 0) for s in signals), hiring_cfg["max_points"])
    subs.append(Subcomponent("hiring_or_expansion", hiring_points, hiring_cfg["max_points"]))

    recency_cfg = cfg["recent_public_activity"]
    if not avail:
        recency_points = None
    elif inputs.most_recent_activity_days is None:
        recency_points = 0
    else:
        recency_points = _band_by_value_max_days(inputs.most_recent_activity_days, recency_cfg["bands"])
    subs.append(Subcomponent("recent_public_activity", recency_points, recency_cfg["max_points"]))

    demand_cfg = cfg["product_demand_trigger"]
    if not avail:
        demand_points = None
    else:
        signals = inputs.product_demand_signals or []
        demand_points = min(sum(demand_cfg["signals"].get(s, 0) for s in signals), demand_cfg["max_points"])
    subs.append(Subcomponent("product_demand_trigger", demand_points, demand_cfg["max_points"]))

    dm_cfg = cfg["verified_decision_maker"]
    if not avail:
        dm_points = None
    else:
        dm_points = dm_cfg["points"].get(inputs.decision_maker_tier, 0)
    subs.append(Subcomponent("verified_decision_maker", dm_points, dm_cfg["max_points"]))

    contact_cfg = cfg["contactability"]
    if not avail:
        contact_points = None
    else:
        signals = inputs.contactability_signals or []
        contact_points = min(sum(contact_cfg["signals"].get(s, 0) for s in signals), contact_cfg["max_points"])
    subs.append(Subcomponent("contactability", contact_points, contact_cfg["max_points"]))

    return _combine("opportunity", cfg["formula_version"], subs)


def _band_by_value_max_days(days: int, bands: list[dict]) -> float:
    for band in bands:
        if band["max_days"] is None or days <= band["max_days"]:
            return band["points"]
    return 0


# --------------------------------------------------------------------------
# Lead Priority — PRD 8.4
# --------------------------------------------------------------------------

def score_lead_priority(account_fit: ScoreResult, opportunity: ScoreResult, config: dict) -> ScoreResult:
    cfg = config["lead_priority"]
    af_weight = cfg["account_fit_weight"]
    opp_weight = cfg["opportunity_weight"]

    af_has_data = account_fit.coverage > 0
    opp_has_data = opportunity.coverage > 0

    if af_has_data and opp_has_data:
        total = round(account_fit.total * af_weight + opportunity.total * opp_weight, 2)
    elif af_has_data:
        total = round(account_fit.total, 2)
    elif opp_has_data:
        total = round(opportunity.total, 2)
    else:
        total = 0.0

    combined_max = 100 * af_weight + 100 * opp_weight
    earned_coverage_max = (
        (100 * af_weight if af_has_data else 0) + (100 * opp_weight if opp_has_data else 0)
    )
    weighted_af_coverage = account_fit.coverage * af_weight
    weighted_opp_coverage = opportunity.coverage * opp_weight
    coverage = round((weighted_af_coverage + weighted_opp_coverage) / combined_max * 100, 2)

    breakdown = {
        "account_fit": {"total": account_fit.total, "coverage": account_fit.coverage, "weight": af_weight},
        "opportunity": {"total": opportunity.total, "coverage": opportunity.coverage, "weight": opp_weight},
    }
    return ScoreResult(
        score_type="lead_priority",
        total=total,
        coverage=coverage,
        breakdown=breakdown,
        formula_version=cfg["formula_version"],
    )


def is_provisional(coverage: float, config: dict) -> bool:
    return coverage < config["lead_priority"]["provisional_coverage_threshold"]
