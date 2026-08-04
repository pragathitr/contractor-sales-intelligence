import copy

import pytest

from app.services.scoring import (
    AccountFitInputs,
    OpportunityInputs,
    is_provisional,
    score_account_fit,
    score_lead_priority,
    score_opportunity,
)

BASE_CONFIG = {
    "account_fit": {
        "formula_version": "account-fit-v1",
        "certification_tier": {
            "max_points": 20,
            "points": {"master_elite": 20, "certified_plus": 14, "certified": 8, "other_verified": 5},
        },
        "distinctions": {"max_points": 5, "presidents_club": 5, "other_distinction": 2},
        "rating": {
            "max_points": 10,
            "bands": [
                {"min": 4.80, "max": 5.01, "points": 10},
                {"min": 4.50, "max": 4.80, "points": 8},
                {"min": 4.00, "max": 4.50, "points": 5},
                {"min": 0.00, "max": 4.00, "points": 2},
            ],
        },
        "review_volume": {
            "max_points": 10,
            "bands": [
                {"min": 100, "max": None, "points": 10},
                {"min": 50, "max": 100, "points": 8},
                {"min": 20, "max": 50, "points": 6},
                {"min": 5, "max": 20, "points": 3},
                {"min": 1, "max": 5, "points": 1},
                {"min": 0, "max": 1, "points": 0},
            ],
        },
        "product_service_alignment": {
            "max_points": 20,
            "services": {
                "residential_replacement_or_shingles": 6,
                "repair_or_maintenance": 3,
                "ventilation_or_accessories": 3,
                "solar_roofing": 3,
                "metal_roofing": 3,
                "commercial_roofing_or_coatings": 2,
            },
        },
        "business_scale": {
            "max_points": 15,
            "signals": {
                "two_plus_locations": 5,
                "multiple_counties_or_boroughs": 3,
                "multiple_crews_or_capacity": 4,
                "five_plus_recent_projects": 3,
            },
        },
        "territory_fit": {
            "max_points": 10,
            "bands": [
                {"min": 0, "max": 5, "points": 10},
                {"min": 5, "max": 10, "points": 8},
                {"min": 10, "max": 15, "points": 6},
                {"min": 15, "max": 20, "points": 4},
                {"min": 20, "max": 25, "points": 2},
                {"min": 25, "max": None, "points": 0},
            ],
        },
        "years_in_business": {
            "max_points": 10,
            "bands": [
                {"min": 15, "max": None, "points": 10},
                {"min": 8, "max": 15, "points": 8},
                {"min": 3, "max": 8, "points": 5},
                {"min": 0, "max": 3, "points": 3},
            ],
        },
    },
    "opportunity": {
        "formula_version": "opportunity-v1",
        "recent_project_activity": {"max_points": 30},
        "hiring_or_expansion": {
            "max_points": 20,
            "signals": {
                "new_location_or_territory": 8,
                "relevant_active_hiring": 6,
                "new_service_or_category": 4,
                "additional_crews_or_capacity": 2,
            },
        },
        "recent_public_activity": {
            "max_points": 15,
            "bands": [
                {"max_days": 90, "points": 15},
                {"max_days": 180, "points": 10},
                {"max_days": 365, "points": 6},
                {"max_days": 540, "points": 3},
                {"max_days": None, "points": 0},
            ],
        },
        "product_demand_trigger": {
            "max_points": 15,
            "signals": {
                "recent_project_tied_to_product": 6,
                "newly_added_service": 5,
                "expansion_implying_material_demand": 4,
            },
        },
        "verified_decision_maker": {
            "max_points": 10,
            "points": {"key_contact": 10, "other_management_contact": 6, "none_verified": 0},
        },
        "contactability": {
            "max_points": 10,
            "signals": {"direct_business_email": 5, "direct_business_phone": 3, "generic_contact": 2},
        },
    },
    "lead_priority": {
        "formula_version": "lead-priority-v1",
        "account_fit_weight": 0.65,
        "opportunity_weight": 0.35,
        "provisional_coverage_threshold": 60,
    },
}


