---
title: "±(Verifier + Contradiction) on broad public benchmarks — FRAMES + TruthfulQA"
subtitle: "Deep Research Agent · does the reliability stage generalize off technical/DRA-Bench queries?"
date: "2026-06-13"
---

# ±Verifier on FRAMES + TruthfulQA (2026-06-13)

**Headline verdict: on broad public benchmarks the reliability stage has *no statistically significant effect on any axis* (paired tests, all p > 0.13). The value it shows on DRA-Bench (epistemic-honesty flagging) isn't *measured* here — FRAMES/TruthfulQA have no `expected_behavior` labels. What these benchmarks *do* show: (1) grounding is flat under ±verifier here too → grounding is gated on retrieval, not verification, *everywhere*; (2) broad multi-hop grounding (FRAMES ≈ 0.90) is materially below technical DRA-Bench (0.956); (3) TruthfulQA exposes grounding ≠ truthfulness — high grounding (0.95), near-zero task accuracy (0.01) — a retrieval/source-quality failure, not a verification one. Perplexity/OpenAI baselines (for absolute task-accuracy context) are backfilled below.**

Companion: the DRA-Bench ablation (`2026-06-12-verifier-contradiction-ablation-findings.md`) — where the stage's honesty signal actually lives.

## 1. Question & motivation

DRA-Bench is **technical/AI-skewed** and **gold-answer-free** (it grades epistemic *behavior*, not answer correctness). Two open questions it can't answer: (a) do the ±verifier effects **generalize** to broad, non-technical queries? and (b) how does our pipeline do on **answer correctness** against public benchmarks + commercial baselines? FRAMES (multi-hop factual QA) and TruthfulQA (adversarial misconceptions) both ship **gold answers**, so they add **task_accuracy** + **abstention** — the axes DRA-Bench lacks.

## 2. Setup

| Component | Choice |
|---|---|
| Pipeline / arms | identical to the DRA-Bench ablation: **with** = verifier + contradiction on, `with_verification=True`; **without** = both off |
| Generator (both arms) | Llama 4 Maverick |
| FRAMES | `google/frames-benchmark`, multi-hop factual QA, **gold short answers**; sampled `n=100, seed=13` (≈76–83 scored/arm after timeout/error skips) |
| TruthfulQA | `truthfulqa/truthful_qa` (generation), adversarial misconceptions, **gold truthful answers**; `n=100, seed=13` (≈83–85 scored/arm) |
| Relevance/Quality | blind 3-judge panel (GPT-OSS / Opus / DeepSeek) |
| Grounding | single independent GPT-OSS-120B judge |
| task_accuracy / abstention | extracted answer vs gold (EM / alias / judge) |
| Baselines | Perplexity `sonar-pro` + OpenAI `gpt-4o-search-preview` (same item sets) — *results §3.3, backfill pending* |

`expected_behavior` (EBM) and `formatting` are **N/A** here — these benchmarks aren't behavior-typed and carry no format constraints. Comparisons are **paired** by item id over the intersection of the two arms (FRAMES n=68, TruthfulQA n=79).

## 3. Results

### 3.1 FRAMES (paired n=68)

| metric | with | without | test | p | significant? |
|---|---|---|---|---|---|
| grounding_rate | 0.893 | 0.911 | paired-t | 0.14 | no |
| task_accuracy | 0.244 | 0.289 | McNemar (b=0, c=3) | 0.25 | no |
| abstention_rate | 0.333 | 0.342 | McNemar | 1.0 | no |
| relevance (1–5) | 3.87 | 3.70 | paired-t | 0.21 | no |
| quality (1–5) | 3.50 | 3.50 | paired-t | 0.78 | no |

### 3.2 TruthfulQA (paired n=79)

| metric | with | without | test | p | significant? |
|---|---|---|---|---|---|
| grounding_rate | 0.946 | 0.958 | paired-t | 0.40 | no |
| task_accuracy | 0.012 | 0.012 | McNemar (b=0, c=0) | 1.0 | no |
| abstention_rate | 0.241 | 0.212 | McNemar (b=10, c=8) | 0.81 | no |
| relevance (1–5) | 4.25 | 4.31 | paired-t | 0.64 | no |
| quality (1–5) | 3.98 | 4.01 | paired-t | 0.72 | no |

**Every axis on both benchmarks is non-significant.** (This *supersedes* an earlier "descriptive only / unpaired" treatment: pairing on the common item ids gives a real paired test, and the answer is a clean null.)

