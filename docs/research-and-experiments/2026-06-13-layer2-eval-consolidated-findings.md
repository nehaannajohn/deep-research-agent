---
title: "Layer-2 Pipeline Eval — Consolidated Findings (DRA-Bench · FRAMES · TruthfulQA)"
subtitle: "Deep Research Agent · the capstone summary of what whole-pipeline evaluation established, and the one conclusion it converges on: the verifier + contradiction layers are sound diagnosis bounded by retrieval"
date: "2026-06-13"
---

# Layer-2 Pipeline Eval — Consolidated Findings (2026-06-13)

**One-line verdict.** Across three benchmarks the whole-pipeline evaluation settles three things: (1) the **verifier is a must-have** — it is the only source of grounding/contested/insufficient labels; (2) the **contradiction layer is necessary but retrieval-bound** — it catches genuine cross-claim conflict (removing it zeroes type3 honesty) yet over-flags settled topics because the *sources* genuinely disagree, not because the layer is wrong; the **structured-reasoning prompt (validated at full scale)** recovers the quality this over-flagging cost (+0.181, Holm-significant) while keeping the honesty (structural EBM tied with the naïve arm); (3) **grounding is gated on retrieval, not verification** — flat under ±verifier on all three benchmarks. The characterized **upper bound on report quality is upstream, at retrieval** (quality / diversity / source-selection), not at these components. The next lever is **adaptive / multi-backend retrieval**, not more verifier tuning.

> **This is the capstone.** It consolidates the headline results the three detailed docs own; go to them for full method, per-type breakdowns, and example artifacts:
> - **DRA-Bench** (epistemic-behavior, the honesty signal): [`2026-06-12-verifier-contradiction-ablation-findings.md`](./2026-06-12-verifier-contradiction-ablation-findings.md)
> - **FRAMES + TruthfulQA** (broad public, task-accuracy): [`2026-06-13-frames-truthfulqa-pipeline-findings.md`](./2026-06-13-frames-truthfulqa-pipeline-findings.md)
> - **The retrieval-ceiling limitation** (the converged conclusion): [`limitations.md`](./limitations.md) #9
> - Verifier B (A-vs-B trained cross-encoder, separate track): [`2026-06-13-verifier-b-v0-vs-v1-findings.md`](./2026-06-13-verifier-b-v0-vs-v1-findings.md)

## 1. Question & motivation

Layer-1 confirmed the verifier is a strong, calibrated *diagnostician* against single-claim/single-evidence benchmarks (FEVER/SciFact). Layer-2 asks the end-to-end question: **what does the reliability stage (verifier + contradiction layer) actually change in the final report — and where is the binding constraint on report quality?** The answer drives the single biggest open product decision: *do we invest next in the verifier, or in retrieval?*

We answer it on three benchmarks chosen to be complementary:
- **DRA-Bench** — our custom epistemic-behavior set (250 prompts, 5 types). The *only* one that grades *honesty* (flag contested, admit insufficient, answer confidently when warranted) via an `expected_behavior` gold label.
- **FRAMES** — multi-hop factual QA with gold short answers → adds **task_accuracy** + **abstention**.
- **TruthfulQA** — adversarial misconceptions with gold truthful answers → stress-tests **grounding ≠ truthfulness**.

## 2. Setup (common to all three)

| Component | Choice |
|---|---|
| Pipeline | `decompose → subquery retrieval (Exa) → claim extraction → verifier → contradiction detection → report composition` |
| **Arm "with"** | verifier **on** (ensemble {Sonnet 4.6, Mistral Large 3, Nova Pro}) + contradiction **on** |
| **Arm "without"** | verifier **off** + contradiction **off** (claims surfaced unverified) |
| **Arm "corrected"** | verifier **on** + contradiction **on with the structured-reasoning pair prompt** (the interim over-flagging fix) |
| Generator (all arms) | Llama 4 Maverick (identical) |
| Grounding judge | single independent GPT-OSS-120B (non-Anthropic; not the in-loop verifier) |
| Relevance / Quality | blind 3-judge panel (GPT-OSS / Opus / DeepSeek) + adjudication |
| Significance | **paired** by item id — paired-t (continuous), McNemar (binary), Holm across families |
| Compute | EC2 p4d, instance-role Bedrock, detached, 6 workers |

