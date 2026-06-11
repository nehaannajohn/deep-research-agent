"""Generator-model comparison experiment.

Which model should play the GENERATOR role (query decomposition + claim generation)?
Compares Mistral Large 3, Llama 4 Maverick, and Haiku 4.5 on decompose + claim-gen across
8 cases, holding retrieval fixed (Exa, k=5, maxChars=2k). Each claim is scored by a 3-judge
panel (GPT-OSS 120B, Opus 4.8, DeepSeek R1) for atomicity + grounding; reports per-judge
means and a panel mean.

Verdict (see docs/experiments findings): Llama 4 Maverick wins — best-grounded, most atomic,
most concise; unanimous across the panel. It is now the generator; Mistral moved to the
in-loop verifier role.

Run live:  python -m experiments.generator_comparison
Outputs:   experiments/results/generator_comparison/{model}.json + summary.json
"""
from __future__ import annotations

import json
import os

from experiments.decomposition_retrieval import (
    DEFAULT_MAX_CHARS,
    RESULTS_DIR,
    TEST_CASES,
    _decompose,
)

GENERATOR_MODELS = {
    "mistral_large_3": "mistral.mistral-large-3-675b-instruct",
    "llama4_maverick": "us.meta.llama4-maverick-17b-instruct-v1:0",
    "haiku_4_5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
}

# The 4 brief cases + 4 additional diverse research prompts (technical / general-science /
# contradictory / emerging) for a larger, less brief-specific sample.
GEN_TEST_CASES = TEST_CASES + [
    ("tc5_rag_hallucination",
     "How effective is retrieval-augmented generation at reducing hallucination in large "
     "language models, and what are its main failure modes?"),
    ("tc6_ultraprocessed_foods",
     "What is the current scientific consensus on the health effects of ultra-processed "
     "foods, and where is the evidence still contested?"),
    ("tc7_remote_productivity",
     "Does remote work increase or decrease software-engineering productivity? Reconcile the "
     "conflicting evidence and explain what drives the disagreement."),
    ("tc8_moe_vs_dense",
     "At a fixed compute budget, how do mixture-of-experts architectures compare to dense "
     "transformer models for large language models?"),
]


def _mean(xs):
    return round(sum(xs) / len(xs), 3) if xs else 0.0


_GEN_JUDGE_PROMPT = """You are scoring the QUALITY of atomic claims extracted by a research agent.
For EACH numbered claim, rate two things:
- atomicity: 1 if the claim states exactly ONE checkable assertion; 0 if it bundles several.
- grounding: does the EVIDENCE support the claim? 0 = not supported, 1 = partial, 2 = full.
Return ONLY JSON: {{"scores": [{{"atomicity": 0|1, "grounding": 0|1|2}}, ...]}}
with one entry per claim, in the SAME ORDER as listed.

CLAIMS:
{block}"""


