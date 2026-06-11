"""Answer-extraction: long `GradableReport` -> short answer (spec §5, D2).

`extract_answer` maps a long report to the short gold-comparable answer for the
agentic tier (facet 2a):

- **Rule fast-path:** if any alias appears in the report's
  ``metadata["descriptive_summary"]`` or in the first sentence of the narrative,
  return that alias verbatim — cheap, deterministic, no model call.
- **LLM extraction:** otherwise prompt an *injected* extractor (a panel-family
  model, never the generator — independence) for ONLY the final short answer,
  or ``INSUFFICIENT`` if the report does not commit. Abstention is a feature of
  an honesty-first system, scored as correct downstream, not a miss.

Pure logic: `extractor` is injected (a fake in tests). No live network here.
"""
from __future__ import annotations

import re
from typing import Optional, Sequence

INSUFFICIENT = "INSUFFICIENT"

_EXTRACT_PROMPT = """Given the QUESTION and the research REPORT, output ONLY the final short answer \
(a name, number, date, or short phrase). If the report does not commit to an answer, output \
exactly INSUFFICIENT.

Do not explain. Output only the answer.

QUESTION:
{question}

REPORT:
{report}"""


def _first_sentence(text: str) -> str:
    """First sentence of the narrative (split on . ! ? or newline)."""
    t = (text or "").strip()
    if not t:
        return ""
    m = re.split(r"(?<=[.!?])\s|\n", t, maxsplit=1)
    return m[0].strip()


def _alias_in(haystack: str, alias: str) -> bool:
    """Case-insensitive whole-token-ish containment of an alias in a haystack."""
    if not alias:
        return False
    return alias.lower() in (haystack or "").lower()


def extract_answer(
    report,
    question: str,
    *,
    aliases: Sequence[str] = (),
    extractor=None,
) -> str:
    """Return the report's short answer, or ``INSUFFICIENT`` if it does not commit."""
    summary = ""
    if isinstance(report.metadata, dict):
        summary = report.metadata.get("descriptive_summary", "") or ""
    first = _first_sentence(report.narrative_markdown)

    # Rule fast-path: an alias present in the summary or the first sentence.
    for alias in aliases:
        if _alias_in(summary, alias) or _alias_in(first, alias):
            return alias

    # LLM extraction path.
    if extractor is None:
        return INSUFFICIENT
    prompt = _EXTRACT_PROMPT.format(question=question, report=report.narrative_markdown or "")
    span = extractor.complete(prompt)
    span = (span or "").strip()
    if not span or span.upper() == INSUFFICIENT:
        return INSUFFICIENT
    return span