**Method.** Same prompts, same generator, same retrieval through every arm; the only variable is the reliability stage. EBM (expected-behavior match) and formatting are DRA-Bench-only (FRAMES/TruthfulQA aren't behavior-typed); task_accuracy and abstention are FRAMES/TruthfulQA-only (DRA-Bench has no short gold answers).

---

## 3. Results — DRA-Bench (separately)

### 3a. Three-arm comparison (with / without / corrected), full paired runs — **usable**

The reliability stage in three configurations: **with** (verifier+contradiction on), **without** (both off), **corrected** (on, with the structured-reasoning contradiction prompt — the over-flagging fix at full scale). Per-arm means (DRA-Bench, n = 238 / 237 / 238):

| metric | with | without | corrected |
|---|---|---|---|
| **EBM — structural** (claim-verdict) | **0.807** | **0.595** | **0.794** |
| **EBM — text-judge** (reads the report) | 0.786 | 0.810 | 0.794 |
| quality (1–5) | 3.895 | 4.118 | **4.105** |
| relevance (1–5) | 4.626 | 4.726 | 4.655 |
| grounding_rate | 0.956 | 0.959 | 0.953 |
| hallucination_rate | 0.028 | 0.022 | 0.028 |
| formatting_pass | 1.00 | 1.00 | 1.00 |

**Paired significance (id-matched, Holm-corrected within the DRA-Bench family).** Continuous via paired-t, binary structural-EBM via McNemar (exact binomial; `b`=first-arm-right/second-wrong, `c`=reverse):

| comparison | metric | effect | raw p | Holm p_adj | survives Holm? |
|---|---|---|---|---|---|
| **corrected vs with** | **quality** | **+0.181** | 7.3e-7 | 7.3e-6 | **yes** |
| corrected vs with | structural EBM | b=8, c=10 | 0.81 | — | **no** (indistinguishable) |
| **corrected vs without** | **structural EBM** | b=49, c=0 (0.796 vs 0.583) | <1e-10 | 7.7e-11 | **yes** |
| with vs without | structural EBM | b=51, c=0 (0.809 vs 0.591) | <1e-10 | 3.0e-11 | **yes** |
| with vs without | quality | −0.169 | <1e-4 | <1e-3 | **yes** |
| with vs without | relevance | −0.087 | <0.01 | <0.05 | **yes** |
| any arm | grounding_rate | ≈0 | n.s. | — | **no** (statistically equal) |

Paired n: corrected-vs-without structural-EBM uses the 230-item id-intersection; the other pairs 233–238. **The headline:** corrected does exactly what the fix intended — it **recovers the quality the over-flagging `with` arm was sacrificing** (+0.181 vs with, survives Holm; corrected's 4.105 ≈ without's 4.118) **while keeping the verifier's structural-EBM honesty** (statistically *indistinguishable* from with — b=8/c=10, p=0.81 — and far above without, +0.21, p_adj=7.7e-11). The `with` arm's over-flagging penalty is itself significant (quality −0.169 and relevance −0.087 vs without, both survive Holm). **Net: corrected buys with's honesty at without's quality.** Grounding is flat across all three arms (the retrieval ceiling).

> **Text-EBM significance — computed (paired McNemar, Holm); no arm differs.** All three arms are text-EBM-scored with **persisted per-item verdicts** (`eval/results/pipeline/{with,without,corrected}_verifier/text_ebm.json`). Aggregate rates with 0.786 / without 0.810 / corrected 0.794 (a later paired re-score read with 0.769 / without 0.806 — within judge non-determinism). Paired, Holm-corrected: **corrected-vs-with p_adj=0.65 (b=20/c=12), corrected-vs-without p_adj=1.0 (b=15/c=14), with-vs-without p_adj=0.65 (b=15/c=23) — none significant.** So the large *structural* EBM gain (corrected/with ≫ without) does **not** reach the reader: at the text level the three arms are statistically indistinguishable — the over-flagging story, now significance-tested. (`eval/results/pipeline_significance/text_ebm_significance.json`.)

**Per-type EBM — structural gain concentrated where it should be (with / without):** type1/2/5 (answer-confident) 1.00 / 1.00; **type3 (contested) 0.82 / 0.00**; type4 (insufficient) 0.22 / 0.00. **Corrected text-EBM per type:** type1 0.936, type2 0.978, type3 0.840, type4 **0.347**, type5 0.894 (answer-confident pooled **0.935**, 130/139). The residual reader-facing gap is **type4 report_insufficient (0.347)** — the hard class for every arm (admitting a genuine gap, not just flagging conflict).

**Quality decomposition (aggregate rubric, 3-arm) — `with` depressed *both* groups; corrected recovers both to ≈ without:**

| group | with | without | corrected | corrected − with |
|---|---|---|---|---|
| answer_confident (type1+2+5) | 4.043 | 4.213 | **4.216** | **+0.173** |
| contested/insufficient (type3+4) | 3.680 | 3.979 | **3.949** | **+0.269** |

The `with` arm's over-flagging depressed quality in *both* groups — over-hedging settled topics (answer_confident) *and* adding spurious extra `contested` flags on genuinely-contested ones. The corrected prompt recovers both back to ≈ `without` (answer_confident 4.216 ≈ 4.213; contested/insufficient 3.949 ≈ 3.979), so the +0.181 paired gain is **broad-based, marginally larger on the contested/insufficient group** (+0.269 vs +0.173 unpaired). The with-vs-without dips were significant in the paired ±verifier analysis (answer_confident −0.144, p=0.045; contested/insufficient −0.302, p=0.003; ablation doc §3); corrected closes essentially all of both.

### 3b. Baselines (50-item subset, fair axes only — decision B) — **usable**

| system | relevance | quality | formatting | text-EBM |
|---|---|---|---|---|
| ours (with verifier) | 4.63 | 3.90 | 1.00 | ~0.79 |
| ours (without) | 4.73 | 4.11 | 1.00 | ~0.81 |
| **ours (corrected)** | 4.66 | 4.11 | 1.00 | ~0.79 |
| **Perplexity** `sonar-pro` | 4.74 | 4.94 | 0.60 | 0.86 |
| **OpenAI** `gpt-4o-search-preview` | 4.58 | 4.46 | 0.60 | 0.84 |
| *Sonnet-4.6 gold (ceiling)* | *4.85* | *4.90* | *0.60* | — |

Grounding/hallucination excluded for the black-box baselines (their *source content* isn't in their response — fair grounding would require fetching cited pages). Exposed per-claim grounding is our differentiator; formatting (1.00 vs 0.60) is the one axis we lead on (we emit diagrams/tables on demand).

### 3c. Similarity to Sonnet-4.6 gold (±verifier) — **usable**

with **0.104** / without **0.106**, paired **p=0.75 (n.s.)**. Low absolute coverage (~10% of a dense gold reference's atomic claims) is a **retrieval-breadth** gap, not a verification error, and the verifier doesn't change it.

---

## 4. Results — FRAMES + TruthfulQA (separately)

### 4a. Three-arm (with / without / corrected), paired — **usable. Headline: no significant effect on any axis, either benchmark.**

**FRAMES** (per-arm n = 78 / 76 / 75):

| metric | with | without | corrected |
|---|---|---|---|
| grounding_rate | 0.893 | 0.911 | 0.918 |
| task_accuracy | 0.244 | 0.289 | 0.253 |
| abstention_rate | 0.333 | 0.342 | 0.320 |
| relevance (1–5) | 3.87 | 3.70 | 3.87 |
| quality (1–5) | 3.50 | 3.50 | 3.44 |

**TruthfulQA** (per-arm n = 83 / 85 / 86):

| metric | with | without | corrected |
|---|---|---|---|
| grounding_rate | 0.946 | 0.958 | 0.944 |
| task_accuracy | 0.012 | 0.012 | 0.023 |
| abstention_rate | 0.241 | 0.212 | 0.233 |
| relevance (1–5) | 4.25 | 4.31 | 4.29 |
| quality (1–5) | 3.98 | 4.01 | 4.05 |

**No comparison reaches significance even before Holm** on either benchmark (paired-t for continuous; McNemar for task_accuracy, where discordant counts are tiny — e.g. TruthfulQA task-accuracy has b=c=0 across arms, FRAMES corrected-vs-with b=2/c=3). Paired n ~63–86; these broad sets are underpowered, and the reliability stage simply doesn't move task-accuracy or grounding here — consistent with the DRA-Bench grounding null and the retrieval ceiling. The corrected prompt neither helps nor hurts on broad benchmarks (it targets DRA-Bench-style epistemic over-flagging, which these sets don't grade).

### 4b. Commercial baselines on FRAMES + TruthfulQA — ✅ **scored (n = 100 each), usable**

All four runs scored through the same instrument (n = 100 each, both providers, both datasets). The decisive axis is **task_accuracy**:

| system | FRAMES task-acc | FRAMES rel/qual | TQA task-acc | TQA rel/qual |
|---|---|---|---|---|
| ours (with verifier) | 0.244 | 3.87 / 3.50 | 0.012 | 4.25 / 3.98 |
| ours (without) | 0.289 | 3.70 / 3.50 | 0.012 | 4.31 / 4.01 |
| ours (corrected) | 0.253 | 3.87 / 3.44 | 0.023 | 4.29 / 4.05 |
| **Perplexity** `sonar-pro` | **0.24** | 4.16 / 3.83 | **0.06** | 4.75 / 4.76 |
| **OpenAI** `gpt-4o-search-preview` | **0.37** | 4.45 / 4.26 | **0.05** | 4.45 / 4.33 |

**Reading it.**
- **FRAMES task-accuracy: our ~0.24–0.29 is *level with Perplexity* (0.24) and behind OpenAI's search model (0.37).** So our FRAMES number is **not a catastrophic gap** — it sits in the commercial range, with a real but bounded deficit to the strongest search-grounded system. The remaining headroom is a retrieval/multi-hop-coverage gap (FRAMES is multi-hop), the same lever as everywhere else.
- **TruthfulQA task-accuracy collapses for everyone** — ours ~0.01–0.02, Perplexity 0.06, OpenAI 0.05. All four are near the floor: the adversarial-misconception trap defeats grounded retrieval **universally**, confirming grounding ≠ truthfulness is a benchmark-wide property, not a defect unique to us. The baselines' 3–5× absolute edge is still near-zero in practical terms.
- **Quality/relevance:** as on DRA-Bench, the commercial systems score higher on the panel's fluency-weighted quality (esp. Perplexity on TruthfulQA, 4.76) — confident prose over exposed uncertainty. Our differentiators (per-claim grounding, honest contestation, on-demand formatting) remain off-axis for black-box baselines.

---

## 5. Key findings

1. **The verifier is a must-have.** Without it there are no supported/contested/insufficient labels — no defensible grounding claim and no honesty signal. This is not an ablation result to weigh; it's the precondition for the product thesis.
2. **Epistemic honesty is the verifier's real value, and it's measurable only on DRA-Bench.** The +0.22 structural EBM gain is one-directional (51 helped / 0 hurt) and lives entirely in **type3 contested (0.82 vs 0.00)** + partial **type4 insufficient (0.22 vs 0.00)**. FRAMES/TruthfulQA can't see it (no behavior labels) → they show a null, as expected.
3. **The structural EBM gain doesn't fully reach the reader under the `with` arm — over-flagging — but the corrected prompt fixes it at scale.** A text-level judge finds `with`-vs-`without` EBM flat (0.786 vs 0.810; paired McNemar n.s., p_adj=0.65 — §3a): on settled answer-confident queries the contradiction layer marks non-contested claims `contested` (e.g. 10/15 claims in the "transfer learning" report, including its textbook definition), so the report reads hedged — same root cause as the **−0.144 quality drop on answer-confident types (p=0.045)**. **The full-scale corrected run resolves this:** quality recovers **+0.181 vs with (Holm p_adj=7.3e-6)** and answer-confident text-EBM rises to **0.935**, while structural EBM stays statistically *tied* to with (McNemar b=8/c=10, p=0.81) and far above without (+0.21, p_adj=7.7e-11). **Corrected = with's honesty at without's quality.** The only residual reader-facing gap is **type4 report_insufficient (text-EBM 0.347)** — the hard "admit a genuine gap" class for every arm.
4. **The over-flagging is *upstream*, not a component bug (decisive).** The flagged claims are *faithfully grounded* in idiosyncratic sources that genuinely disagree — e.g. the IBM "fine-tuning improves performance on the *initial* task" definition is verbatim its source and really conflicts with other sources. The contradiction layer detected a **real cross-source disagreement**; the conflict was introduced by retrieval/source selection.
5. **The contradiction layer is necessary, not removable.** A `verifier_only` arm eliminated the type1 over-flags but **destroyed genuine type3 contestation (type3 EBM 5/5 → 0/5)** — that conflict lives *across* separately-grounded claims, which per-claim verification can't see. (10-item diagnostic; full-scale `corrected_verifier` underway, §7.)
6. **Prompting hit a ceiling, and the structured-reasoning prompt is now the *settled* default.** text-only → structured-reasoning → evidence-grounded prompts each traded type1-precision against type3-recall and none cleanly separated them — because the underlying conflicts are real. The structured-reasoning prompt, **validated at full scale (§3a: recovers quality, preserves structural-EBM honesty)**, is the settled default; further judge tuning is low-value.
7. **Grounding is gated on retrieval, not verification — on all three benchmarks.** with/without grounding: DRA-Bench 0.956/0.959, FRAMES 0.893/0.911, TruthfulQA 0.946/0.958 — every pair within noise (and if anything slightly *lower* with the verifier: it annotates, it doesn't fetch). Cross-benchmark confirmation that the grounding lever is retrieval.
8. **Broad grounding is materially lower than technical (FRAMES ~0.90 vs DRA-Bench 0.956)** → hallucination roughly doubles off-technical, so the adaptive-retrieval payoff is plausibly *larger* on broad queries than the technical-only 3.4%-at-risk estimate suggested.
9. **TruthfulQA exposes grounding ≠ truthfulness, and it's a retrieval problem.** Grounding 0.95, task-accuracy ~0.01: retrieval surfaces passages carrying the popular misconception and the pipeline faithfully cites them — well-grounded yet wrong. Not fixable by verification/composition; the fix is source-quality/consensus signals at retrieval (or a separate claim↔world truthfulness check).
10. **vs commercial baselines (now on all three benchmarks):** comparable on relevance; Perplexity/OpenAI score *higher* on panel quality (fluent confident prose), while our differentiators — exposed per-claim grounding + honest contestation + on-demand formatting (1.00 vs 0.60) — are exactly what black boxes can't be measured on. On **task-accuracy** the broad-benchmark picture is now concrete: **FRAMES — we match Perplexity (0.24) and trail OpenAI-search (0.37); TruthfulQA — all systems near-floor (ours ~0.01–0.02, baselines 0.05–0.06).** So our broad task-accuracy is **competitive-to-bounded, not a collapse** — the FRAMES deficit to OpenAI is a multi-hop-retrieval gap, and the TruthfulQA floor is universal (the misconception trap defeats grounded retrieval for everyone).

**The convergence (→ `limitations.md` #9):** four independent results — flat grounding under ±verifier (all 3 benchmarks), ~10% Sonnet coverage, the faithfully-grounded IBM over-flag, and grounding≠truthfulness on TruthfulQA — all point to the same upstream ceiling: **retrieval quality / diversity / source-selection**, not the verification or contradiction components.

---

## 6. Ablation usability status

| ablation | scale | status |
|---|---|---|
| 3-arm (with / without / corrected) — DRA-Bench, all axes | n=238/237/238 per arm | ✅ **usable** |
| 3-arm (with / without / corrected) — FRAMES / TruthfulQA, all axes | n≈75–86 per arm | ✅ **usable** |
| **Paired significance — DRA-Bench (paired-t + McNemar + Holm)** | id-matched, n=230–238 | ✅ **usable** |
| Paired significance — FRAMES / TruthfulQA | id-matched, n≈63–86 | ✅ **usable (clean null)** |
| Baselines (Perplexity/OpenAI) — DRA-Bench, fair axes | 50-item subset | ✅ **usable** |
| **Baselines (Perplexity/OpenAI) — FRAMES / TruthfulQA** | n=100 each | ✅ **usable** |
| Similarity-to-gold (±verifier) | n=235 paired | ✅ **usable** |
| contradiction variants (verifier_only / structured / evidence-grounded) | **10 items only** | ❌ superseded by the full 3-arm run |
| Text-EBM paired significance (McNemar, all 3 arms) | id-matched, n=230–235 | ✅ **usable — all n.s.** (§3a) |

The original 10-item contradiction runs are superseded: the full `corrected_verifier` run delivers a usable, significance-tested **3-arm comparison (with / without / corrected)** across all three benchmarks. The **only** remaining unmeasured item is per-item text-EBM for the with/without arms (aggregate-only), which would require a Bedrock re-score and is out of close-out scope.

---

## 7. Decision / Verdict

**Keep the verifier + contradiction stage on (default), with the structured-reasoning contradiction prompt as the settled default — now validated at full scale.** The 3-arm run shows it delivers the honesty gain (structural EBM tied with `with`, +0.21 over `without`) at zero grounding cost *and* recovers the quality that naïve over-flagging cost (+0.181 vs `with`, Holm-significant). The residual over-flagging is a retrieval/source problem, not a judge problem.

**The next investment is adaptive / multi-backend retrieval, not the verifier.** Grounding is flat across arms on every benchmark because the system *diagnoses* weak evidence but can't *act* on it — adaptive retrieval is the missing treatment. (Design: `docs/superpowers/specs/2026-06-11-adaptive-retrieval-design.md`.)

**Close-out status — COMPLETE.** All three remaining items are done and folded into this doc:
1. ✅ **Full `corrected_verifier` 3-arm** (DRA-Bench 250 + FRAMES/TruthfulQA 100) — scored on all metrics; the structured prompt recovers answer-confident quality (+0.181 vs with, Holm-significant) and lifts answer-confident text-EBM to 0.935 without eroding structural-EBM honesty (tied with `with`, far above `without`). 3-arm tables in §3a / §4a.
2. ✅ **FRAMES/TruthfulQA baseline scoring** (Perplexity + OpenAI, n=100 each) — scored clean (the only fallout was 400 macOS AppleDouble `._*` files skipped, **zero real-file failures**). §4b: our FRAMES task-acc matches Perplexity / trails OpenAI-search; TruthfulQA is universally near-floor.
3. ✅ **Paired significance** (paired-t + McNemar + Holm, id-matched) — DRA-Bench structural-EBM + quality effects survive Holm; **text-EBM is n.s. across all three arms** (the structural gain doesn't reach the reader, now significance-tested); FRAMES/TruthfulQA are a clean null. Artifacts in `eval/results/pipeline_significance/`.

**Layer-2 is fully closed** — no measurements outstanding; all per-item verdicts (structural + text EBM, all three arms) persisted and significance-tested.

**Not in scope for close-out** (separate track): Verifier B fine-tuning (controllability/cost — bound by the same retrieval ceiling); the 2×2 (±verification × ±contradiction) decoupling; type4 unanswerability recall (a standing gap, text-EBM 0.347).

## 8. Reproducibility

```bash
# DRA-Bench, both arms (full):
python -m experiments.run_pipeline_eval --arm both --workers 6

# Broad benchmarks, both arms:
python -m experiments.run_pipeline_eval --dataset frames     --n 100 --arm both --workers 6
python -m experiments.run_pipeline_eval --dataset truthfulqa --n 100 --arm both --workers 6

# The full 3-arm close-out (corrected contradiction prompt), all three:
python -m experiments.run_pipeline_eval --dataset dra_bench  --arm corrected_verifier --workers 6
python -m experiments.run_pipeline_eval --dataset frames     --n 100 --arm corrected_verifier --workers 6
python -m experiments.run_pipeline_eval --dataset truthfulqa --n 100 --arm corrected_verifier --workers 6

# Baselines (collected locally where API keys live; scored on the instance):
python -m experiments.collect_agentic_baselines --dataset {frames,truthfulqa}
python -m experiments.score_agentic_baselines  --dataset {frames,truthfulqa}

# Text-level EBM re-measurement over cached reports:
#   src/dra/eval/pipeline/judges/behavior_judge.py
# Paired significance (pure local compute — no Bedrock):
#   src/dra/eval/pipeline/stats/significance.py   # paired_t / mcnemar / holm
#   eval/results/pipeline_significance/run_significance.py   # the close-out analysis script
```

Raw outputs (gitignored, on the run host): `eval/results/pipeline{,_frames,_truthfulqa}/{with,without,corrected}_verifier/{per_item,summary}.json` (+ corrected `text_ebm.json`) + `report_cache/`; DRA-Bench baselines `eval/results/baselines/{perplexity,openai}/`; broad baselines `eval/results/{frames,truthfulqa}_baselines/{perplexity,openai}/`. Significance inputs/outputs (pulled local): `eval/results/pipeline_significance/{paired_metrics.json,significance_results.json,run_significance.py}`. Tracked sample report pairs: `experiments/results/verifier_ablation_examples.md`.
