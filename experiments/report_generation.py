"""Report-composition validation run: for the 4 brief cases, generate reports in a
PLAIN arm and a FORMAT-AUGMENTED arm (a diagram instruction added), in unverified/
baseline mode, for manual instruction-adherence inspection. The format instruction is
routed through the planner into plan.constraints, so retrieval (sub-questions) is
identical across arms — the script reports whether they matched (a planner-routing check).

Live: needs AWS creds + EXA_API_KEY. Run: .venv/bin/python -m experiments.report_generation
Writes experiments/results/reports/<case>_{plain,augmented}.md
"""
from __future__ import annotations

DIAGRAM_INSTRUCTION = " Include an architecture diagram of the relevant pipeline or process."


def augment_query(query: str) -> str:
    return query.rstrip().rstrip(".") + "." + DIAGRAM_INSTRUCTION


def main():  # pragma: no cover - live path
    import json
    import os

    from dra.config import load_config
    from dra.llm.bedrock import BedrockChat
    from dra.planner import plan
    from dra.report import compose_report
    from dra.search import default_search_tool
    from dra.synthesis import synthesize
    from experiments.decomposition_retrieval import RESULTS_DIR, TEST_CASES

    cfg = load_config()
    region = os.environ.get("AWS_REGION", "us-east-1")
    gen = BedrockChat(cfg.roles["generator"], region=region)
    search = default_search_tool(cfg)  # cached Exa
    out_dir = os.path.join(RESULTS_DIR, "reports")
    os.makedirs(out_dir, exist_ok=True)

    def build(query):
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
        return p, compose_report(query, p, claims, list(sources.values()), gen)  # unverified baseline mode

    summary = {}
    for case_id, query in TEST_CASES:
        p_plain, rep_plain = build(query)
        p_aug, rep_aug = build(augment_query(query))
        with open(os.path.join(out_dir, f"{case_id}_plain.md"), "w") as f:
            f.write(rep_plain.report_markdown)
        with open(os.path.join(out_dir, f"{case_id}_augmented.md"), "w") as f:
            f.write(rep_aug.report_markdown)
        summary[case_id] = {
            "subquestions_match": p_plain.subquestions == p_aug.subquestions,
            "augmented_wants_visual": bool((p_aug.constraints or {}).get("wants_visual")),
            "augmented_has_mermaid": "```mermaid" in rep_aug.report_markdown,
        }
        print(f"{case_id}: subq_match={summary[case_id]['subquestions_match']} "
              f"wants_visual={summary[case_id]['augmented_wants_visual']} "
              f"mermaid={summary[case_id]['augmented_has_mermaid']}")
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote reports + summary to {out_dir}/ — inspect *_plain.md vs *_augmented.md")


if __name__ == "__main__":  # pragma: no cover
    main()
