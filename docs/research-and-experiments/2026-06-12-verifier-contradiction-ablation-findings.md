---
title: "±(Verifier + Contradiction Detection) — Layer-2 pipeline ablation on DRA-Bench"
subtitle: "Deep Research Agent · what the reliability stage buys the end-to-end report"
date: "2026-06-12"
---

# ±(Verifier + Contradiction Detection) Ablation (2026-06-12)

**Headline verdict (updated 2026-06-13 with a text-level EBM re-measurement): the reliability stage's value depends on how EBM is measured, and the difference exposes a real bug. By the *structural* EBM (claim-verdict based) it delivers a large one-directional gain (+0.22, p<0.0001, 51/0). But a *text-level* judge reading the actual reports finds the gain does NOT replicate (with 0.786 vs without 0.810) — because the stage *over-flags contestation on settled, answer-confident queries* (e.g. it marks the textbook definition of "transfer learning" as `contested`), making those reports read as hedged. So: the stage genuinely helps on contested/insufficient queries (type3/4) but hurts on confident-answer queries (type1/5) by manufacturing disagreement. Net text-EBM is flat. Keep the stage, but the priority fix is tightening the contestation threshold so it fires only on genuine disagreement. Grounding is unaffected either way (flat, n.s.) → adaptive retrieval remains the lever for grounding.**

