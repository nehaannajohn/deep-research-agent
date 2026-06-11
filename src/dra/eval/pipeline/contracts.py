"""Core data contracts for the Layer-2 pipeline-eval harness (spec §2–§3).

`GradableReport` / `GradableClaim` are the *system-agnostic* view every system
under test is normalized to, so the same scorers run on our `ResearchReport`
and a black-box baseline. `EvalItem` is the per-benchmark item the loaders
yield. `Passage` / `Citation` / `VerdictLabel` are reused verbatim from
`dra.schemas` — the harness never redefines the live contracts.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from dra.schemas import Citation, Passage, VerdictLabel

Tier = Literal["agentic", "attribution", "stress", "dra_bench"]


class GradableClaim(BaseModel):
    """An atomic claim normalized for scoring (spec §2).

    `verdict` / `confidence` are `None` for an unverified or black-box report —
    the harness assigns them downstream via the independent grounding judge.
    """

    id: str
    text: str
    citations: list[Citation] = Field(default_factory=list)
    verdict: Optional[VerdictLabel] = None
    confidence: Optional[float] = None


class GradableReport(BaseModel):
    """The system-agnostic report view the scorers consume (spec §2)."""

    query: str
    narrative_markdown: str = ""
    claims: list[GradableClaim] = Field(default_factory=list)
    sources: list[Passage] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class EvalItem(BaseModel):
    """One benchmark item, routed to `run_query` then to tier scorers (spec §3)."""

    id: str
    tier: Tier
    query: str
    constraints: dict = Field(default_factory=dict)
    gold_answer: Optional[str] = None
    gold_answer_aliases: list[str] = Field(default_factory=list)
    reference_claims: list[str] = Field(default_factory=list)
    seed_sources: list[str] = Field(default_factory=list)
    expected_behavior: Optional[str] = None
    label_corpus: Optional[str] = None