def full_account_fit_inputs(**overrides) -> AccountFitInputs:
    defaults = dict(
        certification_tier="master_elite",
        distinctions=["presidents_club"],
        rating=4.9,
        review_count=150,
        verified_services=["residential_replacement_or_shingles", "metal_roofing"],
        business_scale_signals=["multiple_counties_or_boroughs"],
        distance_miles=4,
        business_start_year=2000,
        as_of_year=2026,
    )
    defaults.update(overrides)
    return AccountFitInputs(**defaults)


# --------------------------------------------------------------------------
# Boundaries
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rating,expected_points",
    [(5.00, 10), (4.80, 10), (4.79, 8), (4.50, 8), (4.49, 5), (4.00, 5), (3.99, 2), (0.0, 2)],
)
def test_rating_band_boundaries(rating, expected_points):
    result = score_account_fit(full_account_fit_inputs(rating=rating), BASE_CONFIG)
    assert result.breakdown["rating"]["points"] == expected_points


@pytest.mark.parametrize(
    "review_count,expected_points",
    [(100, 10), (99, 8), (50, 8), (49, 6), (20, 6), (19, 3), (5, 3), (4, 1), (1, 1), (0, 0)],
)
def test_review_volume_band_boundaries(review_count, expected_points):
    result = score_account_fit(full_account_fit_inputs(review_count=review_count), BASE_CONFIG)
    assert result.breakdown["review_volume"]["points"] == expected_points


@pytest.mark.parametrize(
    "distance,expected_points",
    [(0, 10), (4.99, 10), (5, 8), (9.99, 8), (10, 6), (24.99, 2), (25, 0), (40, 0)],
)
def test_territory_fit_band_boundaries(distance, expected_points):
    result = score_account_fit(full_account_fit_inputs(distance_miles=distance), BASE_CONFIG)
    assert result.breakdown["territory_fit"]["points"] == expected_points


def test_certification_tier_points():
    for tier, expected in [("master_elite", 20), ("certified_plus", 14), ("certified", 8), ("other_verified", 5)]:
        result = score_account_fit(full_account_fit_inputs(certification_tier=tier), BASE_CONFIG)
        assert result.breakdown["certification_tier"]["points"] == expected


def test_distinctions_cap_at_max():
    result = score_account_fit(
        full_account_fit_inputs(distinctions=["presidents_club", "other_distinction", "other_distinction", "other_distinction"]),
        BASE_CONFIG,
    )
    assert result.breakdown["distinctions"]["points"] == 5  # 5 + 2*3 = 11, capped at 5


def test_product_alignment_caps_at_max_points():
    result = score_account_fit(
        full_account_fit_inputs(
            verified_services=[
                "residential_replacement_or_shingles",
                "metal_roofing",
                "commercial_roofing_or_coatings",
                "solar_roofing",
                "ventilation_or_accessories",
            ]
        ),
        BASE_CONFIG,
    )
    # 6+3+2+3+3 = 17, under cap of 20 -> not clipped
    assert result.breakdown["product_service_alignment"]["points"] == 17


# --------------------------------------------------------------------------
# Missing-data normalization
# --------------------------------------------------------------------------

def test_missing_certification_is_unavailable_and_excluded_from_denominator():
    result = score_account_fit(full_account_fit_inputs(certification_tier=None), BASE_CONFIG)
    assert result.breakdown["certification_tier"]["available"] is False
    assert result.coverage < 100.0


def test_full_coverage_when_everything_available():
    result = score_account_fit(full_account_fit_inputs(), BASE_CONFIG)
    assert result.coverage == 100.0


def test_completed_search_found_nothing_is_available_zero_not_missing():
    result = score_account_fit(full_account_fit_inputs(verified_services=[], business_scale_signals=[]), BASE_CONFIG)
    assert result.breakdown["product_service_alignment"]["available"] is True
    assert result.breakdown["product_service_alignment"]["points"] == 0
    assert result.breakdown["business_scale"]["available"] is True
    assert result.breakdown["business_scale"]["points"] == 0


def test_all_missing_yields_only_distinctions_available_and_zero_total():
    # distinctions is the one subcomponent treated as always-available: an
    # empty list is a real "no distinctions" fact, not a missing signal.
    result = score_account_fit(
        AccountFitInputs(
            certification_tier=None,
            distinctions=None,
            rating=None,
            review_count=None,
            verified_services=None,
            business_scale_signals=None,
            distance_miles=None,
            business_start_year=None,
        ),
        BASE_CONFIG,
    )
    assert result.breakdown["distinctions"]["available"] is True
    assert all(
        not v["available"] for name, v in result.breakdown.items() if name != "distinctions"
    )
    assert result.total == 0.0


