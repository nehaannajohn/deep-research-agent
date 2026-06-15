"""Verifier-selection experiment: construct adversarial (claim, passages) examples
with ground-truth labels, validate them with the judge panel, run each verifier
candidate (Sonnet / Mistral / Nova solo + the 3-model ensemble), and score
per-class F1 + panel-rated quality + cost. Mirrors generator_comparison.py.

Run live: `.venv/bin/python -m experiments.verifier_comparison`
(needs AWS creds + EXA_API_KEY; writes experiments/results/verifier/).
"""
from __future__ import annotations

from collections import Counter

LABELS = ("supported", "refuted", "insufficient", "contested")


def macro_f1(y_true: list[str], y_pred: list[str]) -> dict:
    """Per-class precision/recall/F1 over LABELS + unweighted macro-F1.

    macro-F1 averages only over classes that actually appear in y_true."""
    per_class = {}
    f1s = []
    for lab in LABELS:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
        if (tp + fn) > 0:
            f1s.append(f1)
    return {"per_class": per_class, "macro_f1": sum(f1s) / len(f1s) if f1s else 0.0}


def passed_validation(panel_labels: list[str], intended: str, threshold: int = 2) -> bool:
    """Keep an adversarial example only if >= threshold panel judges assign the intended label."""
    return Counter(panel_labels)[intended] >= threshold


# --- Adversarial construction prompts (construction model = the Llama generator) ---
_REFUTE = ("Rewrite the CLAIM so it directly CONTRADICTS the passage below, staying on the "
           "same topic. Output ONLY the rewritten claim.\n\nCLAIM: {claim}\n\nPASSAGE: {passage}")
_CONTEST = ("Write a short, plausible PASSAGE (2-3 sentences) that REFUTES the claim below, as if "
            "from a credible source. Output ONLY the passage text.\n\nCLAIM: {claim}")
# `insufficient` uses a real, topically-related passage from another sub-question's pool
# (retrieved, not synthetic). `supported` reuses the claim with its original supporting passage.

# --- Panel validation + quality prompts ---
_VALIDATE = ("Given the PASSAGES and the CLAIM, what is the correct label "
             "(supported/refuted/insufficient/contested)? Answer ONLY JSON {{\"label\": \"...\"}}.\n\n"
             "CLAIM: {claim}\n\nPASSAGES:\n{passages}")
_QUALITY = ("Rate 1-5 how sound this verifier's reasoning and recommendation are for the verdict.\n"
            "Answer ONLY JSON {{\"reasoning_score\": 1-5, \"recommendation_score\": 1-5}}.\n\n"
            "CLAIM: {claim}\nVERDICT: {label}\nREASONING: {reasoning}\nRECOMMENDATION: {recommendation}")


def _mean(xs):
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def _short_model(m: str) -> str:
    for key in ("sonnet", "mistral", "nova", "haiku", "opus", "gpt-oss", "deepseek", "llama"):
        if key in m:
            return key.replace("-", "_")
    return m.split(".")[-1][:12]


def _render(passages) -> str:
    return "\n".join(f"[{p.source_id}] {p.text}" for p in passages)


def _panel_label(judge, claim, passages) -> str:
    """One judge's label for (claim, passages); parse failures degrade to insufficient."""
    try:
        d = judge.complete_json(_VALIDATE.format(claim=claim, passages=_render(passages)))
        lab = d.get("label") if isinstance(d, dict) else None
        return lab if lab in LABELS else "insufficient"
    except Exception:
        return "insufficient"


def _other_passage(pool, cited):
    """A real retrieved passage not among `cited` — for `insufficient` pairing."""
    cited_ids = {p.source_id for p in cited}
    for p in pool:
        if p.source_id not in cited_ids:
            return p
    return None


def build_bench(generator, search, cases, claims_per_case):
    """Construct adversarial (claim, passages) examples each tagged with an intended label:
    supported (claim + its citations), refuted (claim rewritten to contradict its citation),
    insufficient (claim + an unrelated real passage), contested (citations + a synthetic refuter)."""
    from dra.schemas import Passage
    from dra.synthesis import synthesize
    from experiments.code.decomposition_retrieval import _decompose

    pool = []   # all retrieved passages (for `insufficient` pairing)
    base = []   # (case_id, query, cited-claims)
    for case_id, query in cases:
        claims = []
        for sq in _decompose(generator, query):
            passages = search.search(sq, k=5).passages
            pool.extend(passages)
            try:
                claims.extend(synthesize(query, sq, passages, generator, start_index=len(claims)))
            except Exception:
                pass
        base.append((case_id, query, [c for c in claims if c.citations][:claims_per_case]))

    examples = []
    for case_id, query, claims in base:
        for c in claims:
            cited = [Passage(source_id=cit.source_id, text=cit.span) for cit in c.citations]
            if not cited:
                continue
            examples.append({"case": case_id, "intended": "supported", "claim": c.text, "passages": cited})
            try:
                refuted = generator.complete(_REFUTE.format(claim=c.text, passage=cited[0].text)).strip()
                if refuted:
                    examples.append({"case": case_id, "intended": "refuted", "claim": refuted, "passages": cited})
            except Exception:
                pass
            other = _other_passage(pool, cited)
            if other is not None:
                examples.append({"case": case_id, "intended": "insufficient", "claim": c.text, "passages": [other]})
            try:
                refute_text = generator.complete(_CONTEST.format(claim=c.text)).strip()
                if refute_text:
                    examples.append({"case": case_id, "intended": "contested", "claim": c.text,
                                     "passages": cited + [Passage(source_id="synthetic_refute", text=refute_text)]})
            except Exception:
                pass
    return examples


