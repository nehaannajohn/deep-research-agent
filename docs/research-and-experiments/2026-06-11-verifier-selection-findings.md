---
title: "Verifier Selection — single LLM-judge vs 3-model ensemble"
subtitle: "Deep Research Agent · which verifier turns a claim + its cited passages into a trustworthy verdict"
date: "2026-06-11"
---

# Verifier Selection (2026-06-11)

> **Verdict (provisional): the 3-model ENSEMBLE `{Sonnet, Mistral, Amazon Nova}`** — majority-vote label, cross-model agreement as confidence. To be revisited at the rigorous Layer-1 evaluation (FEVER/SciFact).

## 1. Question & motivation

The verifier judges each claim against **all** its cited passages → `{supported, refuted, insufficient, contested}` + reasoning + recommendation + a **measured** confidence. Before locking one in, we needed to decide, empirically, **which** verifier: each of three independent candidate models solo (with self-consistency confidence) vs. a 3-model ensemble (with cross-model-agreement confidence). The verifier's label feeds report honesty and its recommendation/confidence will drive the future adaptive-retrieval loop, so the choice matters.

Independence constraints shaped the candidate set: the generator is Llama (Meta), and the eval panel is GPT-OSS / Opus / DeepSeek — so verifier candidates must avoid the Meta family, and an Anthropic verifier (Sonnet) carries a mild, accepted overlap with Opus on the panel.

## 2. Setup

| Component | Choice |
|---|---|
| Verifier candidates (solo) | Sonnet (Anthropic), Mistral Large 3, Amazon Nova — each self-consistency N=5 |
| Verifier candidate (ensemble) | the 3 together; each member N=1; majority vote + agreement confidence |
| Construction model | Llama 4 Maverick (generator — independent of all candidates/judges) |
| Validation + quality panel | GPT-OSS 120B, Opus 4.8, DeepSeek R1 |
| Retrieval | Exa (k=5, cached) |

**Test bench:** built from the 4 brief cases → generate claims → synthesize adversarial variants for each label: `supported` (control), `refuted` (claim rewritten to contradict its citation), `insufficient` (claim paired with a real but non-establishing passage), `contested` (citations + a synthetic refuter). Each tagged with an **intended label by construction**, then passed through a **panel validation gate** (kept only where ≥2/3 judges agreed). **60 examples survived** (supported 16 · refuted 15 · insufficient 16 · contested 13).

**Method:** each candidate verifies all 60; scored on per-class/macro **F1 vs the constructed labels** (panel-independent), panel-rated **reasoning & recommendation quality** (1–5), and **latency**. Confidence behaviour analysed separately.

## 3. Results

| candidate | macro-F1 | reasoning q | rec q | latency (60 ex) | confidence values |
|---|---|---|---|---|---|
| **ensemble** | **1.000** | **4.53** | **4.39** | 193s | {0.667, 1.0} |
| nova | 1.000 | 3.62 | 3.82 | 193s | {0.6, 1.0} |
| sonnet | 0.983 | 4.48 | 4.35 | 582s | {1.0} |
| mistral | 0.935 | 4.24 | 4.18 | 178s | {0.6, 0.8, 1.0} |

**Confidence (all 60):**

| candidate | mean | when correct | when wrong | n_wrong |
|---|---|---|---|---|
| sonnet | 1.000 | 1.000 | **1.000** | 1 |
| mistral | 0.977 | 0.979 | 0.95 | 4 |
| nova | 0.993 | 0.993 | — | 0 |
| ensemble | 0.972 | 0.972 | — | 0 |

## 4. Findings

**Macro-F1 saturated, so labels did not discriminate.** Two candidates hit a perfect 1.000 and a third 0.983. The validation gate kept only panel-agreed examples, so the surviving 60 are by-construction clear-cut — too easy to separate the candidates on label accuracy. The real signal was elsewhere.

**The discriminator was confidence quality + reasoning quality, and the ensemble won both:**

