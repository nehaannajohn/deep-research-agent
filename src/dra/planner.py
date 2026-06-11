"""Query -> a concrete research brief: sub-questions + an extracted constraint spec."""
from __future__ import annotations

from pydantic import BaseModel, Field

_PLAN_PROMPT = """You are planning research for a user query. Decompose ONLY when it helps.

Rules:
- Split the query into multiple sub-questions ONLY when its parts would retrieve
  genuinely DISTINCT evidence (different topics, sources, or claims).
- If the query is already atomic or specific, return it UNCHANGED as a single
  sub-question. A single sub-question is a valid and common answer — do not pad.
- This mirrors atomic claim extraction: prefer the fewest sub-questions that fully
  cover the query, each likely to surface different evidence.
- Sub-questions cover ONLY the research CONTENT of the query. IGNORE presentation / format /
  length / modality instructions (e.g. "include a diagram", "add a visual", "as a table",
  "in 500 words") when forming sub-questions — capture those in `constraints` (set
  wants_visual / format accordingly) instead. The sub-questions MUST be IDENTICAL whether or
  not such formatting instructions are present in the query.

Return ONLY JSON of the form:
{{"subquestions": ["one or more specific, answerable sub-questions"],
  "constraints": {{"wants_visual": true/false, "format": "table|prose|null", "focus": ["optional topics"]}}}}

Query: {query}"""


class Plan(BaseModel):
    subquestions: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)


def plan(query: str, llm) -> Plan:
    """`llm` is a BedrockChat-like object with `complete_json`."""
    data = llm.complete_json(_PLAN_PROMPT.format(query=query))
    subqs = [s.strip() for s in data.get("subquestions", []) if isinstance(s, str) and s.strip()]
    return Plan(subquestions=subqs, constraints=data.get("constraints") or {})
