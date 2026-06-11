"""Our pipeline: `ResearchReport` -> `GradableReport` (spec §2).

A direct, lossless field map — no model calls. The claim ledger keeps its
verdict/confidence (our system *did* verify in-loop), sources and the rendered
markdown carry over verbatim, and the report metadata is flattened to a dict so
the scorers see ``overall_confidence`` / ``coverage`` / ``instruction_adherence``.
Constraints come from the query plan / eval item and are passed in by the
harness (default empty).
"""
from __future__ import annotations

from typing import Optional

from dra.schemas import ResearchReport

from dra.eval.pipeline.contracts import GradableClaim, GradableReport

__all__ = ["to_gradable"]


def to_gradable(
    report: ResearchReport, *, constraints: Optional[dict] = None
) -> GradableReport:
    """Map our `ResearchReport` to the system-agnostic `GradableReport`."""
    claims = [
        GradableClaim(
            id=c.id,
            text=c.text,
            citations=list(c.citations),
            verdict=c.verdict,
            confidence=c.confidence,
        )
        for c in report.claims
    ]
    return GradableReport(
        query=report.query,
        narrative_markdown=report.report_markdown,
        claims=claims,
        sources=list(report.sources),
        constraints=constraints or {},
        metadata=report.metadata.model_dump(),
    )
