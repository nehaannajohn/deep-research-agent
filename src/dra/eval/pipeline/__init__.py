"""Layer-2 pipeline-evaluation harness (offline).

Scores a finished `ResearchReport` (or any black-box report normalized to the
system-agnostic `GradableReport`) end-to-end: relevance, grounding, quality,
formatting correctness, task accuracy, and system calibration.

INVARIANT: nothing in this subpackage is imported by the live loop
(`dra.loop`). The harness is offline; only the verifier's confidence drives
retrieval online. The dependency is strictly one-directional
(`dra.eval.pipeline` -> `dra`, never the reverse).
"""
from __future__ import annotations
