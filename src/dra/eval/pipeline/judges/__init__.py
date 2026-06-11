"""Layer-2 judges (Phase 2).

The blind judge panel (relevance/quality + fuzzy formatting), the rubric prompt
builders, and the INDEPENDENT grounding judge. Every model is injected (fakes in
tests; panel-family models live). Nothing here is imported by the live loop.

The grounding judge here is deliberately distinct from the pipeline's in-loop
verifier (`dra.verify`) — re-using the verifier to score grounding would measure
its self-consistency, not whether claims are grounded (spec §4).
"""
from __future__ import annotations

from dra.eval.pipeline.judges.grounding_judge import LLMGroundingJudge
from dra.eval.pipeline.judges.panel import JudgePanel
from dra.eval.pipeline.judges.rubrics import (
    fuzzy_formatting_rubric,
    quality_rubric,
    relevance_rubric,
)

__all__ = [
    "JudgePanel",
    "LLMGroundingJudge",
    "relevance_rubric",
    "quality_rubric",
    "fuzzy_formatting_rubric",
]
