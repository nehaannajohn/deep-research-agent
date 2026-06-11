"""Pipeline entry point.

Phase 2: single-pass walking skeleton —
`query -> plan -> (route -> Exa search -> synthesize -> verify) per sub-question -> ResearchReport`.
No adaptive loop yet (that's Phase 3).
"""
from __future__ import annotations

from dataclasses import dataclass

from dra.planner import plan
from dra.router import route
from dra.schemas import ResearchReport
from dra.synthesis import synthesize
from dra.verify.base import Verifier

# Settled retrieval default (experiments/results stage3+4 → VERDICT_k.md): cumulative
# coverage is flat beyond 5 records/sub-question, so 5 is the lean default; the future
# adaptive loop escalates k for the rare sub-question that needs more.
RETRIEVAL_K = 5


@dataclass
class Deps:
    generator: object  # BedrockChat-like: planner/synthesis (complete_json) + router (complete)
    verifier: Verifier
    search: object  # SearchTool


def _render_markdown(report: ResearchReport) -> str:
    out = ["# Research Report", "", f"**Query:** {report.query}", ""]
    sections: dict = {}
    for c in report.claims:
        sections.setdefault(c.section, []).append(c)
    for section, claims in sections.items():
        out.append(f"## {section}")
        for c in claims:
            cites = ", ".join(sorted({cit.source_id for cit in c.citations}))
            conf = f"{c.confidence:.2f}" if c.confidence is not None else "—"
            out.append(f"- {c.text}  _({c.verdict}, conf={conf}; sources: {cites})_")
        out.append("")
    out.append("## References")
    for p in report.sources:
        out.append(f"- [{p.source_id}] {(p.title or p.url or '').strip()}")
    return "\n".join(out)


def run_query(query: str, deps: "Deps | None" = None) -> ResearchReport:
    if deps is None:  # Phase-0 skeleton behaviour
        return ResearchReport(query=query)

    p = plan(query, deps.generator)
    claims: list = []
    sources: dict = {}
    for subq in p.subquestions:
        route(subq, deps.generator)  # label only (Exa is the single MVP backend)
        passages = deps.search.search(subq, k=RETRIEVAL_K).passages
        for psg in passages:
            sources[psg.source_id] = psg
        new = synthesize(query, subq, passages, deps.generator, start_index=len(claims))
        for c in new:
            cited = [sources[cit.source_id] for cit in c.citations if cit.source_id in sources]
            r = deps.verifier.verify(c.text, cited)
            c.verdict, c.confidence = r.label, r.confidence
        claims.extend(new)

    report = ResearchReport(
        query=query,
        resolved_brief=" ; ".join(p.subquestions),
        claims=claims,
        sources=list(sources.values()),
    )
    report.metadata.descriptive_summary = (
        f"{len(claims)} claims across {len(p.subquestions)} sub-questions."
    )
    report.report_markdown = _render_markdown(report)
    return report


def build_deps(cfg) -> Deps:
    from dra.llm.bedrock import BedrockChat
    from dra.search import default_search_tool
    from dra.verify.ensemble import EnsembleVerifier
    from dra.verify.llm_judge import LLMJudgeVerifier

    # Selected verifier (provisional): the 3-model ensemble {Sonnet, Mistral, Nova} with
    # cross-model agreement as confidence. Falls back to the single in-loop judge if no
    # ensemble is configured. See experiments/results/verifier/DECISION.md (revisit at Layer 1).
    if cfg.verifier_models:
        verifier = EnsembleVerifier(
            [LLMJudgeVerifier(BedrockChat(m, region=cfg.region), n_samples=1)
             for m in cfg.verifier_models]
        )
    else:
        verifier = LLMJudgeVerifier(BedrockChat(cfg.roles["inloop_judge"], region=cfg.region))
    return Deps(
        generator=BedrockChat(cfg.roles["generator"], region=cfg.region),
        verifier=verifier,
        search=default_search_tool(cfg),
    )
