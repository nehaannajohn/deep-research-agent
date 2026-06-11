"""Layer-2 statistics toolkit (Phase 3).

Judge reliability (Cohen's κ, human-validation accounting) and significance
(paired-t, McNemar, Holm) over closed-form, pure inputs (spec §7). p-values use
`scipy.stats`; Holm is a pure step-down implementation. No network.
"""
from __future__ import annotations

from dra.eval.pipeline.stats.reliability import cohen_kappa, human_validation_summary
from dra.eval.pipeline.stats.significance import (
    holm,
    mcnemar,
    paired_t,
    unit_of_analysis,
)

__all__ = [
    "cohen_kappa",
    "human_validation_summary",
    "paired_t",
    "mcnemar",
    "holm",
    "unit_of_analysis",
]
