"""Query -> a concrete research brief: sub-questions + an extracted constraint spec."""
from __future__ import annotations

from pydantic import BaseModel, Field

_PLAN_PROMPT = """You are planning research for a user query.
Return ONLY JSON of the form:
{{"subquestions": ["3-6 specific, answerable sub-questions"],
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
