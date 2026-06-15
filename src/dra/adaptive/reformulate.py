"""Claim-targeted query reformulation — the first adaptive repair.

Given a weakly-verified claim, draft a focused search query for THAT claim's
specific assertion (not the whole sub-question), so re-querying the SAME channel
(Exa) surfaces sharper evidence to confirm or correct it. The LLM is injected (a
`complete`-style object); the prompt + parse are pure and fake-testable.
"""
from __future__ import annotations

_PROMPT = (
    "A fact-checking step needs sharper evidence for ONE specific claim.\n"
    "Write a single focused web-search query (<= 20 words) that would surface "
    "authoritative evidence to confirm or refute exactly this claim. Target the "
    "claim's specific assertion, not the broad topic. Output ONLY the query — no "
    "quotes, no preamble.\n\n"
    "SUB-QUESTION CONTEXT: {subquestion}\n"
    "CLAIM: {claim}\n\nSearch query:"
)


def reformulate(claim: str, subquestion: str, llm) -> str:
    """Return a focused search query targeting `claim`. Falls back to the claim
    text itself if the LLM returns nothing usable."""
    prompt = _PROMPT.format(subquestion=(subquestion or "(none)"), claim=claim)
    try:
        out = (llm.complete(prompt) or "").strip()
    except Exception:
        out = ""
    out = out.splitlines()[0].strip().strip('"').strip() if out else ""
    return out or claim
