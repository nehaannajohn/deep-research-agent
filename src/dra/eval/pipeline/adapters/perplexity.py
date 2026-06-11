"""Perplexity Sonar baseline -> `GradableReport` (spec §2, the black-box path).

A baseline returns free prose plus a list of cited URLs/sources — it does NOT
expose a claim ledger. So we:

  1. decompose the narrative to atomic claims via the **shared** decomposer
     (`scoring/decompose.decompose_report`), the same instrument used on our own
     reports, so the comparison is fair;
  2. recover each claim's cited passages by matching it against the baseline's
     returned sources via an **injected** ``matcher(claim_text, sources) ->
     list[Citation]`` (embedding/passage match live; a fake in tests).

``verdict`` / ``confidence`` are deliberately left ``None`` — they are assigned
downstream by the **independent grounding judge**, never the in-loop verifier
(spec §2/§4: audit the black box with our own instrument, honestly). Both
dependencies are injected; no network here.

``raw_response`` shape (provider-normalized upstream)::

    {"query": str, "narrative": str, "sources": list[Passage]}
"""
from __future__ import annotations

from typing import Callable

from dra.schemas import Citation, Passage

from dra.eval.pipeline.contracts import GradableClaim, GradableReport
from dra.eval.pipeline.scoring.decompose import decompose_report

__all__ = ["PerplexityAdapter"]

Decomposer = Callable[[str], list]
Matcher = Callable[[str, list], list]
_PREFIX = "perplexity"


class _BaselineAdapter:
    """Shared free-prose -> GradableReport path for the baseline brackets.

    Subclasses set ``_prefix`` (used to id-namespace the synthesized claims).
    """

    _prefix = "baseline"

    def __init__(self, decomposer: Decomposer, matcher: Matcher):
        self.decomposer = decomposer
        self.matcher = matcher

    def to_gradable(self, raw_response: dict) -> GradableReport:
        narrative = raw_response.get("narrative", "")
        sources = list(raw_response.get("sources", []))

        claim_texts = decompose_report(narrative, self.decomposer)

        claims: list[GradableClaim] = []
        for i, raw_claim in enumerate(claim_texts):
            text = raw_claim if isinstance(raw_claim, str) else getattr(raw_claim, "text", str(raw_claim))
            citations = self.matcher(text, sources)
            claims.append(
                GradableClaim(
                    id=f"{self._prefix}-c{i}",
                    text=text,
                    citations=list(citations),
                    verdict=None,      # filled by the independent grounding judge
                    confidence=None,   # — NOT the in-loop verifier
                )
            )

        return GradableReport(
            query=raw_response.get("query", ""),
            narrative_markdown=narrative,
            claims=claims,
            sources=sources,
            constraints=raw_response.get("constraints", {}) or {},
            metadata=raw_response.get("metadata", {}) or {},
        )


class PerplexityAdapter(_BaselineAdapter):
    """Perplexity Sonar free-prose response -> `GradableReport`."""

    _prefix = _PREFIX
