"""Perplexity research: source-backed public facts only. No scoring or
database policy decisions happen here — callers persist the ResearchFinding
row and decide status.
"""

import json
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.prompts import RESEARCH_PROMPT_TEMPLATE
from app.schemas import ResearchOutput

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

# Perplexity's first request against a new JSON schema can take 10-30s to
# prepare and may time out — use a generous client timeout (PRD/CLAUDE.md).
REQUEST_TIMEOUT_SECONDS = 60

RESEARCH_JSON_SCHEMA = ResearchOutput.model_json_schema()


class ResearchError(Exception):
    pass


def research_contractor(
    *,
    name: str,
    address: str | None,
    city: str | None,
    state: str | None,
    website_url: str | None,
    gaf_profile_url: str | None,
    settings: Settings,
) -> ResearchOutput:
    """Calls Perplexity with the exact PRD prompt and validates the response.
    Raises ResearchError on any failure — callers persist status="failed" and
    never fabricate fallback data.
    """
    if not settings.perplexity_api_key:
        raise ResearchError("PERPLEXITY_API_KEY is not configured")

    prompt = RESEARCH_PROMPT_TEMPLATE.format(
        name=name,
        address=address or "unknown",
        city=city or "unknown",
        state=state or "unknown",
        website_url=website_url or "unknown",
        gaf_profile_url=gaf_profile_url or "unknown",
    )

    payload = {
        "model": settings.perplexity_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": RESEARCH_JSON_SCHEMA},
        },
    }
    headers = {"Authorization": f"Bearer {settings.perplexity_api_key}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(PERPLEXITY_URL, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ResearchError(f"Perplexity request failed: {exc}") from exc

    try:
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        data.setdefault("researched_at", datetime.now(timezone.utc).isoformat())
        return ResearchOutput.model_validate(data)
    except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
        raise ResearchError(f"Invalid Perplexity response: {exc}") from exc