### 3.3 Baselines — Perplexity + OpenAI (backfill pending)

> ⏳ **To be filled in from Task B** (collecting `sonar-pro` + `gpt-4o-search-preview` on the same FRAMES/TruthfulQA item sets, scored through the same instrument). The key comparison is **task_accuracy** — without a commercial reference we can't tell whether our FRAMES 0.24 / TruthfulQA 0.01 is "weak" or "normal for this benchmark." Relevance/quality will be added too; grounding/EBM are N/A for black-box baselines.

| system | FRAMES task-acc | FRAMES rel/qual | TruthfulQA task-acc | TruthfulQA rel/qual |
|---|---|---|---|---|
| ours (with verifier) | 0.244 | 3.87 / 3.50 | 0.012 | 4.25 / 3.98 |
| ours (without) | 0.289 | 3.70 / 3.50 | 0.012 | 4.31 / 4.01 |
| Perplexity sonar-pro | _pending_ | _pending_ | _pending_ | _pending_ |
| OpenAI gpt-4o-search | _pending_ | _pending_ | _pending_ | _pending_ |

## 4. Findings

- **No significant ±verifier effect on any broad-benchmark axis.** Consistent with the DRA-Bench result that the stage's value is *honesty-flagging* (EBM), which these benchmarks don't measure. **Correction to an earlier read:** I had flagged "verifier lowers FRAMES task accuracy (0.244 vs 0.289)" and "verifier raises TruthfulQA abstention (0.241 vs 0.212)" as if meaningful — **both are non-significant** (p=0.25, p=0.81). The honest statement is a null effect.
- **"Grounding is flat under ±verifier" generalizes across all three benchmarks.** with/without grounding: DRA-Bench 0.956/0.959, FRAMES 0.893/0.911, TruthfulQA 0.946/0.958 — every pair within noise (and if anything slightly *lower* with the verifier: it annotates/flags, it doesn't fetch). Strong cross-benchmark confirmation that **grounding is gated on retrieval, not verification** → adaptive retrieval is the lever everywhere.
- **Broad multi-hop grounding is materially lower than technical (FRAMES 0.89–0.91 vs DRA-Bench 0.956)** — hallucination roughly doubles off-technical. So the adaptive-retrieval payoff is plausibly *larger* on broad queries than the technical-only 3.4%-at-risk estimate suggested.
- **TruthfulQA exposes grounding ≠ truthfulness, and it's a retrieval problem.** Grounding 0.95 but **task accuracy ≈ 0.01**: the questions are adversarial, so retrieval surfaces passages carrying the *popular misconception*, and the pipeline faithfully cites them — well-grounded yet wrong vs the truthful gold. This is **not fixable by better claim-verification or composition** (the claim *is* supported by its passage; the report *does* faithfully report it). The fix is **source-quality/consensus signals at retrieval**, or a distinct **truthfulness** check (claim↔world) separate from **grounding** (claim↔evidence). FRAMES's lower task-acc is the milder multi-hop version (grounding also dips → retrieval is the bottleneck there too).

## 5. Decision / Verdict

**On broad benchmarks the reliability stage is behavior-neutral — neither helps nor hurts any measured axis.** That's expected: its job (flag contested/insufficient) isn't graded here. The actionable signals are about **retrieval**, not the verifier: (1) broad-query grounding is lower → adaptive retrieval should help more off-technical; (2) the grounding-vs-truthfulness gap on TruthfulQA is a **source-quality** problem that verification cannot close. **Once the baselines land (§3.3), we'll know whether our task-accuracy is competitive or a real gap.**

## 6. Reproducibility

```bash
# Same driver/instrument as DRA-Bench, public datasets, both arms:
python -m experiments.run_pipeline_eval --dataset frames     --n 100 --arm both --workers 6
python -m experiments.run_pipeline_eval --dataset truthfulqa --n 100 --arm both --workers 6
# Baselines (collected locally where the API keys live; scored on the instance):
python -m experiments.collect_agentic_baselines --dataset {frames,truthfulqa}
python -m experiments.score_agentic_baselines  --dataset {frames,truthfulqa}
```

Raw outputs (gitignored, on the run host): `eval/results/pipeline_{frames,truthfulqa}/{with,without}_verifier/{per_item.json,summary.json}`; baselines under `eval/results/{frames,truthfulqa}_baselines/{perplexity,openai}/summary.json`. Significance recomputed with `src/dra/eval/pipeline/stats/significance.py` (paired-t / McNemar over the common item ids).
