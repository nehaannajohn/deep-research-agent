"""Report-composition validation run: for the brief cases, generate reports in a PLAIN arm
and a FORMAT-AUGMENTED arm (a diagram instruction added), in unverified/baseline mode, with
the two follow-up features wired in — the dedicated diagram generator (always) and the
contradiction layer (optional via --contradictions; judging all claim pairs on topic-coherent
reports is call-heavy, so it's off by default). Cases run in parallel. For manual
instruction-adherence inspection: does the augmented arm produce a detailed, relevant diagram
that the plain arm lacks?

Live: needs AWS creds + EXA_API_KEY. Run: .venv/bin/python -m experiments.report_generation
Writes experiments/results/reports/<case>_{plain,augmented}.md
"""
from __future__ import annotations

DIAGRAM_INSTRUCTION = " Include an architecture diagram of the relevant pipeline or process."


def augment_query(query: str) -> str:
    return query.rstrip().rstrip(".") + "." + DIAGRAM_INSTRUCTION


def _diagram_size(md: str) -> int:
    """Non-empty lines inside the report's first ```mermaid block (a richness proxy)."""
    if "```mermaid" not in md:
        return 0
    body = md.split("```mermaid", 1)[1].split("```", 1)[0]
    return len([ln for ln in body.splitlines() if ln.strip()])


def main(argv=None):  # pragma: no cover - live path
    import argparse
    import json
    import os
    from concurrent.futures import ThreadPoolExecutor

    from dra.config import load_config
    from dra.contradiction import PairContradictionJudge, detect_and_resolve
    from dra.diagram import LLMDiagramGenerator
    from dra.llm.bedrock import BedrockChat
    from dra.planner import plan
    from dra.report import compose_report
    from dra.search import default_search_tool
    from dra.synthesis import synthesize
    from experiments.decomposition_retrieval import RESULTS_DIR, TEST_CASES

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="limit number of cases (0 = all)")
    ap.add_argument("--contradictions", action="store_true",
                    help="also run the (call-heavy) contradiction layer; off by default")
    args = ap.parse_args(argv)

    cfg = load_config()
    region = os.environ.get("AWS_REGION", "us-east-1")
    gen = BedrockChat(cfg.roles["generator"], region=region)
    search = default_search_tool(cfg)  # cached Exa
    diagram_gen = LLMDiagramGenerator(
        BedrockChat(cfg.roles.get("diagram") or cfg.roles["generator"], region=region))
    judge_model = cfg.verifier_models[0] if cfg.verifier_models else cfg.roles["inloop_judge"]
    contradiction_judge = (PairContradictionJudge(BedrockChat(judge_model, region=region))
                           if args.contradictions else None)
    out_dir = os.path.join(RESULTS_DIR, "reports")
    os.makedirs(out_dir, exist_ok=True)

    def build(query):
        # unverified/baseline mode (no grounding verifier), but WITH the dedicated diagram
        # generator (and the contradiction layer when --contradictions) — the features under test.
        p = plan(query, gen)
        claims = []
        sources = {}
        for sq in p.subquestions:
            passages = search.search(sq, k=5).passages
            for psg in passages:
                sources[psg.source_id] = psg
            try:
                claims.extend(synthesize(query, sq, passages, gen, start_index=len(claims)))
            except Exception:
                pass
        claims, contradictions = detect_and_resolve(claims, contradiction_judge)
        rep = compose_report(query, p, claims, list(sources.values()), gen,
                             with_verification=False, diagram_generator=diagram_gen,
                             contradictions=contradictions)
        return p, rep, contradictions

    def run_case(case):
        case_id, query = case
        p_plain, rep_plain, c_plain = build(query)
        p_aug, rep_aug, c_aug = build(augment_query(query))
        with open(os.path.join(out_dir, f"{case_id}_plain.md"), "w") as f:
            f.write(rep_plain.report_markdown)
        with open(os.path.join(out_dir, f"{case_id}_augmented.md"), "w") as f:
            f.write(rep_aug.report_markdown)
        return case_id, {
            "subquestions_match": p_plain.subquestions == p_aug.subquestions,
            "augmented_wants_visual": bool((p_aug.constraints or {}).get("wants_visual")),
            "augmented_has_mermaid": "```mermaid" in rep_aug.report_markdown,
            "augmented_diagram_lines": _diagram_size(rep_aug.report_markdown),
            "plain_has_mermaid": "```mermaid" in rep_plain.report_markdown,
            "contradictions_plain": len(c_plain),
            "contradictions_augmented": len(c_aug),
        }

    cases = TEST_CASES[:args.limit] if args.limit else TEST_CASES
    print(f"Generating {len(cases)} case(s) x (plain, augmented) in parallel "
          f"(diagram=on, contradictions={'on' if args.contradictions else 'off'}) ...")
    summary = {}
    with ThreadPoolExecutor(max_workers=max(1, len(cases))) as pool:
        for case_id, s in pool.map(run_case, cases):
            summary[case_id] = s
            print(f"{case_id}: subq_match={s['subquestions_match']} "
                  f"mermaid plain/aug={s['plain_has_mermaid']}/{s['augmented_has_mermaid']} "
                  f"diagram_lines={s['augmented_diagram_lines']} "
                  f"contradictions(p/a)={s['contradictions_plain']}/{s['contradictions_augmented']}")
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote reports + summary to {out_dir}/ — inspect *_plain.md vs *_augmented.md")


if __name__ == "__main__":  # pragma: no cover
    main()
