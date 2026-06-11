"""Query -> a research brief: a 2-step split so research content and presentation constraints
are separated at decomposition time.
  1) split:     query -> {core_query (presentation/format/modality instructions stripped), constraints}
  2) decompose: core_query -> sub-questions (so retrieval is invariant to format instructions)
The constraints flow downstream to report composition (diagram / table); the sub-questions drive retrieval."""
from __future__ import annotations

from pydantic import BaseModel, Field

_SPLIT_PROMPT = """Separate a user query into its RESEARCH CONTENT and its PRESENTATION CONSTRAINTS.
- "core_query": the research question(s) ONLY. Strip out EVERY presentation / format / length /
  modality instruction (e.g. "include a diagram", "add a visual", "as a table", "in 500 words",
  "with charts"). Keep the research wording otherwise unchanged.
- "constraints": reflect the stripped instructions.

Return ONLY JSON:
{{"core_query": "the research question(s) with presentation instructions removed",
  "constraints": {{"wants_visual": true/false, "format": "table|prose|null", "focus": ["optional topics"]}}}}

Query: {query}"""

_DECOMPOSE_PROMPT = """You are decomposing a research query into sub-questions. Decompose ONLY when it helps.

Rules:
- Split into multiple sub-questions ONLY when its parts would retrieve genuinely DISTINCT evidence
  (different topics, sources, or claims).
- If the query is already atomic or specific, return it UNCHANGED as a single sub-question. A single
  sub-question is a valid and common answer — do not pad.
- Prefer the fewest sub-questions that fully cover the query, each likely to surface different evidence.

Return ONLY JSON: {{"subquestions": ["one or more specific, answerable sub-questions"]}}

Query: {query}"""


class Plan(BaseModel):
    core_query: str = ""
    subquestions: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)


def plan(query: str, llm) -> Plan:
    """`llm` is a BedrockChat-like object with `complete_json`. Two calls: split then decompose."""
    split = llm.complete_json(_SPLIT_PROMPT.format(query=query))
    core = (split.get("core_query") if isinstance(split, dict) else None) or query
    core = core.strip() or query
    constraints = (split.get("constraints") if isinstance(split, dict) else None) or {}
    dec = llm.complete_json(_DECOMPOSE_PROMPT.format(query=core))
    subqs = [s.strip() for s in (dec.get("subquestions", []) if isinstance(dec, dict) else [])
             if isinstance(s, str) and s.strip()]
    if not subqs:
        subqs = [core]
    return Plan(core_query=core, subquestions=subqs, constraints=constraints)