def test_opportunity_unavailable_when_research_did_not_run():
    result = score_opportunity(OpportunityInputs(research_available=False), BASE_CONFIG)
    assert result.coverage == 0.0
    assert all(not v["available"] for v in result.breakdown.values())


def test_opportunity_available_zero_when_research_completed_with_no_findings():
    result = score_opportunity(
        OpportunityInputs(
            research_available=True,
            recent_project_count=0,
            hiring_expansion_signals=[],
            most_recent_activity_days=None,
            product_demand_signals=[],
            decision_maker_tier="none_verified",
            contactability_signals=[],
        ),
        BASE_CONFIG,
    )
    assert result.coverage == 100.0
    assert result.total == 0.0


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def test_scoring_is_deterministic_across_repeated_calls():
    inputs = full_account_fit_inputs()
    results = [score_account_fit(inputs, BASE_CONFIG) for _ in range(5)]
    totals = {r.total for r in results}
    coverages = {r.coverage for r in results}
    assert len(totals) == 1
    assert len(coverages) == 1


def test_lead_priority_deterministic_and_versioned():
    af = score_account_fit(full_account_fit_inputs(), BASE_CONFIG)
    opp = score_opportunity(
        OpportunityInputs(research_available=True, recent_project_count=2, decision_maker_tier="key_contact"),
        BASE_CONFIG,
    )
    lp1 = score_lead_priority(af, opp, BASE_CONFIG)
    lp2 = score_lead_priority(af, opp, BASE_CONFIG)
    assert lp1.total == lp2.total
    assert lp1.formula_version == "lead-priority-v1"


# --------------------------------------------------------------------------
# Config sensitivity
# --------------------------------------------------------------------------

def test_different_configs_change_ranking_and_carry_own_formula_version():
    strict_config = copy.deepcopy(BASE_CONFIG)
    strict_config["account_fit"]["formula_version"] = "account-fit-v2-strict-cert"
    strict_config["account_fit"]["certification_tier"]["points"] = {
        "master_elite": 20,
        "certified_plus": 2,
        "certified": 1,
        "other_verified": 0,
    }

    contractor_a = full_account_fit_inputs(certification_tier="master_elite", rating=4.2, review_count=10)
    contractor_b = full_account_fit_inputs(certification_tier="certified_plus", rating=4.95, review_count=200)

    base_a = score_account_fit(contractor_a, BASE_CONFIG)
    base_b = score_account_fit(contractor_b, BASE_CONFIG)
    strict_a = score_account_fit(contractor_a, strict_config)
    strict_b = score_account_fit(contractor_b, strict_config)

    assert base_b.total > base_a.total  # under the base config, B ranks higher
    assert strict_a.total > strict_b.total  # under the strict config, A ranks higher because B's tier is downweighted

    assert base_a.formula_version == "account-fit-v1"
    assert strict_a.formula_version == "account-fit-v2-strict-cert"


def test_lead_priority_weight_change_shifts_result():
    af = score_account_fit(full_account_fit_inputs(rating=5.0, review_count=200), BASE_CONFIG)
    opp = score_opportunity(
        OpportunityInputs(research_available=True, recent_project_count=0, decision_maker_tier="none_verified"),
        BASE_CONFIG,
    )
    lp_base = score_lead_priority(af, opp, BASE_CONFIG)

    opp_heavy_config = copy.deepcopy(BASE_CONFIG)
    opp_heavy_config["lead_priority"]["formula_version"] = "lead-priority-v2-opportunity-heavy"
    opp_heavy_config["lead_priority"]["account_fit_weight"] = 0.2
    opp_heavy_config["lead_priority"]["opportunity_weight"] = 0.8
    lp_opp_heavy = score_lead_priority(af, opp, opp_heavy_config)

    assert lp_base.total != lp_opp_heavy.total
    assert lp_opp_heavy.formula_version == "lead-priority-v2-opportunity-heavy"


def test_is_provisional_uses_configured_threshold():
    assert is_provisional(59.9, BASE_CONFIG) is True
    assert is_provisional(60.0, BASE_CONFIG) is False
