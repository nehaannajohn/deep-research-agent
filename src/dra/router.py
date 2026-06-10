"""Per-sub-question source routing.

For the MVP the only backend is Exa (Phase-1 bake-off), so the label is currently
informational/observability; the full design routes to distinct tools.
"""
from __future__ import annotations

_ROUTE_PROMPT = """Pick the best source type for this sub-question.
Answer with ONE word: 'academic' (needs research papers) or 'web' (general knowledge).
Sub-question: {subq}"""


def route(subquestion: str, llm) -> str:
    """`llm` is a BedrockChat-like object with `complete`. Returns 'academic' or 'web'."""
    out = (llm.complete(_ROUTE_PROMPT.format(subq=subquestion)) or "").strip().lower()
    return "academic" if "academic" in out else "web"
