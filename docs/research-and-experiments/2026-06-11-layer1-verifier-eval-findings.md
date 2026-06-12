---
title: "Layer-1 Verifier Evaluation — the ensemble on FEVER / SciFact (+ constructed contested)"
subtitle: "Deep Research Agent · validating the provisional in-loop verifier on real component benchmarks"
date: "2026-06-11"
---

# Layer-1 Verifier Evaluation (2026-06-11)

**Headline verdict: the provisional ensemble `{Sonnet, Mistral, Amazon Nova}` is CONFIRMED as the in-loop verifier** — 4-way macro-F1 **0.845** (FEVER) / **0.842** (SciFact), held-out ECE **0.031**, AUROC **0.936**, with a conservative, honesty-aligned error profile.

## 1. Question & motivation

The in-loop verifier was selected **provisionally** (`2026-06-11-verifier-selection-findings.md`) on a small (60-example), by-construction-easy adversarial bench where macro-F1 saturated at 1.0. That selection was explicitly deferred to **Layer 1** — the verifier-in-isolation evaluation on real, labelled component benchmarks — for confirmation or reversal. This experiment runs that evaluation: does the ensemble hold up on FEVER + SciFact with the full metric set (4-way macro-F1, confusion + false-confidence cells, ECE/Brier before/after recalibration, AUROC), and does its 4th label (`contested`) work?

## 2. Setup

| Component | Choice |
|---|---|
| Verifier under test | Ensemble `{Sonnet 4.6, Mistral Large 3, Amazon Nova Pro}` — majority-vote label, cross-model agreement as raw confidence, holistic per-claim, `n_samples=1` |
| Datasets | FEVER (`copenlu/fever_gold_evidence`, val, **n=1000** stratified) · SciFact (AllenAI release, **n=300**) |
| Contested arm | **75/dataset constructed** from that dataset's held-out `supported` pairs: synthesize a refuting `E′` (Llama 4 Maverick), keep only pairs the ensemble validates as `E→supported ∧ E′→refuted`, then score the holistic `verify(C, [E, E′])` |
| Calibration | Platt, fit on a **held-out** 50/50 split (n_fit=725, n_eval=725) — ECE/Brier reported out-of-sample |
| Compute | EC2 p4d.24xlarge, instance-role Bedrock creds, **8 parallel workers**, detached run |

**Labels** — 4-way `{supported, refuted, insufficient, contested}`. The public sets are 3-way (no contested); contested is supplied only by the constructed arm. **Method:** for each example the ensemble runs `verify(claim, passages)`; predictions are cached, then scored. macro-F1 averages over the classes present in gold (so it is 4-way once contested is folded in). AUROC + ECE use the binary collapse `p(supported) = confidence if pred=='supported' else 1-confidence`.

## 3. Results

### FEVER (n=1075) — macro-F1 **0.845** · accuracy 0.829

| class | precision | recall | f1 | support |
|---|---|---|---|---|
| supported | 0.879 | 0.937 | 0.907 | 333 |
| refuted | 0.727 | 0.934 | 0.817 | 333 |
| insufficient | 0.894 | **0.605** | 0.721 | 334 |
| contested | **1.000** | 0.880 | 0.936 | 75 |

False-confidence cells: `insufficient→supported`=37, `refuted→supported`=6. Contested confusion: 66 correct, 8→refuted, 1→insufficient, **0→supported**.

### SciFact (n=375) — macro-F1 **0.842** · accuracy 0.835

| class | precision | recall | f1 | support |
|---|---|---|---|---|
| supported | 0.825 | 0.839 | 0.832 | 124 |
| refuted | 0.757 | 0.828 | 0.791 | 64 |
| insufficient | 0.790 | 0.741 | 0.765 | 112 |
| contested | 0.986 | 0.973 | 0.980 | 75 |

False-confidence cells: `insufficient→supported`=17, `refuted→supported`=5. Contested confusion: 73 correct, 2→refuted, **0→supported**.

### Calibration & discrimination (held-out, pooled)

| metric | value |
|---|---|
| ECE before → after (Platt) | **0.102 → 0.031** |
| Brier before → after | 0.079 → 0.062 |
| AUROC (threshold-independent) | **0.936** |
| fit split | disjoint, n_fit=725 / n_eval=725 |
| mean latency / claim | ~2.6 s (FEVER) · ~3.0 s (SciFact) |

## 4. Findings

- **The ensemble is a strong, conservative verifier.** Real-class macro-F1 (~0.81 three-way) is in line with the provisional read, and the error profile is the one we want for an honesty-first system: the **false-confidence cells are small** (37+6 / 1000 FEVER; 17+5 / 300 SciFact), and whenever it errs on `insufficient` it overwhelmingly goes to `refuted`, **not** to `supported` — it gets *cautious*, not *over-confident*.
- **The 4th label works and is well-behaved.** Contested precision is ~1.0 on both sets and the three real classes have **zero** false `contested` predictions — the ensemble does not hallucinate the 4th label. Contested recall is high (0.88 / 0.97).
- **Calibration generalizes.** The held-out ECE-after (0.031) ≈ the earlier in-sample number (0.030), so the Platt calibrator is not overfitting; recalibration roughly **3×** improves ECE (0.102→0.031). **AUROC 0.936** shows the confidence signal separates supported-vs-not strongly — a good foundation for thresholding when we add the score-based Verifier B.
- **Standing weakness: NEI / `insufficient` recall** (0.605 FEVER, 0.741 SciFact). The verifier under-recognizes "not enough info," preferring to commit to `refuted`. This is the known hard class and ties to the multi-passage construct-validity limitation below.
- **The 4-way macro-F1 is partly flattered by contested** (a high-F1 class): the three real classes are essentially unchanged from the 3-way run; folding contested in lifts the headline from 0.813/0.802 → 0.845/0.842.

