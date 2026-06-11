"""Passages -> atomic claims, each tagged with the passage(s) it rests on (cite-as-you-write).

The generator *proposes* claim->citation links; they are only candidates here — an
independent verifier confirms them later. Claims with no valid citation are dropped.
"""
from __future__ import annotations

from dra.schemas import Citation, Claim

_SYNTH_PROMPT = """Overall query: {query}
Sub-question: {subq}

Passages (cite each claim by its [source_id]):
{passages}

Write atomic claims (ONE assertion each) that answer the sub-question.
STRICT GROUNDING RULE: use ONLY information explicitly stated in the passages above. Do NOT
add facts, names, numbers, dates, taxonomies, or any detail from your own knowledge — if it
is not written in the passages, do not write it. A claim that is true but not supported by
the passages does NOT belong here. Respect any formatting/scope intent in the overall query.
Each claim must cite the source_id(s) whose text directly supports it.
Return ONLY JSON: {{"claims": [{{"text": "...", "citations": ["source_id", ...]}}]}}"""


def _format_passages(passages) -> str:
    return "\n".join(f"[{p.source_id}] {p.text}" for p in passages)


def synthesize(query: str, subquestion: str, passages, llm, start_index: int = 0) -> list:
    """`llm` is a BedrockChat-like object with `complete_json`."""
    by_id = {p.source_id: p for p in passages}
    data = llm.complete_json(
        _SYNTH_PROMPT.format(query=query, subq=subquestion, passages=_format_passages(passages))
    )
    claims = []
    for i, c in enumerate(data.get("claims", [])):
        text = (c.get("text") or "").strip()
        if not text:
            continue
        cites = [Citation(source_id=sid, span=by_id[sid].text)
                 for sid in c.get("citations", []) if sid in by_id]
        if not cites:  # drop claims with no valid (grounded) citation
            continue
        claims.append(Claim(id=f"c{start_index + i}", text=text, section=subquestion, citations=cites))
    return claims
