"""A/B experiment: does query decomposition improve retrieval?

For each brief test case, run retrieval arms with Exa highlights:
  A — no decomposition: one search on the full query.
  B — decomposition: plan() -> one search per sub-question.
Dump per-arm sub-questions, retrieved excerpts, unique-source counts, and
cross-arm source overlap to experiments/results/ for human inspection.

Staged, human-in-the-loop:
  Stage 1 (decomposition decision, budget fixed at 2k):
      python -m experiments.decomposition_retrieval
  Stage 2 (maxCharacters sweep for the chosen setting):
      python -m experiments.decomposition_retrieval charsweep            # decompose
      python -m experiments.decomposition_retrieval charsweep --no-decompose
"""
from __future__ import annotations

import json
import os

from dra.schemas import Passage

TEST_CASES = [
    ("tc1_straightforward",
     "What are the real-world risks and benefits of using synthetic data to train or "
     "fine-tune large language models? Focus on data quality, bias, and evaluation."),
    ("tc2_contradictory",
     "Is chain-of-thought prompting an effective reasoning strategy for LLMs, or does it "
     "primarily improve output formatting? The literature disagrees—find the real fault "
     "lines and explain what accounts for the conflicting results."),
    ("tc3_sparse",
     "What is the current state of inference-time compute scaling for LLM reasoning? "
     "Separate what has been empirically validated from what is still speculative, and "
     "identify where the evidence is too thin to draw conclusions."),
    ("tc4_multimodal",
     "Map the research landscape of multi-agent LLM systems. Produce a structured report "
     "that includes a visual taxonomy or design graph showing the major architectural "
     "patterns, how they relate, and where the open problems are."),
]

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
K = 8
DEFAULT_MAX_CHARS = 2000          # Stage 1 holds the excerpt budget here
SWEEP_BUDGETS = (1000, 2000, 4000)  # Stage 2 sweeps these


def unique_source_ids(passages) -> set:
    return {p.source_id for p in passages}


def overlap_stats(a_ids: set, b_ids: set) -> dict:
    shared = len(a_ids & b_ids)
    union = len(a_ids | b_ids)
    return {
        "only_a": len(a_ids - b_ids),
        "only_b": len(b_ids - a_ids),
        "shared": shared,
        "jaccard": (shared / union) if union else 0.0,
    }


def _passage_row(p: Passage) -> dict:
    return {"source_id": p.source_id, "url": p.url, "title": p.title,
            "score": p.score, "excerpt": p.text}


def _decompose(generator, query) -> list:
    from dra.planner import plan
    return plan(query, generator).subquestions or [query]


def run_ab(generator, search, cases=TEST_CASES, out_dir=None) -> dict:
    """Stage 1: Arm A (no decomposition) vs Arm B (decomposition) at a fixed excerpt budget.
    `generator` has complete_json; `search` is a SearchTool fixed at the Stage-1 budget."""
    out_dir = out_dir or os.path.join(RESULTS_DIR, "stage1_decomposition")
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    for case_id, query in cases:
        a_passages = search.search(query, k=K).passages            # Arm A — no decomposition
        subqs = _decompose(generator, query)                       # Arm B — decomposition
        b_by_subq = {sq: search.search(sq, k=K).passages for sq in subqs}
        b_passages = [p for ps in b_by_subq.values() for p in ps]
        a_ids, b_ids = unique_source_ids(a_passages), unique_source_ids(b_passages)
        result = {
            "query": query,
            "arm_a_no_decomposition": {
                "n_unique_sources": len(a_ids),
                "passages": [_passage_row(p) for p in a_passages],
            },
            "arm_b_decomposition": {
                "subquestions": subqs,
                "n_subquestions": len(subqs),
                "n_unique_sources": len(b_ids),
                "passages_by_subquestion": {
                    sq: [_passage_row(p) for p in ps] for sq, ps in b_by_subq.items()
                },
            },
            "overlap": overlap_stats(a_ids, b_ids),
        }
        report[case_id] = result
        with open(os.path.join(out_dir, f"{case_id}.json"), "w") as f:
            json.dump(result, f, indent=2)
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump({cid: {"n_subquestions": r["arm_b_decomposition"]["n_subquestions"],
                         "overlap": r["overlap"],
                         "arm_a_sources": r["arm_a_no_decomposition"]["n_unique_sources"],
                         "arm_b_sources": r["arm_b_decomposition"]["n_unique_sources"]}
                   for cid, r in report.items()}, f, indent=2)
    return report


def run_charsweep(generator, exa_factory, decompose: bool, cases=TEST_CASES,
                  budgets=SWEEP_BUDGETS, out_dir=None) -> dict:
    """Stage 2: for the chosen decomposition setting, sweep maxCharacters budgets.
    `exa_factory` is a callable max_chars -> SearchTool."""
    out_dir = out_dir or os.path.join(RESULTS_DIR, "stage2_charsweep")
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    for case_id, query in cases:
        queries = _decompose(generator, query) if decompose else [query]
        per_budget = {}
        for mc in budgets:
            search = exa_factory(mc)
            passages = [p for q in queries for p in search.search(q, k=K).passages]
            per_budget[str(mc)] = {
                "n_unique_sources": len(unique_source_ids(passages)),
                "total_excerpt_chars": sum(len(p.text) for p in passages),
                "passages": [_passage_row(p) for p in passages],
            }
        report[case_id] = {"query": query, "decompose": decompose,
                           "queries_used": queries, "by_max_chars": per_budget}
        with open(os.path.join(out_dir, f"{case_id}.json"), "w") as f:
            json.dump(report[case_id], f, indent=2)
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump({cid: {str(mc): {
                            "n_unique_sources": r["by_max_chars"][str(mc)]["n_unique_sources"],
                            "total_excerpt_chars": r["by_max_chars"][str(mc)]["total_excerpt_chars"]}
                         for mc in budgets}
                   for cid, r in report.items()}, f, indent=2)
    return report


def main(argv=None):  # pragma: no cover - live path
    import sys
    from dra.config import load_config
    from dra.llm.bedrock import BedrockChat
    from dra.search.exa import ExaSearch

    argv = argv if argv is not None else sys.argv[1:]
    cfg = load_config()
    region = os.environ.get("AWS_REGION", "us-east-1")
    generator = BedrockChat(cfg.roles["generator"], region=region)
    exa_factory = lambda mc: ExaSearch(cfg.exa_key, max_chars=mc)

    if argv and argv[0] == "charsweep":
        decompose = "--no-decompose" not in argv  # default: decompose
        run_charsweep(generator, exa_factory, decompose=decompose)
        print("Wrote char-sweep results to experiments/results/stage2_charsweep/")
    else:
        run_ab(generator, exa_factory(DEFAULT_MAX_CHARS))
        print("Wrote A/B results to experiments/results/stage1_decomposition/")


if __name__ == "__main__":  # pragma: no cover
    main()
