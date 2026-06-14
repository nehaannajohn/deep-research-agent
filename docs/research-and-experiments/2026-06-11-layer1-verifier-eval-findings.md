---
title: "Layer-1 Verifier Evaluation — ensemble (A) vs fine-tuned cross-encoder (Verifier B v0/v1) on FEVER / SciFact"
subtitle: "Deep Research Agent · which verifier-in-isolation, on real component benchmarks: the LLM ensemble, or a small fine-tuned cross-encoder"
date: "2026-06-11"
---

# Layer-1 Verifier Evaluation (2026-06-11; Verifier B v0/v1 added 2026-06-14)

**Headline verdict (A).** The provisional ensemble `{Sonnet, Mistral, Amazon Nova}` is CONFIRMED as the in-loop verifier — 4-way macro-F1 **0.845** (FEVER) / **0.842** (SciFact), held-out ECE **0.031**, AUROC **0.936**, with a conservative, honesty-aligned error profile.

**Headline verdict (Verifier B, added 2026-06-14).** The fine-tuned DeBERTa cross-encoders are a **competent, calibratable, ~130× faster** alternative: on the identical FEVER+SciFact test set, **v0** matches the ensemble on competency (combined 3-way macro-F1 0.839 vs A's 0.815), calibrates well (ECE 0.066→**0.039**, AUROC **0.966**), and runs at **19 ms/claim vs A's ~2485 ms** — one local forward pass replacing three Bedrock calls. **Best B = v0**; the extra our-distribution data in **v1** did not help on the clean benchmark (and slightly hurt calibration). The Layer-1 bar for B was never "beat A" (B is in-distribution, A is zero-shot) — it was *parity + calibratability + a real latency/cost win*, and that is met.

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
3. **The 3 solo candidates were not re-evaluated here** (only the ensemble). Verifier B (DeBERTa v0/v1) **was** added at Layer-1 on 2026-06-14 — see §4B. The A-vs-B *production-replacement* word still waits on the Layer-2 cross-check under real multi-passage retrieval.
4. **Cost is not measured** (`model_calls`=0): no verifier currently exposes a per-call count, so the cost columns read 0. Latency is real (~2.6–3.0 s/claim at `n_samples=1`).

## 4B. Verifier B (v0 / v1) on the same FEVER + SciFact test set (added 2026-06-14)

We evaluated the two fine-tuned **Verifier B** cross-encoders (DeBERTa-v3-base, 3-way head `{supported, refuted, nei}`) on the **identical** seed-13 FEVER+SciFact test set, scored the same way as the ensemble, to answer the Layer-1 question for B: *is a small fine-tuned verifier a competent, calibratable, cheaper/faster alternative?* — **not** "does it beat A" (B trains in-distribution on FEVER/SciFact while A is zero-shot, so a B macro-F1 win is expected and uninteresting).

- **v0** — trained on FEVER + SciFact public pairs.
- **v1** — v0's data **+** our-distribution synthetic hard-negatives + an evidence-ablated curriculum (designed for messy multi-passage retrieval).

**5-set comparison (combined FEVER+SciFact, 3-way, n=1300; B latency on one A100):**

| set | macro-F1 | ECE (pre→post Platt) | AUROC | Brier (post) | latency p50 | speedup vs A |
|---|---|---|---|---|---|---|
| **Ensemble A** | 0.815 | — → 0.031\* | 0.936\* | 0.062\* | ~2485 ms | 1× |
| v0 (uncal) | 0.839 | 0.066 | 0.966 | 0.072 | 19.1 ms | 130× |
| **v0 (Platt)** ⭐ | **0.839** | 0.066 → **0.039** | **0.966** | 0.069 | 19.1 ms | **130×** |
| v1 (uncal) | 0.834 | 0.064 | 0.962 | 0.075 | 18.8 ms | 132× |
| v1 (Platt) | 0.834 | 0.064 → 0.059 | 0.962 | 0.072 | 18.8 ms | 132× |

\* A's ECE/AUROC/Brier from §3 (pooled, includes contested); A's **combined** 3-way macro-F1 is recomputed from its cached predictions on the same 1300 examples (contested excluded). Two comparability notes: (i) A's combined 3-way (0.815) sits below its per-dataset 0.845/0.842 because pooling FEVER+SciFact lowers the hard `insufficient` F1; (ii) the calibration *target* differs — A calibrates agreement-in-its-verdict, B calibrates P(supported) — so the ECE figures establish "both are calibratable," not a byte-identical number.

**Findings.**
- **Both B variants reach competency parity with A** on the identical basis (0.839 / 0.834 vs 0.815) — the expected in-distribution edge; the point is parity, achieved.
- **B is well-calibrated and a stronger ranker** — v0's Platt drives ECE 0.066→**0.039** (≈ A's 0.031) and AUROC **0.966** > A's 0.936. (Per the §7 note, B's confidence is the *threshold* signal the future adaptive loop needs; AUROC 0.966 says it separates supported-vs-not cleanly.)
- **The decisive axis is latency/cost: ~130× faster** (19 ms vs ~2485 ms). One local 184M forward pass replaces three Bedrock LLM round-trips per claim, eliminating the network cost entirely — a *comparable* B is already a clear win on this axis.
- **Best B = v0 (Platt-calibrated).** v1 is marginally worse on every axis, most notably calibratability (ECE-after 0.059 vs 0.039 — v1's Platt barely helps).

### Why v1 differs from v0 (error analysis — full multi-passage)

> **Methodology note (corrected 2026-06-14).** This analysis uses the REAL `verify(claim, passages)` aggregated over **all** cited evidence sentences (309/1300 examples are multi-passage; up to 25 sentences). An earlier pass scored only the first sentence, which over-stated the gap (52/38) and mislabeled multi-passage cases — e.g. *"Nuuk is the seat of government of only Iceland"* (gold `refuted`): the **2nd** evidence sentence names Greenland, so on full evidence v1 correctly says `refuted` (it only looked like an abstention when the 2nd sentence was hidden). The macro-F1 / ECE / AUROC in §4B were always computed on full evidence and are unaffected.

On full evidence: **v0-right & v1-wrong = 55; v1-right & v0-wrong = 48** (net v0 +7) — v1 is **very close** to v0, consistent with the 0.839 vs 0.834 macro-F1. v1 is the **more conservative** model; that conservatism *wins* 48 cases (v0 over-commits) and the 55 losses break down as:

| v1 error type | count | honesty defense? |
|---|---|---|
| **Over-abstains** (gold supported/refuted → v1 `insufficient`) | 31 (20 sup, 11 ref) | **partly** — defensible on multi-hop chains and thin single-evidence (e.g. *"Tijuana is on an island"*, evidence only says "on the Baja California Peninsula"; *"Ivan Reitman directed Ashton Kutcher"*, requires a 2-hop chain). Some are genuine misses (*"Liverpool was the town where The Beatles formed"*, evidence states it directly). |
| **Over-commits** (gold `insufficient` → v1 supported/refuted) | 21 (9 sup, 12 ref) | **NO** — v1 asserts a verdict the evidence doesn't support (*"Arginine 90 in p150n…"*: 7 passages, none mention Arg90, v1 says supported; *"Arterioles have a larger lumen than venules"*: 10 irrelevant cardiac passages, v1 says refuted). |
| **Wrong-direction flips** | 3 | NO |

**Interpretation.** The story is *not* "v1 is uniformly worse" — it's a **conservatism trade**: v1's evidence-ablated curriculum (built to recognize thin/ablated evidence) makes it abstain more, which **helps** where v0 over-commits (v1's 48 wins) and **hurts** where the evidence does justify a verdict (the 31 over-abstentions, partly defensible). The genuinely concerning bucket is the **21 over-commitments on `insufficient` evidence** — the opposite of conservatism, where v1 hallucinates a verdict from irrelevant passages. Net on the clean benchmark: v1 ≈ v0 (v0 marginally ahead on macro-F1 + calibration), with v1's conservatism a plausible *asset* under real retrieval. **This is exactly why the Layer-2 drop-in tests both v0 and v1** — Layer-1 FEVER/SciFact, whose gold can encode world knowledge beyond the shown evidence (limitation #6), under-credits an evidence-faithful abstainer; the multi-passage Layer-2 operating condition is the fairer test of whether v1's conservatism is honesty or under-confidence. Raw disagreements + full evidence + tags: `eval/results/verifier_b/v1_gap.json`; reviewer-friendly `v1_vs_v0_verifier_gap.{md,csv}`.

## 5. Decision / Verdict

**In-loop verifier = the ensemble `{Sonnet, Mistral, Amazon Nova}` — CONFIRMED (no longer provisional).** The Layer-1 ranking does not overturn the provisional selection: the ensemble is accurate (4-way macro-F1 ~0.84), conservative in the safe error direction, well-calibrated after recalibration (ECE 0.031), and a strong discriminator (AUROC 0.936), with a clean, low-false-positive 4th label. The provisional→confirmed flip is recorded in `experiments/results/verifier/DECISION.md`. The standing `insufficient`-recall weakness and the contested upper-bound are carried forward as known limitations.

**Verifier B (added 2026-06-14): a viable cheaper/faster drop-in candidate — best variant v0.** At Layer-1, v0 reaches competency parity with the ensemble (combined 3-way 0.839 vs 0.815), calibrates well (ECE 0.039, AUROC 0.966), and is **~130× faster** (19 ms vs ~2485 ms/claim) — the latency/cost case for swapping the 3-model ensemble for one local cross-encoder. **v1's our-distribution curriculum did not help on the clean benchmark** (marginally worse macro-F1 + calibration), so v0 is the **Layer-1 pick** — but the full-evidence error analysis (§4B) shows v1 is the *more conservative* model, abstaining where evidence is thin/multi-hop; that conservatism is penalized by FEVER gold (which can encode world knowledge beyond the shown evidence, limitation #6) yet may be an **asset under real retrieval**. So **both v0 and v1 go to the Layer-2 drop-in** — the best Layer-1 verifier may not be the best Layer-2 verifier. The final production verdict waits on that **Layer-2 A-vs-B drop-in** under real multi-passage retrieval (the prereq `verify()` multi-passage aggregation fix is done; eval plan: `docs/superpowers/plans/2026-06-14-verifier-b-v0v1-eval.md`); Layer-1 only certifies B is *competent, calibratable, and cheap enough to be worth that test*.

## 6. Pipeline / code changes

- `src/dra/eval/runner.py` — `ThreadPoolExecutor` parallelism (`max_workers`), order-preserving, skip-on-exception.
- `src/dra/eval/harness.py` — `--workers`, `--limit`, `--contested N`, `--calib-split`; per-benchmark contested via `augment_with_contested`; reports written before the (optional) reliability plot.
- `src/dra/eval/report.py` — held-out `--calib-split` partition (disjoint Platt fit); **AUROC** surfaced (invariant under monotonic Platt, reported once).
- `src/dra/eval/loaders/contested.py` — parallel `build_contested_set`; `augment_with_contested`.
- `pyproject.toml` — `matplotlib` dev extra (reliability diagram).

## 7. What this sets up next

- The in-loop verifier is **locked** for the pipeline — Layer-2 can proceed with the ensemble as the live verifier.
- **Verifier B (DeBERTa cross-encoder) Layer-1 is now done** (§4B): v0 is competent, calibratable, ~130× faster; v1's our-distribution data didn't help on the clean task. The held-out splits + AUROC/threshold machinery generalized to B's score-based confidence as designed.
- The **Layer-2 A-vs-B cross-check** is the remaining step for the final production word — drop **v0** (and v1, to confirm the Layer-1 ranking holds) into the pipeline on DRA-Bench, **gated on the `CrossEncoderVerifier.verify()` multi-passage aggregation fix** (single-passage Layer-1 is unaffected; multi-cited Layer-2 claims over-flip to `contested` without it). Plan: `docs/superpowers/plans/2026-06-14-verifier-b-v0v1-eval.md`.

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

**Verifier B (v0/v1) — §4B (GPU only, no Bedrock; checkpoints `eval/verifier_b_models/{v0,v1}/best`):**
```bash
# Layer-1 metrics per variant (macro-F1 + Platt ECE/Brier + AUROC + latency):
CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.verifier_b.eval_layer1 --variant v0
CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.verifier_b.eval_layer1 --variant v1
# 5-set comparison table (A recomputed from its predictions + v0/v1 layer1.json):
.venv/bin/python -m experiments.verifier_b.compare_layer1
# v1-vs-v0 disagreement / error analysis:
.venv-train/bin/python -m experiments.verifier_b.disagreement
```
Raw outputs (gitignored): `eval/results/verifier_b/{v0,v1}/layer1.json`, `eval/results/verifier_b/v1_gap.json`.
