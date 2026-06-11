"""System adapters — normalize each system under test to a `GradableReport` (Phase 3).

`dra.to_gradable` is a direct field map from our `ResearchReport` (claim ledger,
sources, narrative, metadata, plan constraints). `PerplexityAdapter` /
`OpenAIAdapter` take a baseline's free-prose response, decompose it to atomic
claims via the shared decomposer, and recover citations via an injected matcher —
leaving `verdict`/`confidence` as ``None`` for the downstream independent
grounding judge (spec §2). All model dependencies are injected; no network.
"""
from __future__ import annotations

from dra.eval.pipeline.adapters.dra import to_gradable
from dra.eval.pipeline.adapters.openai import OpenAIAdapter
from dra.eval.pipeline.adapters.perplexity import PerplexityAdapter

__all__ = ["to_gradable", "PerplexityAdapter", "OpenAIAdapter"]
