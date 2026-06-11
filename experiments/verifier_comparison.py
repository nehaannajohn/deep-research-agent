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


def main():
    raise NotImplementedError(
        "Live orchestration is implemented in a later task; this documents the flow:\n"
        "1) load_config(); build generator (construction) + 3 verifier candidates from "
        "cfg.verifier_models + the EnsembleVerifier + the panel from cfg.panel_models.\n"
        "2) For the 4 brief cases: retrieve (cached Exa) + generate claims; build supported/"
        "refuted/insufficient/contested examples using the prompts above; tag intended labels.\n"
        "3) Validate each example with the panel (_VALIDATE); keep those where "
        "passed_validation(panel_labels, intended) is True.\n"
        "4) Run each verifier over the kept bench; collect label/reasoning/recommendation/"
        "confidence/cost/latency.\n"
        "5) Score with macro_f1(intended, predicted) per candidate + panel _QUALITY means + cost; "
        "write experiments/results/verifier/{per_case.json, summary.json}.")


if __name__ == "__main__":
    main()
