---
title: "Generator-Model Comparison — Mistral vs Llama 4 Maverick vs Haiku 4.5"
subtitle: "Deep Research Agent · choosing the generator (decompose + claim-gen) role"
date: "2026-06-10"
---

# Generator-Model Comparison (2026-06-10)

## 1. Question & motivation

The generator drives a large share of the pipeline (query decomposition **and** atomic
claim generation), so the model in that role matters. The default was **Mistral Large 3**,
chosen early. We tested whether it's actually the right call against two leaner candidates —
**Llama 4 Maverick (17B)** and **Haiku 4.5** — on the full generator role.

A reframing first: among models **not reserved for the eval panel** (Opus, GPT-OSS 120B,
DeepSeek R1 are the panel), **Mistral Large 3 (675B) is already the largest/highest-capability
candidate.** So the real question was not "is there something better than Mistral?" but "does
Mistral's size earn its keep, or is a leaner model good enough — or better?"

## 2. Method

For each candidate generator: decompose → retrieve (Exa, **k=5, maxChars=2k**, fixed) →
generate claims, across **8 cases** (the 4 brief test cases + 4 additional diverse prompts:
RAG-hallucination, ultra-processed-food health, remote-work productivity, MoE-vs-dense). Each
candidate does its **own** decomposition (the whole generator role is under test).

Every claim is scored by a **3-judge panel — GPT-OSS 120B, Claude Opus 4.8, DeepSeek R1**
(all independent of the candidates) for:
- **atomicity** (0/1): exactly one checkable assertion?
- **grounding** (0–2): does the cited evidence support the claim?

Judging is chunked (≤12 claims/call) for reliability; unparseable batches are flagged
`unjudged` and excluded from means rather than silently scored 0.

Harness: `experiments/generator_comparison.py` → `experiments/results/generator_comparison/`.
Judge = panel (not a candidate), so no self-preference among the three generators. (Caveat:
Opus and Haiku are both Claude — a mild self-preference risk for Haiku's scores only; Haiku
lost decisively, so it doesn't affect the decision.)

## 3. Results — 8 cases, 3-judge panel

**Grounding (0–2) — the north star:**

| model | gpt_oss | opus | deepseek | **panel** | claims |
|---|---|---|---|---|---|
| **llama4_maverick** (17B) | 1.13 | 1.27 | 1.31 | **1.24** | 147 |
| haiku_4_5 | 0.90 | 0.96 | 1.05 | 0.97 | 287 |
| mistral_large_3 (675B) | 0.89 | 0.92 | 1.01 | 0.94 | 635 |

**Atomicity (0/1):** llama **0.80** > haiku 0.74 > mistral 0.73 (panel).

**Ranking agreement:** **all three judges independently rank grounding `Llama > Haiku >
Mistral`** — unanimous. On atomicity, GPT-OSS and Opus rank Llama first; DeepSeek is the lone
dissenter (ranks Mistral first on atomicity, but still ranks Llama first on grounding).

## 4. Findings

- **The smallest model wins on the metric that matters most.** Llama 4 Maverick (17B) beats
  Mistral Large 3 (675B) on grounding by a wide, unanimous margin (1.24 vs 0.94).
- **Why — Mistral over-reaches.** Inspection of its low-grounded claims shows confident,
  *specific* assertions the cited excerpt doesn't support (exact taxonomies, author-years,
  precise category lists) — it fills detail from parametric memory and staples a citation on.
  Llama hugs the evidence: fewer, tighter claims that paraphrase what's actually in the passage.
- **A stricter prompt did NOT fix it.** We added an explicit hard rule to `synthesis.py`
  ("use ONLY information explicitly stated in the passages… a claim that is true but not
  supported does not belong here"). Mistral still grounded worst (0.94) and still
  over-generated massively: **635 claims vs Llama's 147** (4×), even hitting a token-limit
  truncation. The over-reach is structural, not prompt-tunable.
- **For grounded synthesis, bigger is a liability, not an asset** — rich world knowledge
  becomes a source of unsupported specifics. The lean model that defers to the evidence is
  what verifiable grounding rewards.

**Honest caveats:** even Llama's grounding (1.24/2 ≈ 62%) is only moderate — real headroom
remains for the verification loop + retrieval, regardless of generator. This is single-vote
per judge (no formal Cohen's κ / significance) over n=8; 3-judge unanimity on grounding is a
strong directional result, not a proof.

## 5. Decision

**Generator = Llama 4 Maverick.** Mistral moves to the **in-loop verifier** role (its
world-knowledge suits *judging* better than faithful generation, and the in-loop verifier is
the baseline slated for replacement by the fine-tuned DeBERTa anyway). **Haiku is dropped**
(worst on both axes).

**Model independence holds** after the swap (`config.assert_independence()` passes):
generator = Llama (meta) ≠ in-loop verifier = Mistral ≠ panel {GPT-OSS, Opus, DeepSeek} ≠
baseline {Perplexity, OpenAI}. Wired in `.env` / `.env.example`.

## 6. Pipeline changes shipped from this experiment

- **`.env` / `.env.example`**: `BEDROCK_GENERATOR_MODEL` → Llama 4 Maverick;
  `BEDROCK_INLOOP_JUDGE_MODEL` → Mistral Large 3.
- **`synthesis.py`**: explicit anti-parametric-knowledge grounding rule in the prompt.
- **`llm/bedrock.py`**: default `max_tokens` 1024 → **8192** (1024 truncated claim-list JSON;
  surfaced because claim generation hadn't run live until this experiment).

## 7. Reproducibility

```bash
python -m experiments.generator_comparison   # 3 generators × 8 cases × 3-judge panel
```
Outputs: `experiments/results/generator_comparison/{model}.json` + `summary.json`.
