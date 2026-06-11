"""Fable reference-report generation + parse (spec §10 D1, plan Phase G).

DRA-Bench gold is a **Fable-generated reference report** per prompt. We ask Fable
(an Anthropic-family model) for a detailed structured `.md` report with a
*minimal* prompt (per D1 — no elaborate prompting), then parse that markdown into
a `GradableReport` using the **same** standalone decomposer the harness runs on
our own and the baseline reports. The reference is therefore scored on the same
axes (and the same independent grounding judge), so any Fable hallucination
surfaces symmetrically and the comparison stays fair without assuming Fable is
perfect.

`generate_reference` is the live Fable call (`# pragma: no cover`). `FABLE_PROMPT`
and `parse_reference` are pure and fake-tested.
"""
from __future__ import annotations

from typing import Callable

from dra.eval.pipeline.contracts import GradableClaim, GradableReport
from dra.eval.pipeline.scoring.decompose import decompose_report

__all__ = ["FABLE_PROMPT", "generate_reference", "parse_reference"]

Decomposer = Callable[[str], list]


def FABLE_PROMPT(query: str) -> str:
    """Minimal instruction for the Fable reference report (per D1)."""
    return (
        f"Research the following question and produce a detailed, well-structured "
        f"report in Markdown.\n\nQuestion: {query}"
    )


def generate_reference(query: str, fable_llm) -> str:  # pragma: no cover
    """Live: ask Fable for the structured `.md` reference report."""
    return fable_llm.complete(FABLE_PROMPT(query))


def parse_reference(query: str, markdown: str, decomposer: Decomposer) -> GradableReport:
    """Parse a Fable reference `.md` into a `GradableReport` (pure).

    Reuses `decompose_report` (the shared claim-extraction instrument) to reduce
    the narrative to atomic claims, mirroring the baseline path. Each claim is
    namespaced `fable-NNN` with empty citations and `verdict=None` — verdicts are
    assigned downstream by the independent grounding judge, never inferred here.
    """
    claim_texts = decompose_report(markdown, decomposer)
    claims: list[GradableClaim] = []
    for i, raw_claim in enumerate(claim_texts):
        text = raw_claim if isinstance(raw_claim, str) else getattr(raw_claim, "text", str(raw_claim))
        claims.append(
            GradableClaim(
                id=f"fable-{i:03d}",
                text=text,
                citations=[],
                verdict=None,
            )
        )
    return GradableReport(
        query=query,
        narrative_markdown=markdown,
        claims=claims,
        sources=[],
        metadata={"source": "fable_reference"},
    )
