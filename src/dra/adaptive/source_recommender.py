"""Source recommender — diagnose the insufficient-evidence gap and name what fills it.

Diversifying retrieval is only meaningful if it points OUTSIDE what we already
have. So Sonnet is shown the actual context — the sub-question, the sources Exa
already returned, and the extracted claims — and asked: which ADDITIONAL,
specific authoritative sources (not already in the list) would cover the evidence
gap? Output is grounded in what's missing relative to Exa's results, not a generic
"good sources" list.

These recommendations are the retrieval-ceiling signal: a per-claim map of the
primary/authoritative sources (official statistics, standards bodies, registries,
primary documents) that the open-web pool didn't supply. How the loop consumes
them (targeted fetch vs. logged as a coverage gap) is decided at wiring time.

`recommend_sources` is pure (llm injected) and fake-testable; `existing_sources`
and `claims` are plain strings so the module doesn't depend on the report schema.
"""
from __future__ import annotations

import json
import re


def _prompt(subquestion: str, existing_sources: list[str], claims: list[str]) -> str:
    have = "\n".join(f"- {s}" for s in existing_sources) or "- (none)"
    cls = "\n".join(f"- {c}" for c in claims) or "- (none)"
    return (
        "A research sub-question was investigated using ONLY broad web search "
        "(Exa). The evidence is INSUFFICIENT to fully establish the claims below.\n\n"
        f"SUB-QUESTION: {subquestion}\n\n"
        f"SOURCES EXA ALREADY RETURNED:\n{have}\n\n"
        f"EXTRACTED CLAIMS (need stronger evidence):\n{cls}\n\n"
        "Recommend ADDITIONAL, SPECIFIC authoritative sources that are NOT already "
        "in the list above and would cover the evidence gap. Prefer PRIMARY / "
        "authoritative sources outside general web pages — official statistics, "
        "standards bodies, registries, datasets, primary documents. For each, give "
        "the source (name or domain), its kind, and which gap it fills.\n"
        'Return ONLY a JSON array: '
        '[{"source": "...", "kind": "...", "covers": "..."}]'
    )


def _extract_array(text: str) -> list:
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _domain(s: str) -> str:
    m = re.search(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", (s or "").lower())
    return m.group(0) if m else ""


def recommend_sources(subquestion: str, existing_sources: list[str],
                      claims: list[str], llm) -> list[dict]:
    """Return [{"source", "kind", "covers"}] of additional sources to fill the gap.

    Recommendations whose domain already appears among `existing_sources` are
    dropped, so the output genuinely adds coverage rather than re-naming what Exa
    already returned. Returns [] if the LLM gives nothing usable.
    """
    have_domains = {_domain(s) for s in existing_sources if _domain(s)}
    try:
        raw = _extract_array(llm.complete(_prompt(subquestion, existing_sources, claims)) or "")
    except Exception:
        raw = []
    out = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        src = str(r.get("source", "")).strip()
        if not src:
            continue
        d = _domain(src)
        if d and d in have_domains:  # already covered by Exa's results
            continue
        out.append({"source": src, "kind": str(r.get("kind", "")).strip(),
                    "covers": str(r.get("covers", "")).strip()})
    return out