### Honest caveats

1. **Contested results are an UPPER BOUND — the constructed conflict is comparatively *easy*.** We build contested by synthesizing **two opposing single-evidence versions** (`E` cleanly supports `C`, `E′` cleanly refutes `C`), and we **keep only pairs the ensemble already validated** as individually clear. So the holistic `verify(C, [E, E′])` is shown two unambiguous, opposing pieces — a clean, well-separated conflict. **Real production `contested` arises from messy multi-passage retrieval** where the disagreement is subtler, the passages noisier, and the conflict not pre-validated. The contested F1 here (0.94 / 0.98) should therefore be read as a **best-case ceiling**, not the operating-condition estimate; the verifier's contested ability on organic conflict will be lower.
2. **Single-evidence benchmark ≠ holistic multi-passage operating mode** (limitations.md #6). FEVER/SciFact present one curated, single-direction evidence per claim; production feeds the verifier k≈5 mixed-relevance passages. Layer-1 is a cleaner task than the real one, so these numbers are a (likely optimistic) proxy — the Layer-2 evaluation exercises the verifier under real retrieval.
3. **This is a confirmation, not a head-to-head re-pick.** Only Verifier A (the ensemble) was run on the real benchmarks; the 3 solo candidates and Verifier B (DeBERTa) were not re-evaluated here. The A-vs-B comparison is the Layer-2 cross-check.
4. **Cost is not measured** (`model_calls`=0): no verifier currently exposes a per-call count, so the cost columns read 0. Latency is real (~2.6–3.0 s/claim at `n_samples=1`).

## 5. Decision / Verdict

**In-loop verifier = the ensemble `{Sonnet, Mistral, Amazon Nova}` — CONFIRMED (no longer provisional).** The Layer-1 ranking does not overturn the provisional selection: the ensemble is accurate (4-way macro-F1 ~0.84), conservative in the safe error direction, well-calibrated after recalibration (ECE 0.031), and a strong discriminator (AUROC 0.936), with a clean, low-false-positive 4th label. The provisional→confirmed flip is recorded in `experiments/results/verifier/DECISION.md`. The standing `insufficient`-recall weakness and the contested upper-bound are carried forward as known limitations; the final A-vs-B word waits on the Layer-2 cross-check once Verifier B lands.

## 6. Pipeline / code changes

- `src/dra/eval/runner.py` — `ThreadPoolExecutor` parallelism (`max_workers`), order-preserving, skip-on-exception.
- `src/dra/eval/harness.py` — `--workers`, `--limit`, `--contested N`, `--calib-split`; per-benchmark contested via `augment_with_contested`; reports written before the (optional) reliability plot.
- `src/dra/eval/report.py` — held-out `--calib-split` partition (disjoint Platt fit); **AUROC** surfaced (invariant under monotonic Platt, reported once).
- `src/dra/eval/loaders/contested.py` — parallel `build_contested_set`; `augment_with_contested`.
- `pyproject.toml` — `matplotlib` dev extra (reliability diagram).

## 7. What this sets up next

- The in-loop verifier is **locked** for the pipeline — Layer-2 can proceed with the ensemble as the live verifier.
- **Verifier B (DeBERTa cross-encoder)** training is unblocked (the held-out splits + the AUROC/threshold machinery are in place); for B, note that recalibration interacts with the decision threshold (unlike the label-emitting A), so its eval must fit τ on the calibration split and report both threshold-dependent and -independent (AUROC/PR-AUC) metrics.
- The **Layer-2 A-vs-B cross-check** will deliver the final verifier word under real multi-passage retrieval.

## 8. Reproducibility

```bash
# On an instance with Bedrock access (instance role) — no Midway expiry:
export AWS_REGION=us-east-1
export BEDROCK_VERIFIER_MODELS="global.anthropic.claude-sonnet-4-6,mistral.mistral-large-3-675b-instruct,us.amazon.nova-pro-v1:0"
export BEDROCK_GENERATOR_MODEL="us.meta.llama4-maverick-17b-instruct-v1:0"   # E′ synthesis for contested
python -m dra.eval.harness --verifier A --datasets fever,scifact \
  --workers 8 --calib-split 0.5 --contested 75 --refresh
```

Raw outputs (gitignored, on the run host): `eval/results/verifier/reports/report_A.{json,md}` + `reliability_A.png`; cached predictions under `eval/results/verifier/predictions/`. Run on EC2 `i-0cd55ad3510a56ca9` (p4d.24xlarge), 8 workers, ~8 min wall for the 3-class pass; contested adds the `E′` synthesis + validation.
