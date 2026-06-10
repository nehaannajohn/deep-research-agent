"""Passages -> atomic claims, each tagged with the passage(s) it rests on (cite-as-you-write).

The generator *proposes* claim->citation links; they are only candidates here — an
independent verifier confirms them later. Claims with no valid citation are dropped.
"""
from __future__ import annotations

from dra.schemas import Citation, Claim

_SYNTH_PROMPT = """Sub-question: {subq}

Passages (cite each claim by its [source_id]):
{passages}

Write atomic claims (ONE assertion each) that answer the sub-question, grounded ONLY in
the passages above. Each claim must cite the source_id(s) it uses.
Return ONLY JSON: {{"claims": [{{"text": "...", "citations": ["source_id", ...]}}]}}"""


def _format_passages(passages) -> str:
    return "\n".join(f"[{p.source_id}] {p.text[:600]}" for p in passages)


def synthesize(subquestion: str, passages, llm, start_index: int = 0) -> list:
    """`llm` is a BedrockChat-like object with `complete_json`."""
    by_id = {p.source_id: p for p in passages}
    data = llm.complete_json(_SYNTH_PROMPT.format(subq=subquestion, passages=_format_passages(passages)))
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
