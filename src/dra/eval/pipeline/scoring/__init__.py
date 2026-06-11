"""Layer-2 pipeline-eval scoring primitives (Phase 1).

Pure scoring functions with all model dependencies injected (fakes in tests;
real models wired later at orchestration). No network here.
"""
from __future__ import annotations

from dra.eval.pipeline.scoring.calibration import system_ece
from dra.eval.pipeline.scoring.formatting import score_formatting
from dra.eval.pipeline.scoring.grounding import GroundingJudge, score_grounding
from dra.eval.pipeline.scoring.similarity import score_similarity
from dra.eval.pipeline.scoring.task_accuracy import (
    EquivalenceJudge,
    score_task_accuracy,
)

__all__ = [
    "score_grounding",
    "GroundingJudge",
    "score_formatting",
    "score_similarity",
    "score_task_accuracy",
    "EquivalenceJudge",
    "system_ece",
]
