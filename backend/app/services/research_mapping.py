"""Maps validated Perplexity research (free-text evidence) into the
category-key inputs scoring.py expects. Pure text classification — no
network/database calls — kept separate from scoring.py because it is about
interpreting research content, not computing scores from known inputs.
"""

from datetime import datetime, timezone

RECENT_WINDOW_DAYS = 18 * 30

SERVICE_KEYWORDS = {
    "metal_roofing": ["metal roof", "copper", "standing seam"],
    "commercial_roofing_or_coatings": ["commercial roofing", "industrial roofing", "epdm", "tpo", "coating"],
    "ventilation_or_accessories": ["ventilation"],
    "solar_roofing": ["solar"],
    "repair_or_maintenance": ["repair", "maintenance"],
}

SCALE_KEYWORDS = {
    "multiple_counties_or_boroughs": ["counties", "boroughs", "tri-state", "tri state", "multiple locations", "several locations"],
    "multiple_crews_or_capacity": ["crews", "multiple crews", "teams of"],
    "two_plus_locations": ["second location", "multiple offices", "two locations"],
    "five_plus_recent_projects": [],  # derived from recent_projects count, not keywords
}

HIRING_KEYWORDS = {
    "new_location_or_territory": ["new location", "new territory", "expanding into", "opened a new"],
    "relevant_active_hiring": ["hiring", "now hiring", "job opening", "we're hiring"],
    "new_service_or_category": ["now offering", "new service", "added service"],
    "additional_crews_or_capacity": ["additional crew", "expanded crew", "growing team"],
}

DEMAND_KEYWORDS = {
    "recent_project_tied_to_product": ["shingle", "roofing material", "product installation"],
    "newly_added_service": ["now offering", "new service"],
    "expansion_implying_material_demand": ["expansion", "growing demand", "increased volume"],
}


def _evidence_text(items: list[dict]) -> str:
    return " ".join((i.get("evidence") or "") for i in items).lower()


def map_verified_services(research: dict) -> list[str]:
    text = _evidence_text(research.get("services", []))
    matched = [key for key, kws in SERVICE_KEYWORDS.items() if any(kw in text for kw in kws)]
    return ["residential_replacement_or_shingles"] + matched


def map_business_scale_signals(research: dict) -> list[str]:
    text = _evidence_text(research.get("service_territories", []) + research.get("growth_signals", []))
    signals = [key for key, kws in SCALE_KEYWORDS.items() if kws and any(kw in text for kw in kws)]
    if len(research.get("recent_projects", [])) >= 5:
        signals.append("five_plus_recent_projects")
    return signals


def map_hiring_expansion_signals(research: dict) -> list[str]:
    text = _evidence_text(research.get("growth_signals", []))
    return [key for key, kws in HIRING_KEYWORDS.items() if any(kw in text for kw in kws)]


def map_product_demand_signals(research: dict) -> list[str]:
    text = _evidence_text(research.get("product_demand_signals", []))
    return [key for key, kws in DEMAND_KEYWORDS.items() if any(kw in text for kw in kws)]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Perplexity doesn't always include a timezone (e.g. date-only strings
    # like "2024-06-15") — treat naive values as UTC so they're comparable.
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def recent_project_count(research: dict) -> tuple[int, bool]:
    """Returns (count within 18mo, only_older_activity_found)."""
    now = datetime.now(timezone.utc)
    dated = [(_parse_date(p.get("published_at"))) for p in research.get("recent_projects", [])]
    dated = [d for d in dated if d is not None]
    recent = [d for d in dated if (now - d).days <= RECENT_WINDOW_DAYS]
    only_older = bool(dated) and not recent
    return len(recent), only_older


def most_recent_activity_days(research: dict) -> int | None:
    now = datetime.now(timezone.utc)
    dates = [_parse_date(p.get("published_at")) for p in research.get("recent_projects", [])]
    dates = [d for d in dates if d is not None]
    if not dates:
        return None
    return (now - max(dates)).days


def decision_maker_tier(research: dict) -> str:
    key_titles = ["owner", "president", "gm", "general manager", "operations", "production", "purchasing", "procurement"]
    for dm in research.get("decision_makers", []):
        title = (dm.get("title") or "").lower()
        if any(k in title for k in key_titles):
            return "key_contact"
    return "other_management_contact" if research.get("decision_makers") else "none_verified"


def contactability_signals(research: dict) -> list[str]:
    signals = []
    for dm in research.get("decision_makers", []):
        if dm.get("business_email"):
            signals.append("direct_business_email")
        if dm.get("business_phone"):
            signals.append("direct_business_phone")
    if research.get("public_contacts"):
        signals.append("generic_contact")
    return signals
