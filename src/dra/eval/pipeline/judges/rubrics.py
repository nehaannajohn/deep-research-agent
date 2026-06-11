"""Rubric prompt builders for the blind judge panel (spec §4, §6).

Each builder renders a self-contained 1–5 scoring prompt that asks for a single
integer score plus a one-line justification, as JSON. The prompts are
deliberately *blind*: they never name the system under test (no "Deep Research
Agent" / "Perplexity" / "Fable" identity), so a judge cannot favour an
artifact by provenance — the same independence principle as the grounding judge.
"""
from __future__ import annotations

from dra.eval.pipeline.contracts import GradableReport

# Shared answer-format instruction — one integer 1..5 + a one-line justification.
_SCALE = (
    "Score on an integer scale from 1 (worst) to 5 (best).\n"
    'Answer ONLY JSON: {"score": <1-5 integer>, "justification": "<one line>"}'
)


def _report_block(report: GradableReport) -> str:
    """Render the (anonymous) report body the judge scores."""
    return report.narrative_markdown or ""


def relevance_rubric(report: GradableReport, query: str) -> str:
    """1–5 relevance rubric: does the report answer the query / are citations on-topic."""
    return (
        "You are evaluating a research report for RELEVANCE.\n"
        "Judge whether the report directly answers the QUESTION and whether its "
        "content and citations stay on-topic. Do not reward length or style here.\n\n"
        f"{_SCALE}\n\n"
        f"QUESTION:\n{query}\n\n"
        f"REPORT:\n{_report_block(report)}"
    )


def quality_rubric(report: GradableReport, query: str) -> str:
    """1–5 quality rubric: coherence + comprehensiveness."""
    return (
        "You are evaluating a research report for QUALITY.\n"
        "Judge coherence (clear, well-organized argument) and comprehensiveness "
        "(covers the important aspects of the question). Do not reward off-topic "
        "padding.\n\n"
        f"{_SCALE}\n\n"
        f"QUESTION:\n{query}\n\n"
        f"REPORT:\n{_report_block(report)}"
    )


def fuzzy_formatting_rubric(report: GradableReport, query: str, constraint: str) -> str:
    """1–5 hook for a single fuzzy formatting/scope constraint the deterministic
    checks cannot decide (e.g. tone, focus-topic coverage)."""
    return (
        "You are evaluating whether a research report satisfies a specific "
        "FORMATTING / SCOPE constraint.\n"
        f"CONSTRAINT: {constraint}\n"
        "Score 5 if fully satisfied, 1 if ignored.\n\n"
        f"{_SCALE}\n\n"
        f"QUESTION:\n{query}\n\n"
        f"REPORT:\n{_report_block(report)}"
    )
