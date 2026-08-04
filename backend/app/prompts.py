"""Exact prompt templates from PRD sections 7.3 and 9.2. Do not paraphrase."""

RESEARCH_PROMPT_TEMPLATE = """\
Research the roofing contractor below for a roofing-material distributor's
sales account-planning workflow.

Contractor:
- Name: {name}
- Address: {address}
- City/State: {city}, {state}
- Website: {website_url}
- GAF profile: {gaf_profile_url}

First confirm that every source refers to this exact contractor. Use the
address, location, website domain, and business description to avoid confusing
it with another company.

Research:
1. Verified decision-makers involved in ownership, operations, production,
   purchasing, or procurement.
2. Roofing services and roofing-system categories offered.
3. Geographic service territory and verified business locations.
4. Relevant projects, permits, portfolio updates, or announcements from the
   last 18 months.
5. Hiring, expansion, new-location, new-crew, or new-service signals.
6. Public business contact information.
7. Evidence indicating potential roofing-product demand.
8. Important risks, conflicting information, or missing information.

Rules:
- Return only facts supported by public sources.
- Do not infer revenue, employee count, pricing, purchasing volume, supplier
  relationships, or private information.
- Do not use or reproduce individual Google review content.
- Return null or an empty list when information cannot be verified.
- Include source URL, source title, supporting evidence, publication date when
  available, and confidence for every finding.
- Separate observed facts from interpretations.
- Return valid JSON matching the supplied schema.
"""

INSIGHT_PROMPT_TEMPLATE = """\
You are helping a roofing-material distributor prepare for sales outreach.

Using only the supplied contractor data, validated research findings, score
breakdown, and evidence, generate concise and practical account-planning
insights.

Rules:
- Do not introduce facts absent from the supplied data.
- Do not claim the contractor definitely needs a product.
- Use "potential product fit" and explain the supporting evidence.
- Clearly distinguish observed facts from inferences and suggested actions.
- If information is unavailable, say it requires verification.
- Do not infer revenue, purchasing volume, employee count, pricing, or supplier
  dissatisfaction.
- Do not use generic sales language.
- Recommend specific discovery questions that help the representative verify
  assumptions.
- Return valid JSON matching the supplied schema.
"""