> **Scope note (important).** This ablation toggles **two stages together** — the per-claim **verifier** *and* the cross-claim **contradiction detection** — as one block, vs. neither. So every gain below is attributable to the **combination**, not to verification alone. The two are architecturally independent (contradiction detection uses its own `PairContradictionJudge` over the claims, not the verifier's verdicts); separating their individual contributions needs a 2×2 (see §7). This is a valid combined ablation, deliberately framed as such.

> **This doc covers DRA-Bench only.** The same ±verifier ablation on the broad public benchmarks (FRAMES + TruthfulQA) — plus the Perplexity/OpenAI baselines on those sets — lives in the companion: `2026-06-13-frames-truthfulqa-pipeline-findings.md`.

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

### 2.1 What DRA-Bench is

DRA-Bench is our **custom epistemic-behavior benchmark.** Public benchmarks ask *"is the final answer correct?"* (agentic QA like FRAMES) or *"is a single claim entailed by a single evidence?"* (FEVER/SciFact, our Layer-1). Neither measures the thing this system is built for: *does the agent do the **epistemically right thing*** — flag a genuine contradiction, admit when a question has no answer, and answer confidently only when the evidence warrants it. DRA-Bench is the benchmark that exposes the **claim ledger's honesty**, which is invisible to the others.

- **250 prompts**, synthesized by a **non-generator model** (so they aren't tuned to our Llama generator) and **reviewed by the author**, stratified into **5 query types** chosen to span the behavior space:

| type | n | what it probes | target `expected_behavior` |
|---|---|---|---|
| type1 — deep NLP/AI | 50 | a well-posed technical question with a defensible answer | `answer_confident` |
| type2 — pros-and-cons | 50 | a balanced assessment where both sides should appear | `answer_confident` (both sides) |
| **type3 — contradictory** | 50 | topics where credible sources genuinely disagree | **`flag_contested`** |
| **type4 — no-answer / ambiguous** | 50 | ill-posed / unanswerable / false-premise (TruthfulQA-like) | **`report_insufficient`** (or `ask_clarification`) |
| type5 — multi-format output | 50 | an answer best conveyed as a table or diagram | `answer_confident` + format |

- **`expected_behavior` label** — each prompt carries a type-derived target (above); this is the gradable gold for the *honesty* axis, the one label DRA-Bench supplies that public sets can't.
- **Gold reference reports** — one detailed reference report per prompt, generated by an **independent model (Sonnet 4.6** on Bedrock; switched from Fable after an API-credit/data-sharing wall — `limitations.md` #8). Used for the *similarity-to-reference* axis and as a strong-reference comparison; the reference is graded by the **non-Anthropic** judges to keep it independent.
- **Type 3 + Type 4 are the discriminating types** — they're where "do the right thing" diverges from "write a fluent answer," and where this ablation's signal lives.

**Method.** Same prompts, same generator, same retrieval through both arms; **the only variable is the reliability stage** (verifier + contradiction together). Each report is scored on the axes below; comparisons are **paired** (matched by prompt id, n=235): paired-t for the 1–5 rubric/continuous axes, McNemar for the binary expected-behavior match.

### 2.2 Metrics we designed & how each is computed

| metric | what it measures | formula / method | source |
|---|---|---|---|
| **grounding_rate** | share of claims backed by their cited evidence | an **independent LLM judge** verdicts each `(claim, its cited passages)` → supported / insufficient / refuted; `grounding_rate = supported / n_claims` | **LLM judge** (single, independent; not the in-loop verifier) |
| **hallucination_rate** | share of claims fabricated or uncited | same per-claim judge; `= (insufficient + uncited) / n_claims` | **LLM judge** |
| **relevance** (1–5) | report answers the query; citations are on-topic | a **blind 3-judge panel** (GPT-OSS / Opus / DeepSeek) scores a rubric → mean/majority, with **adjudication** when judges diverge | **LLM panel** |
| **quality** (1–5) | coherence + comprehensiveness | same panel, quality rubric | **LLM panel** |
| **formatting_pass** | met the prompt's explicit format ask | deterministic checks (`wants_visual`→mermaid-block regex; `format=table`→markdown-table detector; length caps); `= satisfied / applicable` | **rule** (deterministic) |
| **expected_behavior_match** | did the system do the *right thing* for the type | a heuristic reads the report's behavior (flagged a contested finding? abstained / said insufficient? answered confidently?) and compares it to the prompt's assigned `expected_behavior` | **rule vs. assigned label** |
| **similarity-to-gold** | claim coverage vs the Sonnet reference | claim-level **entailment** overlap of our claims vs the reference's claims | **LLM judge + reference** |
| **system-ECE** | is surfaced per-claim confidence calibrated | bin confidence vs correctness — **needs gold verdicts → N/A on DRA-Bench** | gold (N/A here) |
| **task_accuracy** | extracted short answer vs gold | EM / alias / judge-equivalence — **N/A on DRA-Bench** (no short gold answers; used on agentic benchmarks like FRAMES) | gold (N/A here) |

In short: **LLM judges** drive grounding / hallucination / relevance / quality / similarity; **rules** drive formatting + expected-behavior; **gold** would drive task-accuracy + ECE but those are N/A on DRA-Bench (no short gold answers or gold verdicts).

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

### EBM measured two ways — structural vs text-level judge (added 2026-06-13)

The headline `expected_behavior_match` above is the **structural** metric: it checks observable properties of our claim ledger (`flag_contested` ⇒ ≥1 claim has verdict `contested`; `report_insufficient` ⇒ abstained / has an `insufficient` claim; `answer_confident` ⇒ did not abstain). To check whether that gain reflects what a *reader* sees, we re-scored EBM with a **text-level judge** (`openai.gpt-oss-120b`) that reads the report text and decides whether it exhibits the behavior — the same judge applied to our pipeline and (separately) to the baselines, so comparisons are fair.

| EBM measure | with | without |
|---|---|---|
| **Structural** (claim-verdict based) | **0.807** | **0.595** |
| **Text-level judge** | 0.786 | **0.810** |

**The structural +0.22 does not replicate under a text judge — the sign even flips.** The reason is in the per-type disagreement counts (where the two arms get *different* text-EBM verdicts):

| type | expected behavior | n | **without-pass / with-fail** | with-pass / without-fail |
|---|---|---|---|---|
| type1 | answer_confident | 48 | **8** | 0 |
| type2 | answer_confident | 47 | 0 | 0 |
| type3 | flag_contested | 50 | 3 | **9** |
| type4 | report_insufficient | 46 | 6 | 7 |
| type5 | answer_confident | 44 | **5** | 0 |

The verifier **wins on type3/4** (legitimate contestation/insufficiency: net +6 / +1) but **loses on type1/5** (confident-answer: −8 / −5). Three of five types are `answer_confident`, so the losses dominate → net text-EBM is flat-to-negative. **Crucially, structural EBM is blind to this**: it scores `answer_confident` as merely "did not abstain," and the verifier doesn't abstain on type1, so structural type1 = 1.00/1.00 — it cannot see the over-hedging the text judge penalizes.

**The root cause is over-flagging (concrete evidence).** On settled, answer-confident topics the contradiction layer marks *non-contested* claims as `contested` — because multiple sources phrase the same fact differently and the pairwise logic reads wording variance as disagreement:

| type1 query (expect `answer_confident`) | over-flagging in the WITH-verifier report |
|---|---|
| *"What is transfer learning…?"* | **10 of 15 claims `contested`** — incl. c0 (conf 1.0): *"Transfer learning is a technique where a model trained on one task is reused as the starting point for a related task"* (the textbook definition) |
| *"How does grokking arise…?"* | **12 of 17 `contested`** — incl. the standard definition of grokking |
| *"How do LLMs do in-context learning…?"* | **8 of 17 `contested`** — incl. the definition of ICL |

The text judge's reasons on these cases are consistent: *"presents many contested and contradictory claims, hedging rather than giving a clear answer"* (with) vs *"directly defines… without hedging"* (without). So the report reads as conflicted on a topic that has a confident answer.

**The same over-flagging also shows up as a significant *quality* cost — it's one bug with two symptoms.** Splitting the −0.21 aggregate quality dip by whether contestation *should* appear:

| group | quality with | without | Δ | p | relevance Δ | p |
|---|---|---|---|---|---|---|
| **answer_confident** (type1+2+5) | 4.058 | 4.201 | **−0.144** | **0.045** | −0.086 | 0.051 |
| **contested/insufficient** (type3+4) | 3.677 | 3.979 | **−0.302** | **0.003** | −0.083 | 0.21 |

Two distinct, both-significant mechanisms:
- **Over-hedging cost** (answer-confident types, −0.144, p=0.045): the *spurious* contestation on settled topics reads as hedged → panel marks it down. **Same root cause as the text-EBM losses on type1/5** — the over-flagging produces *three* symptoms at once on answer-confident queries (failed text-EBM, lower quality, and the bogus `contested` labels themselves).
- **Honest-contestation cost** (contested types, −0.302, p=0.003): the *legitimate* flagging on genuinely contested topics, where the panel under-values honesty (the rent-control example, §4). A metric limitation, not a bug.

Relevance is essentially flat (borderline on the answer-confident pool), so the effect is concentrated in *quality* — a hedged tone reads as lower quality, not lower relevance. **Per-type quality Δ:** type1 −0.208, type2 −0.170, type3 **−0.480** (only individually-significant one, p=0.001), type4 −0.109, type5 −0.045.

> **Broad benchmarks live in a companion doc.** The ±verifier results on FRAMES + TruthfulQA (where the stage shows no significant effect on any axis) are written up separately: `2026-06-13-frames-truthfulqa-pipeline-findings.md`.

## 4. Findings

- **The reliability stage's value is epistemic honesty, and it's concentrated exactly where it should be.** The +0.22 EBM gain is entirely in **type3** (contested: **0.82 vs 0.00** — without the stage the system *never* flags a genuine contradiction) and partial **type4** (insufficient: 0.22 vs 0.00). type1/2/5 (where confident answering is correct) are 1.00 in both arms. The gain is **one-directional**: 51 prompts the stage helped, **0** it hurt (McNemar b=51/c=0).
- **⚠️ The +0.22 is partly a structural-metric artifact — and the gap exposes an over-flagging bug (added 2026-06-13).** A text-level judge reading the reports finds EBM *flat* (with 0.786 vs without 0.810), not +0.22 (see §3 "EBM measured two ways"). The structural metric credits the verifier's `contested` verdicts but is blind to the *cost* of producing them: on `answer_confident` type1/5 queries the contradiction layer over-flags settled facts as `contested` (e.g. 10/15 claims in the "transfer learning" report, including its textbook definition), so the report reads as hedged and the text judge fails it. The stage helps where contestation is real (type3/4) and hurts where it isn't (type1/5). **This is the single most actionable finding: tighten the `contested` threshold to fire only on genuine semantic disagreement, not cross-source wording variance.** The cost of *not* fixing it is now measured on two axes: failed text-EBM on type1/5 *and* a significant **−0.144 quality drop on answer-confident types (p=0.045, §3 decomposition)**. Fixing it should recover type1/5 confidence, the answer-confident quality, *and* the text-EBM together — without touching the legitimate type3/4 gains.
- **Attribution (the combined-ablation point): the type3 win is the contradiction layer; the type4 win is the verifier.** The contested-flagging that drives type3 comes from `detect_and_resolve` + the composition instruction "present contradicting pairs together as a contested finding" — i.e. **contradiction detection**, not per-claim verification. The type4 insufficient-flagging + the calibrated confidence/disclaimers come from the **verifier**. Because the ablation toggles both together, the headline number is their **sum**; a 2×2 would separate them.
- **Grounding is flat and not significant (0.956 vs 0.959, p=0.28).** Both arms make the same claims from the same evidence; the reliability stage *annotates and flags* but, with no adaptive-retrieval loop, **cannot fetch better evidence** — so grounding can't move. **This is the key strategic finding: grounding is gated on retrieval, not on verification** → the next lever is **adaptive retrieval** (the "treatment" to the verifier's "diagnosis").
- **The −0.21 quality dip is TWO different costs, and only one is "real" (see §3 decomposition).** (a) On **contested types (type3/4)** the dip is large (−0.302, p=0.003) and is the metric under-valuing *honest* contestation — e.g. *"Is rent control effective…?"*: the **without** report scores quality **[5,4,5]** for a clean *"mixed effects"* gloss; the **with** report scores **[3,2,4]** for explicitly naming the contested sources. The panel rewards fluent confident prose, so it rewards the *less honest* report — exactly the gap `expected_behavior_match` exists to capture. (b) On **answer-confident types (type1/2/5)** there's a *second*, smaller-but-significant dip (−0.144, p=0.045) that is **not** a metric artifact — it's the **over-flagging bug** making settled-topic reports read hedged. (a) is a measurement limitation we accept; **(b) is a bug to fix** — and the fix recovers quality *and* text-EBM together. (Full 10-example artifact: `experiments/results/verifier_ablation_examples.md`.)
- **Honest weakness — type4 recovery is low (0.22).** Even with the stage, the system flags only ~1 in 5 ill-posed/unanswerable prompts as insufficient; it over-answers the rest. Recognizing unanswerability is a standing gap (consistent with Layer-1's low `insufficient` recall).

### Illustrative example (type3 — rent control)
**Query:** *"Is rent control an effective tool for housing affordability or does it reduce housing supply and quality?"* · `expected_behavior = flag_contested`.

**WITHOUT** verifier+contradiction — quality **[5,4,5]**, EBM ✗ (synthesizes; does not flag the conflict):
> Rent control has **mixed effects** on housing affordability, supply, and quality. While it provides short-term benefits to current tenants, it can lead to decreased affordability, reduced housing supply, and lower housing quality in the long run [c0, c4, c7, c12].

**WITH** verifier+contradiction — quality **[3,2,4]**, EBM ✓ (names the contradiction explicitly):
> The effectiveness of rent control … is **contested**, with some claims suggesting it increases affordability … while others argue it reduces supply and quality. One source indicates more restrictive reforms increase availability for low-income households [c2]; however, this is **contested by multiple claims** — that in the long run rent control decreases affordability [c4], reduces the total number of rental units [c5], and reduces supply [c7].

Both reach a similar substantive position; only the **with** arm surfaces *that the sources directly disagree* — the behavior `expected_behavior` rewards and the quality rubric mildly penalizes. (Remaining 9 pairs: `experiments/results/verifier_ablation_examples.md`.)

### Caveats
1. **Combined ablation** — toggles verifier **and** contradiction detection together; does not isolate either (2×2 needed).
2. **n ≈ 235/250 per arm** — timeout-skipped items (Bedrock load); a resume pass will fill them.
3. **Single grounding judge** (not a panel) — a deliberate cost/objectivity choice; panel-for-grounding noted as a future exploration (`future-explorations.md` #5).
4. **Baseline grounding not assessed** (decision B) — black-box source content not retrieved.
5. **Quality rubric vs. honesty tension** — the quality axis, as scored by the panel, partially penalizes the correct behavior on contested topics; interpret the quality dip in that light.

## 5. Decision / Verdict

**Keep the verifier + contradiction-detection stage on (default) — but fix the over-flagging as the top priority.** By the structural metric it delivers a large honesty gain (EBM +0.22) at zero grounding cost; but a text-level judge shows that gain doesn't reach the reader because the stage **over-flags contestation on settled, answer-confident queries** (net text-EBM flat, §3/§4). So the stage is doing the right thing on genuinely contested/insufficient queries (type3/4) and the wrong thing on confident-answer queries (type1/5).

**Action: tighten the `contested` threshold (the `PairContradictionJudge` / contestation logic) to require genuine semantic disagreement, not cross-source wording variance.** This is the highest-value fix — it should turn the stage into a net win on *both* the structural and text-level EBM, and recover the **measured −0.144 quality cost on answer-confident types (p=0.045)**. (The remaining quality cost — −0.302 on genuinely contested type3/4 — is the panel under-valuing honest contestation, a metric limitation we accept, not a bug.) Re-run this ablation after the fix to confirm.

**Strategic call: the next investment is adaptive retrieval, not the verifier.** Grounding is flat across arms (p=0.28) because the system diagnoses weak evidence but can't act on it — adaptive retrieval is the missing "treatment." (Design: `docs/superpowers/specs/2026-06-11-adaptive-retrieval-design.md`.)

## 6. Pipeline / code changes
None to the pipeline from this experiment. Tooling built to run it: `experiments/run_pipeline_eval.py` (±verifier driver + report cache), `src/dra/eval/pipeline/harness.py` (orchestrator, `score_gradable`), the DRA-Bench/FRAMES loaders, and the baseline-scoring driver. The `without_verifier` arm currently drops *both* stages (the source of the combined-ablation framing).

## 7. What this sets up next
- **🔧 Fix contestation over-flagging (highest priority).** The contradiction layer marks settled facts `contested` when sources merely word them differently (§3/§4). Tighten `PairContradictionJudge` to require genuine semantic disagreement; re-run this ablation to confirm the stage becomes a net win on text-EBM and recovers quality. Add a regression guard: a type1 `answer_confident` query should rarely produce `contested` claims.
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

The text-level EBM re-measurement (§3 "EBM measured two ways") uses `src/dra/eval/pipeline/judges/behavior_judge.py` over the cached reports of both arms. Raw outputs (gitignored, on the run host): `eval/results/pipeline/{with,without}_verifier/{per_item.json,summary.json}` + cached reports under `report_cache/`. Sample report pairs (tracked): `experiments/results/verifier_ablation_examples.md`. **Broad-benchmark (FRAMES/TruthfulQA) results: companion doc `2026-06-13-frames-truthfulqa-pipeline-findings.md`.**
