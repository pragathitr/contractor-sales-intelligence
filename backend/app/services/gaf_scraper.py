"""Collects and parses GAF listing/profile information. No research, scoring,
insight generation, or database policy decisions happen here.

Headless Chromium is blocked by GAF's Akamai bot protection (verified against
both curl and stealth-patched headless Playwright) — this must run with
headless=False, which needs a real display. Documented limitation, not
solvable with fingerprint spoofing alone.
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Iterator, Optional

from playwright.sync_api import Page, sync_playwright

GAF_BASE_URL = "https://www.gaf.com/en-us/roofing-contractors"
LOCATOR_URL = GAF_BASE_URL + "/{contractor_type}?distance={distance}&postalCode={zip_code}&countryCode=us"

# GAF splits contractors into two entirely separate directories (residential
# vs commercial) rather than one page with a type filter — each needs its own
# crawl. P0 only ingests residential (PRD 6.1 default search).
RESIDENTIAL = "residential"
COMMERCIAL = "commercial"

RESULTS_SELECTOR = "ul.contractor-listing__results"
CARD_SELECTOR = f"{RESULTS_SELECTOR} article"
NEXT_BUTTON_SELECTOR = "button.pagination__next"

CITY_DISTANCE_RE = re.compile(r"^(?P<city>.+),\s*(?P<state>[A-Z]{2}) - (?P<distance>[\d.]+) mi$")
PHONE_RE = re.compile(r"Phone Number:\s*([\d()\-\s]+)")

CERT_TITLE_TO_TIER = {
    "master elite": "master_elite",
    "certified plus": "certified_plus",
    "certified": "certified",
}


@dataclass
class ListingRecord:
    gaf_contractor_id: Optional[str]
    name: Optional[str]
    contractor_type: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    city: Optional[str]
    state: Optional[str]
    distance_miles: Optional[float]
    phone: Optional[str]
    profile_url: Optional[str]


def extract_card(card) -> Optional[ListingRecord]:
    """Returns None for non-contractor placeholder cards (GAF pads result
    pages with empty <article> elements that carry no data-layer payload)."""
    data_layer = card.evaluate("el => el.querySelector('a[data-layer]')?.getAttribute('data-layer')")
    if not data_layer:
        return None
    attrs = json.loads(data_layer)[0]["event_attributes"]

    text = card.inner_text()
    city_match = CITY_DISTANCE_RE.search(next((line for line in text.splitlines() if " mi" in line), ""))
    phone_match = PHONE_RE.search(text)
    profile_url = card.evaluate("el => el.querySelector('a')?.href")

    return ListingRecord(
        gaf_contractor_id=attrs.get("contractor_id"),
        name=attrs.get("contractor_name"),
        contractor_type=attrs.get("contractor_type"),
        rating=float(attrs["contractor_rating"]) if attrs.get("contractor_rating") not in (None, "") else None,
        review_count=int(attrs["contractor_reviews_count"]) if attrs.get("contractor_reviews_count") not in (None, "") else None,
        city=city_match.group("city") if city_match else None,
        state=city_match.group("state") if city_match else None,
        distance_miles=float(city_match.group("distance")) if city_match else None,
        phone=phone_match.group(1).strip() if phone_match else None,
        profile_url=profile_url,
    )


def _wait_for_cards(page: Page, timeout_seconds: float = 10) -> None:
    """After a pagination click, the results list briefly re-renders
    client-side and goes empty before repopulating — poll past that flicker
    instead of trusting networkidle alone."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if page.locator(CARD_SELECTOR).count() > 0:
            return
        time.sleep(0.3)


def scrape_listings(page: Page, zip_code: str, distance_miles: int, contractor_type: str = RESIDENTIAL) -> Iterator[list[ListingRecord]]:
    """Yields one list of contractor records per results page."""
    url = LOCATOR_URL.format(contractor_type=contractor_type, distance=distance_miles, zip_code=zip_code)
    page.goto(url, wait_until="load", timeout=60000)
    page.wait_for_selector(RESULTS_SELECTOR, timeout=15000)

    while True:
        _wait_for_cards(page)
        cards = page.locator(CARD_SELECTOR)
        records = [extract_card(cards.nth(i)) for i in range(cards.count())]
        yield [r for r in records if r is not None]

        next_button = page.locator(NEXT_BUTTON_SELECTOR)
        if next_button.count() == 0 or not next_button.is_enabled():
            break
        # force=True: a sticky header and a floating "document cart" widget
        # sit on top of this button depending on scroll position — it's
        # genuinely visible and clickable, just physically overlapped.
        next_button.click(force=True)
        page.wait_for_load_state("networkidle")


def scrape_profile(page: Page, profile_url: str) -> dict:
    """Fetches profile-page fields not present on the listing card:
    certification tier, distinctions, about text, website, external review
    link, and business start year (when GAF exposes it)."""
    page.goto(profile_url, wait_until="load", timeout=60000)
    page.wait_for_timeout(1000)

    cert_titles = page.locator(".certifications-content-item__title").all_inner_texts()
    certification_tier = None
    distinctions: list[str] = []
    for title in cert_titles:
        lowered = title.lower()
        matched_tier = next((tier for key, tier in CERT_TITLE_TO_TIER.items() if key in lowered), None)
        if matched_tier and (certification_tier is None or _tier_rank(matched_tier) > _tier_rank(certification_tier)):
            certification_tier = matched_tier
        if "president" in lowered and "presidents_club" not in distinctions:
            distinctions.append("presidents_club")
        elif "award" in lowered and matched_tier is None and "other_distinction" not in distinctions:
            distinctions.append("other_distinction")

    about_locator = page.locator(".about-us-block__description")
    about_text = about_locator.first.inner_text().strip() if about_locator.count() > 0 else None

    website_url = None
    website_link = page.locator("a:has-text('Visit Website')")
    if website_link.count() > 0:
        website_url = website_link.first.get_attribute("href")

    return {
        "certification_tier": certification_tier,
        "distinctions": distinctions,
        "about_text": about_text,
        "website_url": website_url,
        **extract_address(page),
    }


def extract_address(page: Page) -> dict:
    """GAF embeds a schema.org LocalBusiness JSON-LD block on every profile
    page with a structured street address — cheaper and more reliable than
    parsing the visible <address> element's free text."""
    ld_json = page.locator("script[type='application/ld+json']")
    for i in range(ld_json.count()):
        try:
            data = json.loads(ld_json.nth(i).inner_text())
        except (ValueError, TypeError):
            continue
        address = data.get("address") if isinstance(data, dict) else None
        if isinstance(address, dict) and address.get("streetAddress"):
            return {
                "address": address.get("streetAddress"),
                "zip_code": address.get("Postalcode") or address.get("postalCode"),
            }
    return {"address": None, "zip_code": None}


def _tier_rank(tier: str) -> int:
    return {"other_verified": 0, "certified": 1, "certified_plus": 2, "master_elite": 3}.get(tier, -1)


def run_ingestion(zip_code: str, distance_miles: int, fetch_profiles: bool = True) -> list[dict]:
    """Full residential listing + profile scrape for one search. Requires a
    real display (see module docstring) — not suitable for a headless server."""
    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        for batch in scrape_listings(page, zip_code, distance_miles, RESIDENTIAL):
            for record in batch:
                merged = record.__dict__.copy()
                if fetch_profiles and record.profile_url:
                    try:
                        merged.update(scrape_profile(page, record.profile_url))
                    except Exception as exc:  # noqa: BLE001 - one contractor failure must not fail the batch
                        merged["profile_scrape_error"] = str(exc)
                results.append(merged)
        browser.close()
    return results
