"""OpenAI baseline (stretch) -> `GradableReport` (spec §2).

Same shape and path as the Perplexity adapter: free-prose narrative + cited
sources -> shared decomposer -> atomic claims -> injected matcher for citations,
with ``verdict``/``confidence`` left ``None`` for the downstream independent
grounding judge. Reuses `_BaselineAdapter` so the two baselines stay identical
modulo the claim-id namespace; both dependencies injected, no network.
"""
from __future__ import annotations

from dra.eval.pipeline.adapters.perplexity import _BaselineAdapter

__all__ = ["OpenAIAdapter"]


class OpenAIAdapter(_BaselineAdapter):
    """OpenAI free-prose response -> `GradableReport` (stretch baseline)."""

    _prefix = "openai"
