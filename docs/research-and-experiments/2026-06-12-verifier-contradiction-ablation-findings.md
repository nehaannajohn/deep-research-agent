---
title: "±(Verifier + Contradiction Detection) — Layer-2 pipeline ablation on DRA-Bench"
subtitle: "Deep Research Agent · what the reliability stage buys the end-to-end report"
date: "2026-06-12"
---

# ±(Verifier + Contradiction Detection) Ablation (2026-06-12)

**Headline verdict: the reliability stage delivers a large, one-directional gain in epistemic honesty (expected-behavior match +0.22, p<0.0001, 51 items helped / 0 hurt) at no cost to grounding (flat, n.s.) and a small panel-quality dip (−0.21, p=0.0004) that is largely the quality rubric under-valuing honesty. Keep it on. The next lever for *grounding* is adaptive retrieval, not the verifier.**

> **Scope note (important).** This ablation toggles **two stages together** — the per-claim **verifier** *and* the cross-claim **contradiction detection** — as one block, vs. neither. So every gain below is attributable to the **combination**, not to verification alone. The two are architecturally independent (contradiction detection uses its own `PairContradictionJudge` over the claims, not the verifier's verdicts); separating their individual contributions needs a 2×2 (see §7). This is a valid combined ablation, deliberately framed as such.

## 1. Question & motivation

Layer-1 confirmed the verifier is a strong, well-calibrated *diagnostician*. Layer-2 asks the end-to-end question: **what does the reliability stage (verifier + contradiction layer) actually change in the final report?** Hypothesis: it improves *epistemic honesty* (flagging contested/insufficient) more than raw grounding — because without an adaptive-retrieval loop, the system can *diagnose* weak evidence but cannot *act* to improve it. Prompted upstream of the adaptive-retrieval decision: if grounding is gated on retrieval rather than verification, that points the next investment at retrieval.

## 2. Setup

| Component | Choice |
|---|---|
| Pipeline | `decompose → subquery retrieval (Exa) → claim extraction → verifier → contradiction detection → report composition` |
| **Arm A — "with"** | verifier **on** (ensemble {Sonnet, Mistral, Nova}) + contradiction detection **on**; `compose_report(with_verification=True)` |
| **Arm B — "without"** | verifier **off** (claims surfaced unverified) + contradiction detection **off**; `compose_report(with_verification=False)` |
| Generator (both arms) | Llama 4 Maverick (identical) |
| Eval set | DRA-Bench, **250 prompts, 5 types × 50** (deep-NLP/AI · pros-cons · contradictory · no-answer/ambiguous · multi-format); ~235 completed per arm (timeout skips) |
| Grounding judge | **single independent** GPT-OSS-120B (non-Anthropic; not the in-loop verifier) |
| Relevance/Quality | **blind 3-judge panel** (GPT-OSS / Opus / DeepSeek) + adjudication |
| Compute | EC2 p4d, instance-role Bedrock, detached, 6 workers |

**Method.** Same prompts, same generator, same retrieval through both arms; **the only variable is the reliability stage** (verifier + contradiction together). Each report is scored on the axes below; comparisons are **paired** (matched by prompt id, n=235): paired-t for the 1–5 rubric/continuous axes, McNemar for the binary expected-behavior match.

**How each metric is computed** (judge vs. rule vs. gold):

| metric | computed by |
|---|---|
| grounding_rate / hallucination_rate | **LLM judge** (single independent grounding judge over each claim's cited passages) |
| relevance / quality (1–5) | **LLM judge panel** (3 judges + adjudication) |
| formatting_pass | **rule** (deterministic: mermaid-block regex, markdown-table detector, length caps) |
| expected_behavior_match | **rule vs. assigned label** (heuristic on the report — flagged contested? abstained? answered? — vs. the prompt's type-derived `expected_behavior`) |
| task_accuracy / system-ECE | **gold** — N/A on DRA-Bench (no short gold answers / gold verdicts) |

## 3. Results

### Overall (paired, n = 235)

| metric | with | without | diff | p | significant? |
|---|---|---|---|---|---|
| **expected-behavior match** | **0.809** | **0.591** | **+0.218** | **<0.0001** (McNemar; b=51, c=0) | **yes** — one-directional |
| quality (1–5) | 3.902 | 4.111 | −0.209 | **0.0004** (paired-t) | yes |
| relevance (1–5) | 4.638 | 4.723 | −0.085 | 0.023 | marginal (does **not** survive Holm across the 4) |
| grounding_rate | 0.956 | 0.959 | −0.004 | 0.28 | **no** (statistically equal) |
| hallucination_rate | 0.027 | 0.022 | +0.005 | — | negligible |
| formatting_pass | 1.00 | 1.00 | 0 | — | equal |

### Per-type (with / without)

| type | EBM | grounding | quality |
|---|---|---|---|
| type1 deep-NLP/AI (answer-confident) | 1.00 / 1.00 | 0.972 / 0.984 | 4.06 / 4.27 |
| type2 pros-cons (answer-confident) | 1.00 / 1.00 | 0.946 / 0.948 | 4.28 / 4.45 |
| **type3 contradictory (flag-contested)** | **0.82 / 0.00** | 0.945 / 0.936 | **3.80 / 4.28** |
| **type4 no-answer (report-insufficient)** | **0.22 / 0.00** | 0.961 / 0.972 | 3.54 / 3.65 |
| type5 multi-format (answer-confident) | 1.00 / 1.00 | 0.954 / 0.957 | 3.82 / 3.86 |

### Baseline bracket (separate comparison, solid axes only — decision B)
Perplexity Sonar + OpenAI (web-search) on a 50-item subset, our instrument: relevance ≈ **4.74** (Perplexity) / **4.58** (OpenAI). **Grounding deliberately excluded** for the baselines — a black-box system's *source content* isn't in its response (Perplexity returns 1-line snippets, OpenAI only URLs+titles), so a fair grounding number would require fetching the cited pages; exposed per-claim grounding is *our* differentiator (see `limitations.md` #8 context).

## 4. Findings

- **The reliability stage's value is epistemic honesty, and it's concentrated exactly where it should be.** The +0.22 EBM gain is entirely in **type3** (contested: **0.82 vs 0.00** — without the stage the system *never* flags a genuine contradiction) and partial **type4** (insufficient: 0.22 vs 0.00). type1/2/5 (where confident answering is correct) are 1.00 in both arms. The gain is **one-directional**: 51 prompts the stage helped, **0** it hurt (McNemar b=51/c=0).
- **Attribution (the combined-ablation point): the type3 win is the contradiction layer; the type4 win is the verifier.** The contested-flagging that drives type3 comes from `detect_and_resolve` + the composition instruction "present contradicting pairs together as a contested finding" — i.e. **contradiction detection**, not per-claim verification. The type4 insufficient-flagging + the calibrated confidence/disclaimers come from the **verifier**. Because the ablation toggles both together, the headline number is their **sum**; a 2×2 would separate them.
- **Grounding is flat and not significant (0.956 vs 0.959, p=0.28).** Both arms make the same claims from the same evidence; the reliability stage *annotates and flags* but, with no adaptive-retrieval loop, **cannot fetch better evidence** — so grounding can't move. **This is the key strategic finding: grounding is gated on retrieval, not on verification** → the next lever is **adaptive retrieval** (the "treatment" to the verifier's "diagnosis").
- **The quality dip (−0.21, significant) is largely the metric under-valuing honesty, not worse reports.** It concentrates in type3 (3.80 vs 4.28). Example — *"Is rent control effective, or does it cut supply/quality?"*: the **without** report scores **quality [5,4,5]** for a clean *"mixed effects"* synthesis that **glosses the genuine conflict**; the **with** report scores **[3,2,4]** for explicitly stating *"this is contested — one source indicates X, another indicates Y."* The panel's quality rubric rewards fluent confident prose and penalizes contestation-flagging — so on a genuinely contested topic it **rewards the less honest report**. This is precisely why `expected_behavior_match` exists: it captures the honesty the quality rubric misses. (Full 10-example artifact: `experiments/results/verifier_ablation_examples.md`.)
- **Honest weakness — type4 recovery is low (0.22).** Even with the stage, the system flags only ~1 in 5 ill-posed/unanswerable prompts as insufficient; it over-answers the rest. Recognizing unanswerability is a standing gap (consistent with Layer-1's low `insufficient` recall).

### Caveats
1. **Combined ablation** — toggles verifier **and** contradiction detection together; does not isolate either (2×2 needed).
2. **n ≈ 235/250 per arm** — timeout-skipped items (Bedrock load); a resume pass will fill them.
3. **Single grounding judge** (not a panel) — a deliberate cost/objectivity choice; panel-for-grounding noted as a future exploration (`future-explorations.md` #5).
4. **Baseline grounding not assessed** (decision B) — black-box source content not retrieved.
5. **Quality rubric vs. honesty tension** — the quality axis, as scored by the panel, partially penalizes the correct behavior on contested topics; interpret the quality dip in that light.

## 5. Decision / Verdict

**Keep the verifier + contradiction-detection stage on (default).** It delivers a large, one-directional honesty gain (EBM +0.22) with **zero** grounding cost and only a small, largely-artifactual quality dip. The reliability stage is doing its job — surfacing contested/insufficient evidence the user would otherwise never see.

**Strategic call: the next investment is adaptive retrieval, not the verifier.** Grounding is flat across arms (p=0.28) because the system diagnoses weak evidence but can't act on it — adaptive retrieval is the missing "treatment." (Design: `docs/superpowers/specs/2026-06-11-adaptive-retrieval-design.md`.)

## 6. Pipeline / code changes
None to the pipeline from this experiment. Tooling built to run it: `experiments/run_pipeline_eval.py` (±verifier driver + report cache), `src/dra/eval/pipeline/harness.py` (orchestrator, `score_gradable`), the DRA-Bench/FRAMES loaders, and the baseline-scoring driver. The `without_verifier` arm currently drops *both* stages (the source of the combined-ablation framing).

## 7. What this sets up next
- **Adaptive retrieval** — the lever for grounding/coverage (the flat-grounding result is its motivation).
- **Decouple contradiction detection from verification** — run it in both arms (it only needs the claims), enabling a clean **2×2 (±verification × ±contradiction)** to separate the type3 (contradiction) vs type4/confidence (verification) contributions.
- **Improve type4 (unanswerability) detection** — 0.22 is a real gap.
- **Verifier B (DeBERTa)** for the A-vs-B cross-check + a panel-for-grounding robustness check.

## 8. Reproducibility

```bash
# On EC2 (instance-role Bedrock), both arms over DRA-Bench:
export AWS_REGION=us-east-1
export BEDROCK_GENERATOR_MODEL=us.meta.llama4-maverick-17b-instruct-v1:0
export BEDROCK_VERIFIER_MODELS=global.anthropic.claude-sonnet-4-6,mistral.mistral-large-3-675b-instruct,us.amazon.nova-pro-v1:0
export BEDROCK_PANEL_MODELS=openai.gpt-oss-120b-1:0,global.anthropic.claude-opus-4-8,us.deepseek.r1-v1:0
export BEDROCK_GROUNDING_JUDGE_MODEL=openai.gpt-oss-120b-1:0
python -m experiments.run_pipeline_eval --arm both --workers 6
```

Raw outputs (gitignored, on the run host): `eval/results/pipeline/{with,without}_verifier/{per_item.json,summary.json}` + cached reports under `report_cache/`. Sample report pairs (tracked): `experiments/results/verifier_ablation_examples.md`.
