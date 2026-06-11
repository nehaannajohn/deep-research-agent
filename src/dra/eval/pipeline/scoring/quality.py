"""Quality scorer — a thin wrapper binding the quality rubric to a panel.

The panel is *injected* (no import of a concrete panel here). The wrapper only
builds the rubric prompt and delegates aggregation/adjudication to the panel.
"""
from __future__ import annotations

from dra.eval.pipeline.contracts import GradableReport
from dra.eval.pipeline.judges.rubrics import quality_rubric


def score_quality(report: GradableReport, query: str, panel, *, seed: int) -> dict:
    """Build the quality rubric and return the panel's aggregate dict."""
    prompt = quality_rubric(report, query)
    return panel.score(prompt, seed=seed)
