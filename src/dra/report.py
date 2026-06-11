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


_NARRATIVE_PROMPT = """Compose a research report answering the QUERY using ONLY the CLAIMS below.
Rules:
- Every factual sentence MUST cite a claim id in square brackets, e.g. [c1]; use only the ids listed.
- Do NOT introduce any fact that is not one of the claims.
- Start with a "## Summary" section, then logical "## <topic>" sections.
{table}- Be concise.

QUERY: {query}

CLAIMS:
{claims}

Output GitHub-flavored Markdown only."""


def _claims_block(claims, verified: bool) -> str:
    lines = []
    for c in claims:
        if verified:
            conf = f", conf {c.confidence:.2f}" if c.confidence is not None else ""
            lines.append(f"[{c.id}] ({c.verdict}{conf}) {c.text}")
        else:
            lines.append(f"[{c.id}] {c.text}")
    return "\n".join(lines)


def strip_unknown_claim_refs(text: str, valid_ids: set) -> str:
    """Constrain-by-construction guard: drop any [cN] reference not in the ledger."""
    return re.sub(r"\[(c\d+)\]", lambda m: m.group(0) if m.group(1) in valid_ids else "", text)


def compose_narrative(query, plan, claims, generator, verified: bool) -> str:
    constraints = plan.constraints or {}
    table = ("- Present the core comparison as a Markdown table.\n"
             if constraints.get("format") == "table" else "")
    prompt = _NARRATIVE_PROMPT.format(query=query, claims=_claims_block(claims, verified),
                                      table=table)
    try:
        text = (generator.complete(prompt) or "").strip()
    except Exception:
        text = ""
    if not text:
        text = f"## Summary\nThis report summarizes {len(claims)} finding(s) for: {query}."
    return strip_unknown_claim_refs(text, {c.id for c in claims})


def compose_report(query, plan, claims, sources, generator, with_verification=None,
                   diagram_generator=None) -> ResearchReport:
    brief = " ; ".join(plan.subquestions)
    if not claims:
        return ResearchReport(
            query=query, resolved_brief=brief,
            report_markdown=f"# Research Report\n**Query:** {query}\n\n"
                            "No findings could be established for this query.",
            claims=[], sources=sources,
            metadata=ReportMetadata(descriptive_summary="No findings."),
        )
    verified = (with_verification if with_verification is not None
                else any(c.verdict != "unverified" for c in claims))
    narrative = compose_narrative(query, plan, claims, generator, verified)
    if (plan.constraints or {}).get("wants_visual") and diagram_generator is not None:
        from dra.diagram import insert_diagram
        narrative = insert_diagram(narrative, diagram_generator.generate(query, claims, narrative))
    md = rollup_metadata(plan, claims, verified)
    appendix = render_appendix(claims, sources, md, verified)
    report_markdown = f"# Research Report\n**Query:** {query}\n\n{narrative}\n\n---\n\n{appendix}"
    return ResearchReport(query=query, resolved_brief=brief, report_markdown=report_markdown,
                          claims=claims, sources=sources, metadata=md)