- **Confidence informativeness.** Self-consistency confidence *saturates* on this bench — **Sonnet's is a degenerate constant 1.0**, identical on its one wrong prediction (confidently wrong); it carries no signal and can't be calibrated. The **ensemble's cross-model agreement is the only informative signal**: `0.667` exactly on contended examples, `1.0` elsewhere — variance that tracks difficulty.
- **Error correction.** On the `insufficient` cases (bench idx 6/10/13), **Mistral systematically mislabels `insufficient → supported`** — the dangerous false-confidence direction. The ensemble **outvotes** that error (Sonnet + Nova) *and* drops its confidence to `0.667` to flag the disagreement.
- **Reasoning/recommendation quality** (the signal that will feed the adaptive loop): ensemble best at 4.53 / 4.39; Nova worst at 3.62 / 3.82 despite perfect labels.

Nova ties on labels but has the weakest reasoning and near-flat confidence; Sonnet is strong on quality but 3× slower (582s, from N=5 self-consistency) with a useless confidence signal; Mistral has the real label weakness.

**Caveats (carried to Layer 1):**
1. **Bench saturation** — perfect macro-F1 means labels don't discriminate; this is a small, by-construction-easy bench (`limitations.md #1`). The rigorous test is FEVER/SciFact (high-N).
2. **Mild self-preference on quality** — the quality panel includes Opus (Anthropic) and the ensemble contains Sonnet (Anthropic): the accepted, diluted overlap.
3. **Quality is single-vote, n=180, no significance testing.**
4. **Cost** — the ensemble runs 3 model calls per claim in-loop (comparable latency to a solo at N=5 here, but it's 3 distinct calls).

## 5. Decision / Verdict

**Verifier = the 3-model ensemble `{Sonnet, Mistral, Amazon Nova}` (provisional).** Chosen because macro-F1 saturated and, on every metric that *did* discriminate — confidence informativeness, error-correction, reasoning/recommendation quality — the ensemble was best, at latency comparable to the solos.

**Provisional — revisit at Layer 1.** Finalize on FEVER / SciFact / VitaminC with the full metric set (macro-F1, confusion matrix, **ECE/Brier/AUROC**, κ, latency/cost) per `2026-06-11-evaluation-strategy.md`. If the ranking changes there, the selection changes.

## 6. Pipeline / code changes

- `src/dra/verify/base.py` — `VerifierResult` (label/confidence/reasoning/recommendation/votes) + `verify(claim, passages)` contract.
- `src/dra/verify/llm_judge.py` — holistic self-consistent judge; resilient to truncated/unparseable output (a live-run bug); brief-reasoning prompt.
- `src/dra/verify/ensemble.py` — `EnsembleVerifier` (majority vote, agreement confidence, no-majority→insufficient, single-member passthrough).
- `src/dra/config.py` — `verifier_models`; `assert_independence` now rejects a generator-family verifier member.
- `src/dra/loop.py` — verify call-site passes the full cited-passage set (fixes the `citations[0]` bug); `build_deps` wires the ensemble (fallback to single in-loop judge).
- `.env` / `.env.example` — `BEDROCK_VERIFIER_MODELS`.

## 7. What this sets up next

- Unblocks **report composition** (verification-agnostic; built immediately after).
- The selected verifier is the LLM-judge config that **Layer 1** will benchmark against Verifier B (the DeBERTa cross-encoder) on FEVER/SciFact and finalize.
- The ensemble's cross-model agreement is the **raw confidence signal** the recalibration slice (`2026-06-11-calibration.md`) will Platt-scale.
- The constructed `contested` examples are seed data for the gold conflict set (FEVER/SciFact are 3-way and can't cover `contested`).

## 8. Reproducibility

```bash
# requires AWS creds (Arenal-science) + EXA_API_KEY
AWS_PROFILE=Arenal-science .venv/bin/python -m experiments.verifier_comparison
# inspect the side-by-side dataset + confidence stats
.venv/bin/python -m experiments.inspect_verifier_results
```

Raw outputs: `experiments/results/verifier/` — `summary.json`, `bench.json` (60 validated examples), `{sonnet,mistral,nova,ensemble}.json` (per-example preds), `comparison_sample.{md,csv}` + `comparison_sample_detailed.json` (20-example side-by-side w/ reasoning), `confidence_stats.json`, `DECISION.md`.