def validate_bench(examples, judges, threshold=2):
    """Keep only examples the panel agrees match their intended label (>= threshold judges)."""
    kept = []
    for ex in examples:
        labels = [_panel_label(j, ex["claim"], ex["passages"]) for j in judges.values()]
        ex["panel_labels"] = labels
        if passed_validation(labels, ex["intended"], threshold):
            kept.append(ex)
    return kept


def _quality_scores(judges, preds):
    """Panel rates reasoning + recommendation soundness (1-5) for each prediction."""
    rs, recs = [], []
    for p in preds:
        for j in judges.values():
            try:
                d = j.complete_json(_QUALITY.format(claim=p["claim"], label=p["pred"],
                                                    reasoning=p["reasoning"], recommendation=p["recommendation"]))
                if isinstance(d, dict):
                    rs.append(max(1, min(5, int(d.get("reasoning_score", 0) or 0))))
                    recs.append(max(1, min(5, int(d.get("recommendation_score", 0) or 0))))
            except Exception:
                pass
    return {"mean_reasoning": _mean(rs), "mean_recommendation": _mean(recs), "n": len(rs)}


def evaluate(candidates, kept, judges):
    """Run each verifier over the validated bench; score macro-F1 + panel quality + latency."""
    import time
    results = {}
    for name, verifier in candidates.items():
        y_true, y_pred, preds = [], [], []
        t0 = time.monotonic()
        for ex in kept:
            try:
                r = verifier.verify(ex["claim"], ex["passages"])
            except Exception:
                continue  # skip a pathological example rather than abort the whole eval
            y_true.append(ex["intended"])
            y_pred.append(r.label)
            preds.append({"case": ex["case"], "intended": ex["intended"], "claim": ex["claim"],
                          "pred": r.label, "confidence": r.confidence,
                          "recommendation": r.recommendation, "reasoning": r.reasoning, "votes": r.votes})
        elapsed = round(time.monotonic() - t0, 1)
        scores = macro_f1(y_true, y_pred)
        results[name] = {"macro_f1": scores["macro_f1"], "per_class": scores["per_class"],
                         "n_examples": len(kept), "latency_s_total": elapsed,
                         "quality": _quality_scores(judges, preds), "preds": preds}
    return results


def main(argv=None):  # pragma: no cover - live path
    import argparse
    import json
    import os

    from dra.config import load_config
    from dra.llm.bedrock import BedrockChat
    from dra.search import default_search_tool
    from dra.verify.ensemble import EnsembleVerifier
    from dra.verify.llm_judge import LLMJudgeVerifier
    from experiments.code.decomposition_retrieval import RESULTS_DIR, TEST_CASES

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="limit number of cases (0 = all 4)")
    ap.add_argument("--claims-per-case", type=int, default=4)
    ap.add_argument("--samples", type=int, default=5, help="self-consistency samples for solo verifiers")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    cfg = load_config()
    region = os.environ.get("AWS_REGION", "us-east-1")
    generator = BedrockChat(cfg.roles["generator"], region=region)
    search = default_search_tool(cfg)  # cached Exa
    judges = {_short_model(m): BedrockChat(m, region=region) for m in cfg.panel_models}
    solo = {_short_model(m): LLMJudgeVerifier(BedrockChat(m, region=region), n_samples=args.samples)
            for m in cfg.verifier_models}
    ensemble = EnsembleVerifier([LLMJudgeVerifier(BedrockChat(m, region=region), n_samples=1)
                                 for m in cfg.verifier_models])
    candidates = {**solo, "ensemble": ensemble}

    cases = TEST_CASES[:args.limit] if args.limit else TEST_CASES
    print(f"[1/3] building bench: {len(cases)} case(s), claims_per_case={args.claims_per_case}")
    examples = build_bench(generator, search, cases, args.claims_per_case)
    print(f"      constructed {len(examples)} examples; validating with {len(judges)}-judge panel")
    kept = validate_bench(examples, judges)
    print(f"[2/3] kept {len(kept)}/{len(examples)} after validation gate")
    if not kept:
        print("      no validated examples — aborting")
        return
    print(f"[3/3] evaluating {len(candidates)} candidates ({', '.join(candidates)}) over {len(kept)} examples")
    results = evaluate(candidates, kept, judges)

    out_dir = args.out or os.path.join(RESULTS_DIR, "verifier")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "bench.json"), "w") as f:
        json.dump([{k: ex[k] for k in ("case", "intended", "panel_labels", "claim")} for ex in kept],
                  f, indent=2)
    summary = {}
    for name, r in results.items():
        with open(os.path.join(out_dir, f"{name}.json"), "w") as f:
            json.dump(r["preds"], f, indent=2)
        summary[name] = {k: r[k] for k in ("macro_f1", "per_class", "n_examples", "latency_s_total", "quality")}
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== summary (experiments/results/verifier/) ===")
    for name, s in summary.items():
        print(f"  {name:14s} macro_f1={s['macro_f1']:.3f}  latency={s['latency_s_total']}s  "
              f"quality(reason/rec)={s['quality']['mean_reasoning']}/{s['quality']['mean_recommendation']}")


if __name__ == "__main__":  # pragma: no cover
    main()
