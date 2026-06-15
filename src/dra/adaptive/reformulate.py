"""Sub-query reformulation — the first adaptive repair (same channel, better query).

When a sub-question's claims came back weakly verified, re-querying Exa with the
SAME wording returns the same pool. So we reword the **sub-query** to surface
sharper evidence, using the weakly-supported claims as the signal for *what* the
original retrieval missed. Re-query Exa with the result, regenerate the claims,
re-verify. The LLM is injected; the prompt + parse are pure and fake-testable.
"""
from __future__ import annotations

_PROMPT = (
    "A research sub-question was searched on the web, but the evidence came back "
    "too weak to confidently verify its findings. Reword it into a SINGLE better "
    "web-search query (<= 20 words) that would surface stronger, more direct "
    "evidence for the weakly-supported points below. Keep the same intent; change "
    "the framing/terms. Output ONLY the query — no quotes, no preamble.\n\n"
    "SUB-QUESTION: {subquestion}\n"
    "WEAKLY-SUPPORTED POINTS:\n{claims}\n\nBetter search query:"
)


def reformulate(subquestion: str, weak_claims: list[str], llm) -> str:
    """Return a reworded search query for `subquestion`, informed by the weakly-
    supported claims. Falls back to the original sub-question if the LLM returns
    nothing usable."""
    pts = "\n".join(f"- {c}" for c in (weak_claims or [])) or "- (none)"
    prompt = _PROMPT.format(subquestion=subquestion, claims=pts)
    try:
        out = (llm.complete(prompt) or "").strip()
    except Exception:
        out = ""
    out = out.splitlines()[0].strip().strip('"').strip() if out else ""
    return out or subquestion
