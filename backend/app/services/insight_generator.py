"""OpenAI insight generation. Transforms only scraped data, validated
research, deterministic scores, and known product categories into guidance.
No web research and no new facts are introduced here.
"""

import json
from datetime import datetime, timezone

from openai import OpenAI
from pydantic import ValidationError

from app.config import Settings
from app.prompts import INSIGHT_PROMPT_TEMPLATE
from app.schemas import InsightOutput

INSIGHT_JSON_SCHEMA = InsightOutput.model_json_schema()


class InsightError(Exception):
    pass


def generate_insight(
    *,
    contractor: dict,
    research: dict | None,
    score_breakdown: dict,
    product_categories: list[str],
    version: int,
    settings: Settings,
) -> InsightOutput:
    """Calls OpenAI with the exact PRD prompt plus supplied context and
    validates the response. Raises InsightError on any failure — callers
    persist status="failed" and never fabricate fallback data.
    """
    if not settings.openai_api_key:
        raise InsightError("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=settings.openai_api_key)
    context = {
        "contractor": contractor,
        "research": research,
        "score_breakdown": score_breakdown,
        "product_categories": product_categories,
    }

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": INSIGHT_PROMPT_TEMPLATE},
                {"role": "user", "content": json.dumps(context)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "insight_output", "schema": INSIGHT_JSON_SCHEMA},
            },
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data["version"] = version
        return InsightOutput.model_validate(data)
    except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
        raise InsightError(f"Invalid OpenAI response: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - one contractor failure must not fail the batch
        raise InsightError(f"OpenAI request failed: {exc}") from exc
