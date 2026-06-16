"""Adaptive retrieval loop — confidence-gated, claim-level, sub-query repair.

Single pass first (identical to dra.loop.run_query). Then, per sub-question, if any
of its claims is below τ, repair the sub-query — in two ways and keep the best:

  Part 1 (reformulate): reword the sub-query (using the weak claims as the signal),
    re-query Exa, regenerate + re-verify the claims.
  Part 2 (diversify): recommend NET-NEW source URLs (given the sub-question, the
    already-cited URLs, and the claims), fetch them query-targeted, COMBINE with the
    incumbent Exa passages, regenerate + re-verify.

Keep the candidate (incumbent included) with the highest section confidence (= the
weakest claim's calibrated confidence, the gate's own quantity). Stop a sub-question
on τ / no-progress / max-iters. Only below-τ sub-questions iterate; the rest stay
frozen. See docs/archive/2026-06-14-adaptive-retrieval-design.md.
"""
from __future__ import annotations

from dra.adaptive.control import made_progress, needs_repair
from dra.adaptive.reformulate import reformulate
from dra.adaptive.source_recommender import recommend_sources
from dra.contradiction import detect_and_resolve
from dra.loop import RETRIEVAL_K, Deps  # reuse the single-pass contract + default k
from dra.planner import plan
from dra.report import compose_report
from dra.router import route
from dra.schemas import ResearchReport
from dra.synthesis import synthesize


def _section_score(claims) -> float:
    """A sub-question's confidence = its weakest claim's calibrated confidence
    (the gate quantity). No verified claims => 0.0 (weak)."""
    confs = [c.confidence for c in claims if c.confidence is not None]
    return min(confs) if confs else 0.0


def _synth_verify(query, subq, passages, deps, start_index):
    """Synthesize claims for one sub-query from `passages` and verify each against
    its own cited passages — mirrors the single-pass per-sub-question step."""
    claims = synthesize(query, subq, passages, deps.generator, start_index=start_index)
    src = {p.source_id: p for p in passages}
    for c in claims:
        cited = [src[cit.source_id] for cit in c.citations if cit.source_id in src]
        r = deps.verifier.verify(c.text, cited)
        c.verdict, c.confidence = r.label, r.confidence
    return claims


def run_query_adaptive(query: str, deps: "Deps | None" = None, *, tau: float = 0.7,
                       eps: float = 0.05, max_iters: int = 3, recommender_llm=None,
                       fetcher=None, trace: list | None = None) -> ResearchReport:
    """Drop-in for `run_query` with the confidence-gated repair loop. Part 2
    (diversify) runs only when both `recommender_llm` and `fetcher` are provided;
    otherwise the loop is reformulation-only. `trace`, if given, collects one dict
    per sub-question (iters, final score, winning repair, recs/fetched counts)."""
    if deps is None:
        return ResearchReport(query=query)

    p = plan(query, deps.generator)
    all_claims: list = []
    sources: dict = {}

    for subq in p.subquestions:
        route(subq, deps.generator)  # label only (Exa is the single search backend)
        offset = len(all_claims)
        passages = deps.search.search(subq, k=RETRIEVAL_K).passages
        claims = _synth_verify(query, subq, passages, deps, offset)
        best = {"claims": claims, "passages": passages,
                "score": _section_score(claims), "via": "base"}

        iters, n_recs, n_fetched, gaps = 0, 0, 0, []
        while needs_repair(best["score"], tau) and iters < max_iters:
            iters += 1
            prev = best["score"]
            weak = [c.text for c in best["claims"] if needs_repair(c.confidence, tau)]
            candidates = []

            # Part 1 — reformulate the sub-query, re-query Exa, regenerate.
            new_q = reformulate(subq, weak, deps.generator)
            p1 = deps.search.search(new_q, k=RETRIEVAL_K).passages
            candidates.append({"claims": _synth_verify(query, subq, p1, deps, offset),
                               "passages": p1, "via": "reformulate"})

            # Part 2 — diversify: net-new URLs, fetched + combined with Exa passages.
            if recommender_llm is not None and fetcher is not None:
                cited = [getattr(pp, "url", "") for pp in best["passages"] if getattr(pp, "url", "")]
                recs = recommend_sources(subq, cited, weak, recommender_llm)
                fetched = fetcher.fetch_many([r["url"] for r in recs], subq)
                n_recs, n_fetched = len(recs), len(fetched)
                gaps = [r.get("kind", "") for r in recs]
                if fetched:
                    combined = list(best["passages"]) + fetched
                    candidates.append({"claims": _synth_verify(query, subq, combined, deps, offset),
                                       "passages": combined, "via": "diversify"})

            for cand in candidates:
                cand["score"] = _section_score(cand["claims"])
                if cand["score"] > best["score"]:
                    best = cand

            if not made_progress(prev, best["score"], eps):
                break

        for psg in best["passages"]:
            sources[psg.source_id] = psg
        all_claims.extend(best["claims"])
        if trace is not None:
            trace.append({"subq": subq, "iters": iters, "final_score": best["score"],
                          "via": best["via"], "n_recs": n_recs, "n_fetched": n_fetched,
                          "gaps": gaps})

    all_claims, contradictions = detect_and_resolve(all_claims, deps.contradiction_judge)
    return compose_report(query, p, all_claims, list(sources.values()), deps.generator,
                          with_verification=True, diagram_generator=deps.diagram_generator,
                          contradictions=contradictions)