def _judge_claims_batch(judge, claims) -> list:
    """Judge ONE small batch of claims; `judged=False` marks parse/JSON failures so they
    can be excluded from means (rather than silently scored 0)."""
    lines = []
    for i, c in enumerate(claims, 1):
        evidence = " ".join(cit.span for cit in c.citations)[:600]
        lines.append(f"{i}. CLAIM: {c.text}\n   EVIDENCE: {evidence}")
    try:
        d = judge.complete_json(_GEN_JUDGE_PROMPT.format(block="\n".join(lines)))
        scores = d.get("scores", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
        out = []
        for s in scores[:len(claims)]:
            s = s if isinstance(s, dict) else {}
            out.append({"atomicity": 1 if int(s.get("atomicity", 0)) >= 1 else 0,
                        "grounding": max(0, min(2, int(s.get("grounding", 0)))), "judged": True})
        while len(out) < len(claims):  # judge returned fewer than asked → mark unjudged
            out.append({"atomicity": 0, "grounding": 0, "judged": False})
        return out
    except Exception:
        return [{"atomicity": 0, "grounding": 0, "judged": False} for _ in claims]


def _judge_claims(judge, claims, batch=12) -> list:
    """Chunk claims into small batches so the judge's input+output JSON stays reliable
    (large single-call batches truncate and fail). Returns scores aligned to `claims`."""
    out = []
    for start in range(0, len(claims), batch):
        out.extend(_judge_claims_batch(judge, claims[start:start + batch]))
    return out


def run_generator_comparison(generators, search, judges, cases=GEN_TEST_CASES, out_dir=None) -> dict:
    """Compare candidate generators on the full generator role (decompose + claim-gen),
    holding retrieval (search, k=5/2k) fixed. Each claim is scored by a PANEL of judges
    (`judges` = {name: BedrockChat}) for atomicity + grounding; report per-judge means and a
    panel mean (mean of judge means). `generators` = {name: BedrockChat}."""
    from dra.synthesis import synthesize

    out_dir = out_dir or os.path.join(RESULTS_DIR, "generator_comparison")
    os.makedirs(out_dir, exist_ok=True)
    summary = {}
    for name, gen in generators.items():
        per_case = {}
        judge_atom = {j: [] for j in judges}   # judged-claim scores across all cases, per judge
        judge_ground = {j: [] for j in judges}
        total_claims = 0
        synth_failures = 0  # sub-questions whose claim JSON failed to parse (e.g. output truncation)
        for case_id, query in cases:
            subqs = _decompose(gen, query)
            claims = []
            for sq in subqs:
                passages = search.search(sq, k=5).passages  # settled k
                try:
                    claims.extend(synthesize(query, sq, passages, gen, start_index=len(claims)))
                except Exception:
                    synth_failures += 1  # skip this sub-question; don't kill the whole run
            total_claims += len(claims)
            case_by_judge = {}
            for jname, j in judges.items():
                sc = _judge_claims(j, claims)
                a = [s["atomicity"] for s in sc if s["judged"]]
                g = [s["grounding"] for s in sc if s["judged"]]
                judge_atom[jname] += a
                judge_ground[jname] += g
                case_by_judge[jname] = {"n_judged": len(a),
                                        "mean_atomicity": _mean(a), "mean_grounding": _mean(g)}
            per_case[case_id] = {"n_subquestions": len(subqs), "n_claims": len(claims),
                                 "by_judge": case_by_judge}
        by_judge = {jn: {"n_judged": len(judge_atom[jn]),
                         "mean_atomicity": _mean(judge_atom[jn]),
                         "mean_grounding": _mean(judge_ground[jn])} for jn in judges}
        summary[name] = {
            "total_claims": total_claims,
            "synth_failures": synth_failures,
            "by_judge": by_judge,
            "panel_mean_atomicity": _mean([by_judge[jn]["mean_atomicity"] for jn in judges]),
            "panel_mean_grounding": _mean([by_judge[jn]["mean_grounding"] for jn in judges]),
        }
        with open(os.path.join(out_dir, f"{name}.json"), "w") as f:
            json.dump(per_case, f, indent=2)
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def main(argv=None):  # pragma: no cover - live path
    from dra.config import load_config
    from dra.llm.bedrock import BedrockChat
    from dra.search.exa import ExaSearch

    cfg = load_config()
    region = os.environ.get("AWS_REGION", "us-east-1")
    exa = ExaSearch(cfg.exa_key, max_chars=DEFAULT_MAX_CHARS)

    def _short(m):
        for key in ("gpt-oss", "opus", "deepseek"):
            if key in m:
                return key.replace("-", "_")
        return m.split(".")[-1][:12]

    judges = {_short(m): BedrockChat(m, region=region) for m in cfg.panel_models}  # 3-judge panel
    gens = {name: BedrockChat(mid, region=region) for name, mid in GENERATOR_MODELS.items()}
    run_generator_comparison(gens, exa, judges)
    print("Wrote generator comparison to experiments/results/generator_comparison/")


if __name__ == "__main__":  # pragma: no cover
    main()
