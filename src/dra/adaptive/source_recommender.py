"""Source recommender — name NET-NEW, fetchable sources that fill the evidence gap.

Diversifying retrieval only helps if it points OUTSIDE what we already have. So
Sonnet is shown the sub-question, the **URLs Exa already cited**, and the extracted
claims, and asked for ADDITIONAL authoritative sources — as concrete, fetchable
URLs — that are NOT already among the cited ones and would close the insufficient-
evidence gap. The loop then fetches those URLs directly (outside Exa) and re-verifies
the claim against the combined evidence.

Two guards keep it honest: the prompt explicitly demands net-new sources (the cited
URLs are listed as "do not repeat"), and we additionally drop any recommendation
whose domain already appears among the cited URLs — so a redundant suggestion can't
slip through.

`recommend_sources` is pure (llm injected) and fake-testable; inputs are plain
strings so the module doesn't depend on the report schema.
"""
from __future__ import annotations

import json
import re


def _prompt(subquestion: str, cited_urls: list[str], claims: list[str]) -> str:
    have = "\n".join(f"- {u}" for u in cited_urls) or "- (none)"
    cls = "\n".join(f"- {c}" for c in claims) or "- (none)"
    return (
        "A research sub-question was investigated using ONLY broad web search "
        "(Exa). The evidence is INSUFFICIENT to fully establish the claims below.\n\n"
        f"SUB-QUESTION: {subquestion}\n\n"
        f"URLs ALREADY CITED (do NOT repeat these or other pages on the same sites — "
        f"we need NET-NEW sources):\n{have}\n\n"
        f"EXTRACTED CLAIMS (need stronger evidence):\n{cls}\n\n"
        "Recommend ADDITIONAL, authoritative sources that are NOT already cited above "
        "and would close the evidence gap. Prefer PRIMARY / authoritative sources "
        "beyond general web pages — official statistics, standards bodies, registries, "
        "datasets, primary documents. Give each as a CONCRETE, FETCHABLE URL.\n"
        'Return ONLY a JSON array: '
        '[{"url": "https://...", "kind": "...", "covers": "..."}]'
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
    m = re.search(r"https?://([^/\s]+)", (s or "").strip().lower())
    host = m.group(1) if m else ""
    if not host:
        m = re.search(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", (s or "").lower())
        host = m.group(0) if m else ""
    return re.sub(r"^www\.", "", host)   # strip only the www. PREFIX (not a char set)


def recommend_sources(subquestion: str, cited_urls: list[str],
                      claims: list[str], llm) -> list[dict]:
    """Return [{"url", "kind", "covers"}] of NET-NEW fetchable sources.

    A recommendation is dropped if it isn't an http(s) URL, or if its domain already
    appears among `cited_urls` (redundant with Exa's results), or if it duplicates an
    earlier recommendation. Returns [] if the LLM gives nothing usable.
    """
    have_domains = {_domain(u) for u in cited_urls if _domain(u)}
    try:
        raw = _extract_array(llm.complete(_prompt(subquestion, cited_urls, claims)) or "")
    except Exception:
        raw = []
    out, seen = [], set()
    for r in raw:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url", "")).strip()
        if not re.match(r"^https?://", url, re.I):   # must be a concrete, fetchable URL
            continue
        d = _domain(url)
        if (d and d in have_domains) or url in seen:  # net-new only
            continue
        seen.add(url)
        out.append({"url": url, "kind": str(r.get("kind", "")).strip(),
                    "covers": str(r.get("covers", "")).strip()})
    return out
