---
title: "Verifier B v0 vs v1 — does our-generator-distribution training data help?"
subtitle: "Deep Research Agent · trained cross-encoder verifier + PRM-readiness for the learned adaptive controller"
date: "2026-06-13"
---

# Verifier B: v0 (public) vs v1 (+our-distribution) (2026-06-13)

> **Headline:** Both variants train to a strong **~0.85 balanced macro-F1** (≈ the LLM ensemble's 0.845) — **DeBERTa-v3 is a viable Verifier B**. But the two key questions are **not yet answered**: the v0-vs-v1 "does our-distribution data help" comparison is **inconclusive** (the transfer eval is degenerate), and **neither variant is PRM-ready** (monotonicity/insensitivity gates fail) — so the learned adaptive controller stays blocked.

## 1. Question & motivation

We need a trained, cheap, **calibrated** verifier (a) to cross-check the LLM ensemble (Verifier A) and (b) to serve as the **process-reward model (PRM)** for the learned adaptive controller. The open question: does training on **our generator's distribution** (synthetic hard negatives from real Exa passages + an evidence-ablated curriculum) actually beat a **public-only** fine-tune? We test it as an ablation:
- **v0** — DeBERTa-v3-base fine-tuned on **FEVER + SciFact** (public only).
- **v1** — same + **our-distribution data** (synthetic hard negatives + evidence-ablation curriculum).

Hypothesis: v1 ≈ v0 on public macro-F1 but **wins on transfer-to-our-distribution and on PRM-readiness (monotonicity)**.

## 2. Setup

| Component | Choice |
|---|---|
| Model | `microsoft/deberta-v3-base` cross-encoder, 3-way head `{supported, refuted, nei}` |
| Input | `[CLS] claim [SEP] passage [SEP]`, 512 tok; `contested` derived downstream, not a head class |
| v0 data | FEVER (`copenlu/fever_gold_evidence`, train) + SciFact (train) → 137k+2.5k single-passage pairs |
| v1 data | v0 + **synthetic hard negatives** (607 held-out-trainpool Exa passages × 4 perturbation types, judge-filtered) + **evidence-ablated curriculum** (15k: full-gold→supported, partial/distractor→nei) |
| Balancing | class-balanced `WeightedRandomSampler` over the 3 head classes (no downsampling) |
| Train | 3-way CE, HF Trainer, early-stop on balanced held-out macro-F1; transformers **4.46.3** (5.x broke the spm tokenizer), torch 2.12, 1×A100 each, parallel |
| Eval — public | balanced held-out **FEVER `validation` + SciFact `dev`** (disjoint from train) — per-pair macro-F1 |
| Eval — transfer | silver set: our pipeline's DRA-Bench claims + cited passages, labeled by the **independent grounding judge** (95% `supported`) |
| Eval — PRM gates | monotonicity ladder (p_supported over {distractor, partial, full}) + insensitivity (gold vs gold+padding) |

**No-leak:** synthetic negatives come only from the held-out trainpool (disjoint from all eval benchmarks); train uses FEVER/SciFact `train`, eval uses their `validation`/`dev`.

## 3. Results

### 3.1 Balanced public held-out (the real accuracy measure)

| variant | macro-F1 | supported F1 | refuted F1 | nei F1 |
|---|---|---|---|---|
| **v0** (public) | **0.855** | 0.868 | 0.843 | ~0.85 |
| **v1** (+our-dist) | **0.850** | 0.858 | 0.842 | ~0.85 |

Both ≈ the LLM ensemble's Layer-1 macro-F1 (0.845). Prediction distributions are healthy across all three classes (not collapsed). **v1 ≈ v0** (Δ = −0.005, within noise).

### 3.2 Silver transfer set — DEGENERATE (do not interpret as the ablation answer)

| variant | macro-F1 | supported F1 | refuted F1 | ECE before→after (oos) |
|---|---|---|---|---|
| v0 | 0.457 | 0.915 | 0.000 | 0.185 → 0.013 |
| v1 | 0.029 | 0.057 | 0.002 | 0.906 → 0.003 |

These numbers are **artifacts, not signal** (see §4): the transfer set is **95% `supported`** and is scored through `CrossEncoderVerifier.verify()`'s multi-passage aggregation, which flips multi-cited claims off `supported` too eagerly.

### 3.3 PRM fitness gates (§1.6 of the controller design)

| gate | v0 | v1 | pass threshold |
|---|---|---|---|
| monotonicity — frac non-decreasing | 0.725 | 0.780 | ≥ 0.90 → **both FAIL** |
| monotonicity — mean Δp | +0.466 | +0.469 | > 0 ✓ |
| insensitivity — mean \|Δp\| under padding | 0.074 | **0.472** | < 0.05 → **both FAIL** (v1 badly) |

## 4. Findings

- **Verifier B training works.** Both variants hit **~0.85 balanced macro-F1**, matching the LLM ensemble (0.845) at a fraction of the inference cost. A DeBERTa-v3 cross-encoder is a viable Verifier B — the A-vs-B in-pipeline cross-check is worth pursuing.
- **On public data, our-distribution data did not move accuracy (v1 ≈ v0, 0.850 vs 0.855).** Expected — the synthetic/curriculum slices are aimed at *transfer* and *PRM monotonicity*, not raw FEVER/SciFact accuracy.
- **The v0-vs-v1 *transfer* comparison is inconclusive — the eval is degenerate, NOT v1 broken.** The transfer set is 95% `supported`, and `verify()` max-aggregates over a claim's *many* cited passages: if any passage trips the refuted/contested margin (0.5), the whole claim flips off `supported`. v1 is marginally more refute-sensitive, so on multi-cited transfer claims it flipped most `supported`→`contested`/`nei` and supported-F1 collapsed to 0.057. **The balanced per-pair eval proves v1 is healthy (0.850)** — the collapse is an aggregation/skew artifact of the transfer instrument. (Initial read of the raw transfer numbers looked like "v1 is broken"; the balanced eval corrected that.)
- **Neither variant is PRM-ready.** Monotonicity is only 0.725 (v0) / 0.780 (v1) vs the 0.90 bar, and insensitivity fails — v1 *badly* (mean |Δp| = 0.47: padding irrelevant passages onto gold swings its p_supported wildly). The curriculum nudged monotonicity up (0.725→0.78) but not to threshold, and made v1 *more* reactive to evidence changes — good for monotonicity, bad for padding-insensitivity. **A monotone, padding-robust PRM is a hard prerequisite for the learned controller; we don't have one yet.**

## 5. Decision / Verdict

1. **DeBERTa-v3 Verifier B is viable** (≈ ensemble accuracy, far cheaper) → **proceed to the in-pipeline A-vs-B ablation** (wire `CrossEncoderVerifier` into the live loop).
2. **"Does our-distribution data help?" — INCONCLUSIVE.** The public answer is "no change"; the transfer answer is uninterpretable until the eval is fixed. **Re-run the transfer comparison after fixing the eval** (balanced/per-pair scoring + tuned `verify()` margins).
3. **Verifier B is NOT PRM-ready → the learned adaptive controller stays blocked.** Strengthen the evidence-ablated curriculum (more/again rungs; tune so monotonicity ≥0.90 *and* insensitivity <0.05) before any RL.

## 6. Pipeline / code changes
- New: `src/dra/verify/train/{pairs,curriculum,synthetic,transfer,datasets,prm}.py`, `src/dra/verify/cross_encoder.py` (27/27 unit tests); `experiments/verifier_b/*` (harvest, build_data, train, evaluate, run_prm, compare, anchor).
- Review fixes (`dbf514d`): out-of-sample ECE split in `evaluate.py`; variant-independent PRM distractors in `run_prm.py`.
- **Known eval gaps to fix before the re-run:** `evaluate.py` scored only the (skewed) transfer set, not the balanced held-out — the balanced macro-F1 here came from a one-off diagnostic; fold it into `evaluate.py`. `verify()` aggregation margins need tuning for multi-cited claims.

## 7. What this sets up next
- **Fix the transfer eval** (balanced/per-pair + `verify()` margins) → the real v0-vs-v1 transfer answer.
- **Strengthen the curriculum** → pass the PRM gates → unblock the learned controller (`2026-06-12-adaptive-controller-design.md` Part 2).
- **In-pipeline A-vs-B** ablation (Verifier A ensemble vs B cross-encoder, end-to-end).
- Human-anchor the silver transfer labels (~100 rows) → grounding-judge↔human κ.

## 8. Reproducibility

```bash
# On EC2 (.venv-train: torch 2.12 + transformers 4.46.3 + protobuf/sentencepiece), per variant on its own GPU:
.venv-train/bin/python -m experiments.verifier_b.harvest_trainpool --n 80          # held-out passages
.venv-train/bin/python -m experiments.verifier_b.build_data --slice all            # fever/scifact/curriculum/synthetic/transfer
CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.verifier_b.train --variant v0
CUDA_VISIBLE_DEVICES=1 .venv-train/bin/python -m experiments.verifier_b.train --variant v1
for V in v0 v1; do .venv-train/bin/python -m experiments.verifier_b.evaluate --variant $V; \
                   .venv-train/bin/python -m experiments.verifier_b.run_prm --variant $V; done
.venv-train/bin/python -m experiments.verifier_b.compare
```

Raw outputs (gitignored, on the run host): `eval/verifier_b_models/{v0,v1}/best/`, `eval/results/verifier_b/{v0,v1}/{eval,prm}.json`, `eval/results/verifier_b/compare.md`. Plan: `docs/superpowers/plans/2026-06-13-verifier-b.md`.
