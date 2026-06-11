"""Formatting / instruction-adherence checklist (spec §4).

Each constraint compiles to a deterministic check over the report's
``narrative_markdown`` / structure. Decidable constraints (visual block,
table, length cap, focus topics) are scored here; fuzzy constraints (tone,
style, anything we don't recognise) are marked ``applicable=False`` and left
for a future judge hook.
"""
from __future__ import annotations

import re

from dra.eval.pipeline.contracts import GradableReport

_MERMAID_RE = re.compile(r"```mermaid\b", re.IGNORECASE)


def _word_count(md: str) -> int:
    return len(md.split())


def _has_mermaid(md: str) -> bool:
    return bool(_MERMAID_RE.search(md))


def _has_table(md: str) -> bool:
    # a header row with a pipe, followed by a separator row using --- and |
    for m in re.finditer(r"^.*\|.*$", md, re.MULTILINE):
        rest = md[m.end():].lstrip("\n")
        sep = rest.split("\n", 1)[0]
        if "-" in sep and "|" in sep and re.search(r"-{3,}", sep):
            return True
    return False


def score_formatting(report: GradableReport, constraints: dict) -> dict:
    """Compile each constraint to a check; return per-constraint + pass_rate.

    Returns ``{pass_rate, applicable, satisfied, per_constraint}``. Unknown /
    fuzzy constraints are skipped (``applicable=False``) and excluded from the
    rate. ``pass_rate`` is ``None`` when no constraint is applicable.
    """
    md = report.narrative_markdown
    per_constraint: list[dict] = []
    applicable = 0
    satisfied = 0

    for name, value in constraints.items():
        ok: bool
        is_applicable = True

        if name == "wants_visual":
            if value:
                ok = _has_mermaid(md)
            else:
                is_applicable = False
                ok = False
        elif name == "format" and value == "table":
            ok = _has_table(md)
        elif name in ("max_words", "max_length", "word_cap") and isinstance(value, int):
            ok = _word_count(md) <= value
        elif name == "focus_topics" and isinstance(value, (list, tuple)):
            low = md.lower()
            ok = all(str(t).lower() in low for t in value)
        else:
            # Unknown / fuzzy constraint (tone, style, ...). Skip for now.
            # TODO: route to a fuzzy-constraint judge (panel family) in Phase 2.
            is_applicable = False
            ok = False

        if is_applicable:
            applicable += 1
            if ok:
                satisfied += 1

        per_constraint.append({"name": name, "ok": ok, "applicable": is_applicable})

    pass_rate = satisfied / applicable if applicable else None
    return {
        "pass_rate": pass_rate,
        "applicable": applicable,
        "satisfied": satisfied,
        "per_constraint": per_constraint,
    }
