"""Relevance scorer — a thin wrapper binding the relevance rubric to a panel.

The panel is *injected* (no import of a concrete panel here), so the live
blind panel and a fake panel both flow through unchanged. The wrapper only
builds the rubric prompt and delegates aggregation/adjudication to the panel.
"""
from __future__ import annotations

from dra.eval.pipeline.contracts import GradableReport
from dra.eval.pipeline.judges.rubrics import relevance_rubric


def score_relevance(report: GradableReport, query: str, panel, *, seed: int) -> dict:
    """Build the relevance rubric and return the panel's aggregate dict."""
    prompt = relevance_rubric(report, query)
    return panel.score(prompt, seed=seed)
