"""Core data contracts shared across the pipeline.

A `ResearchReport` separates claims from evidence and attaches a (recalibrated)
confidence per claim — the project's hard requirement made concrete.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

VerdictLabel = Literal["unverified", "supported", "refuted", "insufficient", "contested"]


class Passage(BaseModel):
    """A verbatim retrieved evidence span with provenance. Not model-generated."""

    source_id: str
    text: str
    url: str = ""
    title: str = ""
    score: float = 0.0


class Citation(BaseModel):
    """A pointer from a claim to the passage span it rests on."""

    source_id: str
    span: str


class Claim(BaseModel):
    """An atomic assertion plus its verification state."""

    id: str
    text: str
    section: str
    citations: list[Citation] = Field(default_factory=list)
    verdict: VerdictLabel = "unverified"
    confidence: Optional[float] = None
    iterations: int = 0


class ReportMetadata(BaseModel):
    overall_confidence: Optional[float] = None
    confidence_breakdown: dict = Field(default_factory=dict)
    coverage: Optional[float] = None
    instruction_adherence: dict = Field(default_factory=dict)
    descriptive_summary: str = ""
    disclaimers: list[str] = Field(default_factory=list)
    cost: dict = Field(default_factory=dict)
    run_id: str = ""
    seed: Optional[int] = None


class ResearchReport(BaseModel):
    query: str
    resolved_brief: str = ""
    report_markdown: str = ""
    claims: list[Claim] = Field(default_factory=list)
    sources: list[Passage] = Field(default_factory=list)
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
