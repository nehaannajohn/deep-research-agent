"""Report narrative -> atomic claims, via the synthesis decomposer (Phase 3).

The same claim-extraction component the pipeline uses to write grounded claims
(`dra.synthesis.synthesize`) is reused here to reduce ANY report — ours or a
black-box baseline's free prose — to atomic claims, so every system is decomposed
by the same instrument (spec §2/§3.3). The ``decomposer`` is **injected** so this
stays pure and offline (a fake in tests; the synthesis-family component live).

The injected ``decomposer`` is any callable ``narrative_markdown -> list`` (the
elements may be plain claim strings or richer claim objects — the adapter that
calls this decides how to wrap them).
"""
from __future__ import annotations

from typing import Callable

__all__ = ["decompose_report"]

Decomposer = Callable[[str], list]


def decompose_report(narrative_markdown: str, decomposer: Decomposer) -> list:
    """Decompose ``narrative_markdown`` into atomic claims via ``decomposer``.

    Thin wrapper: keeps the decomposition a single, swappable component so the
    baseline adapters and our own path share one claim-extraction instrument.
    """
    return decomposer(narrative_markdown)
