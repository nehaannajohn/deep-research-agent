"""Text-level Expected-Behavior-Match (EBM) judge.

EBM is conceptually about whether the *report text* exhibits the query's
`expected_behavior`:

- ``flag_contested``     — the report surfaces that sources disagree / the
  finding is contested or conflicting.
- ``report_insufficient`` — the report says the answer is unknown / there is
  insufficient evidence / it cannot be determined.
- ``answer_confident``    — the report commits to a direct answer without
  hedging it as unknown.

That property is judgeable from the report text + the query alone (no access to
the system's internal per-claim verdicts or its passages — unlike grounding).
This module provides a pure prompt builder, a resilient parser, and a small
``behavior_match`` orchestration helper around an injected ``llm`` (a
panel-family `BedrockChat` live, a fake in tests). Behaviors that are not
text-judgeable (e.g. ``ask_clarification``) return ``None``.
"""
from __future__ import annotations

from typing import Optional

from dra.llm.bedrock import _extract_json

__all__ = [
    "TEXT_JUDGEABLE_BEHAVIORS",
    "build_behavior_prompt",
    "parse_behavior_match",
    "behavior_match",
]

# Behaviors whose presence is decidable from the report text + the query alone.
# ``ask_clarification`` (the system should ask a question back) and any future
# non-text behavior are intentionally excluded -> ``behavior_match`` returns None.
_CRITERIA = {
    "flag_contested": (
        "the report EXPLICITLY states that sources disagree, that the evidence "
        "is conflicting, or that the finding is contested/disputed. A confident "
        "single answer with no mention of disagreement does NOT count."
    ),
    "report_insufficient": (
        "the report EXPLICITLY states that the answer is unknown, that the "
        "evidence is insufficient, or that the question cannot be determined / "
        "answered from the available information. A confident answer does NOT "
        "count."
    ),
    "answer_confident": (
        "the report gives a direct, committed answer to the query, WITHOUT "
        "hedging it as unknown / undeterminable / lacking evidence. Surfacing "
        "minor caveats is fine as long as a clear answer is given."
    ),
}

TEXT_JUDGEABLE_BEHAVIORS = frozenset(_CRITERIA)

_PROMPT = """You judge whether a research REPORT exhibits a specific EXPECTED BEHAVIOR for a QUERY.

EXPECTED BEHAVIOR: "{behavior}"
This behavior is exhibited when {criteria}

Judge ONLY the report TEXT against this criterion. Do not reward a report for
being correct or well-written — only for whether it exhibits the behavior.

Answer ONLY JSON: {{"match": true|false, "reason": "<one short sentence>"}}

QUERY:
{query}

REPORT:
{report}"""


def build_behavior_prompt(query: str, report_text: str, expected_behavior: str) -> str:
    """Render the judge prompt for one (query, report, expected_behavior).

    Raises ``KeyError`` for a behavior that is not text-judgeable — callers
    should gate on `TEXT_JUDGEABLE_BEHAVIORS` / use `behavior_match`, which
    returns ``None`` for those.
    """
    criteria = _CRITERIA[expected_behavior]
    return _PROMPT.format(
        behavior=expected_behavior,
        criteria=criteria,
        query=query or "",
        report=report_text or "",
    )


def parse_behavior_match(llm_output: str) -> Optional[bool]:
    """Resiliently parse the judge's ``{"match": ...}`` decision.

    Returns ``True``/``False`` on a recognizable boolean, else ``None`` (a
    malformed/empty/unparseable response is treated as "no decision" rather than
    a crash or a silent False).
    """
    try:
        data = _extract_json(llm_output)
    except Exception:  # noqa: BLE001 - unparseable -> no decision
        return _scan_text(llm_output)

    if isinstance(data, dict) and "match" in data:
        return _coerce_bool(data["match"])
    return _scan_text(llm_output)


def _coerce_bool(value) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1"):
            return True
        if v in ("false", "no", "0"):
            return False
    return None


def _scan_text(text: str) -> Optional[bool]:
    """Last-resort bare-text scan for an unfenced true/false."""
    t = (text or "").lower()
    has_true = "true" in t
    has_false = "false" in t
    if has_true and not has_false:
        return True
    if has_false and not has_true:
        return False
    return None


def behavior_match(query: str, report_text: str, expected_behavior: Optional[str],
                   llm) -> Optional[bool]:
    """Judge whether ``report_text`` exhibits ``expected_behavior`` for ``query``.

    Returns ``None`` (not text-judgeable / nothing to judge) when:
    - ``expected_behavior`` is falsy or not in `TEXT_JUDGEABLE_BEHAVIORS`
      (e.g. ``ask_clarification``), or
    - ``report_text`` is empty/whitespace.

    Otherwise prompts the injected ``llm`` (``complete(prompt) -> str``) and
    returns the parsed boolean (``None`` if the response is unparseable or the
    call raises — resilient, never fatal).
    """
    if not expected_behavior or expected_behavior not in TEXT_JUDGEABLE_BEHAVIORS:
        return None
    if not (report_text or "").strip():
        return None

    prompt = build_behavior_prompt(query, report_text, expected_behavior)
    try:
        out = llm.complete(prompt)
    except Exception:  # noqa: BLE001 - a failed call -> no decision, not a crash
        return None
    return parse_behavior_match(out)
