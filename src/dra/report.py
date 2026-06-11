"""Report composition: turn a claim ledger + constraint spec into a ResearchReport.

Hybrid — an LLM (the Llama generator) composes the narrative + instruction artifacts
(Mermaid diagram / table); a deterministic layer renders the Detailed Citation Results
table, Confidence & Coverage, Disclaimers, and Sources. Verification-agnostic: the
verified variant surfaces verdicts/confidence/disclaimers, the unverified baseline omits
them. Constrain-by-construction: the narrative may only cite existing claim IDs.
See docs/superpowers/specs/2026-06-11-report-composition-design.md.
"""
from __future__ import annotations

import re

from dra.schemas import Claim, Passage, ReportMetadata, ResearchReport

_LOW_COVERAGE = 0.5
_VERDICTS = ("supported", "refuted", "insufficient", "contested")


def _mean(xs):
    return round(sum(xs) / len(xs), 3) if xs else None


def _disclaimers(claims, coverage) -> list[str]:
    out = []
    n_cont = sum(1 for c in claims if c.verdict == "contested")
    n_insuf = sum(1 for c in claims if c.verdict == "insufficient")
    if n_cont:
        out.append(f"{n_cont} finding(s) are contested — sources disagree; both sides are shown.")
    if n_insuf:
        out.append(f"{n_insuf} finding(s) have insufficient support and should be treated as tentative.")
    if coverage is not None and coverage < _LOW_COVERAGE:
        out.append(f"Coverage is limited ({coverage:.0%} of sub-questions had supported findings).")
    return out


def rollup_metadata(plan, claims, verified: bool) -> ReportMetadata:
    md = ReportMetadata()
    subqs = list(plan.subquestions)
    if verified:
        md.overall_confidence = _mean([c.confidence for c in claims if c.confidence is not None])
        breakdown = {}
        for verd in _VERDICTS:
            group = [c for c in claims if c.verdict == verd]
            if group:
                breakdown[verd] = {"count": len(group),
                                   "mean_conf": _mean([c.confidence for c in group if c.confidence is not None])}
        md.confidence_breakdown = breakdown
        covered = {c.section for c in claims if c.verdict == "supported"}
        md.coverage = round(len(covered & set(subqs)) / len(subqs), 3) if subqs else None
        md.disclaimers = _disclaimers(claims, md.coverage)
    else:
        covered = {c.section for c in claims}
        md.coverage = round(len(covered & set(subqs)) / len(subqs), 3) if subqs else None
    md.descriptive_summary = f"{len(claims)} claims across {len(subqs)} sub-questions."
    return md


def render_appendix(claims, sources, md: ReportMetadata, verified: bool) -> str:
    out = ["## Detailed Citation Results"]
    if verified:
        out += ["| # | Claim | Verdict | Conf | Sources |", "|---|---|---|---|---|"]
        for c in claims:
            cites = ", ".join(sorted({cit.source_id for cit in c.citations}))
            conf = f"{c.confidence:.2f}" if c.confidence is not None else "—"
            out.append(f"| {c.id} | {c.text} | {c.verdict} | {conf} | {cites} |")
        out += ["", "## Confidence & Coverage",
                f"- Overall confidence: {md.overall_confidence if md.overall_confidence is not None else '—'}"
                f"   ·   Coverage: {md.coverage if md.coverage is not None else '—'}"]
        if md.confidence_breakdown:
            out.append("- Breakdown: " + " · ".join(f"{k} {v['count']}" for k, v in md.confidence_breakdown.items()))
        if md.disclaimers:
            out += ["", "## Disclaimers"] + [f"- {d}" for d in md.disclaimers]
    else:
        out += ["| # | Claim | Sources |", "|---|---|---|"]
        for c in claims:
            cites = ", ".join(sorted({cit.source_id for cit in c.citations}))
            out.append(f"| {c.id} | {c.text} | {cites} |")
    out += ["", "## Sources"]
    for p in sources:
        out.append(f"- [{p.source_id}] {(p.title or p.url or '').strip()}")
    return "\n".join(out)
