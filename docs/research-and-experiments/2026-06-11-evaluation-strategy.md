# Evaluation Strategy — Deep Research Agent

> **Compiled:** 2026-06-11
> **Scope:** How we evaluate the system at two levels — the **verifier** (component) and the **full pipeline** (system) — which benchmarks we use for each, and which metrics we report.
> **Relationship to design:** This operationalizes §5 (Benchmarking & Evaluation) of the design doc (`docs/superpowers/specs/2026-06-09-deep-research-agent-design.md`). The design defines the pipeline evaluation axes and benchmark tiers; this doc reframes them around the component-vs-system split and **adds the verifier metric set, which the design left unspecified.**

---

## 1. Two layers of evaluation

Evaluation happens at two distinct levels. They answer different questions, use different data, and must not be conflated.

| Layer | Question it answers | Data | Reproducible? |
|---|---|---|---|
| **Layer 1 — Verifier (component)** | Given a claim and evidence, does the verifier assign the correct verdict, with calibrated confidence? | Labeled claim-verification datasets | Yes — closed, fixed labels |
| **Layer 2 — Pipeline (system)** | Does the full deep research agent produce a relevant, grounded, well-formed, honest report? | Agentic + attribution benchmarks + our curated gold set | Partly — web changes; gold set is fixed |

Layer 2 has two facets:

- **2a — Task accuracy:** did the agent reach the correct final answer? (agentic benchmarks)
- **2b — Epistemic quality:** is the *claim ledger* correct and is the *confidence calibrated*? (our gold set — the facet only our system exposes)

```
Layer 1: Verifier        → FEVER / SciFact / VitaminC   → pick best verifier (F1 + ECE)
Layer 2a: Pipeline task  → GAIA / FRAMES / BrowseComp   → final-answer correctness
Layer 2b: Pipeline epist → DRA-Bench (custom gold)      → calibration + claim-ledger quality
   └─ cross-check: does the Layer-1 winner also win Layer-2?  (component ≠ system ablation)
```

---

## 2. Layer 1 — Verifier evaluation

The verifier is benchmarked **in isolation**, before it goes into the pipeline. This is where we compare verifier variants — **Verifier A (prompted LLM-judge)** vs **Verifier B (fine-tuned DeBERTa cross-encoder)** — and pick a winner on a fixed, labeled benchmark.

### 2.1 Benchmarks

| Benchmark | What it is | Why chosen / coverage | Role |
|---|---|---|---|
| **FEVER** | ~185K claims labeled Supported / Refuted / NotEnoughInfo against Wikipedia evidence | General-domain, high-N → powers verifier training **and** high-N grounding statistics | Primary |
| **SciFact** | ~1.4K scientific claims with rationale sentences, 3-way labels | Technical/scientific domain — matches our ML-research test prompts far better than Wikipedia | Primary |
| **VitaminC** | Claims paired with *contrastive* evidence (revisions that flip the label) | Forces the verifier to decide on the evidence, not on priors — directly tests our "evidence drives the verdict" invariant | Optional / robustness |
| **AVeriTeC**, **HoVer** | Real-world open-web claims; multi-hop claim verification | Extensions that address the known weakness "entailment models weak on multi-hop" (design §6) | Future extension |

Maps to the design's **Tier 1 (component ground truth)**.

### 2.2 Metrics

The design left verifier metrics unspecified; this is the proposed set. Verdict labels are `{supported, refuted, insufficient, contested}` (FEVER/SciFact are 3-way; `contested` is exercised on conflict sets and our gold data).

| Metric | What it captures | Why it matters here |
|---|---|---|
| **Macro-F1** + per-class precision/recall | Classification quality, weighting all verdicts equally | Classes are imbalanced and the **minority classes (`refuted`, `insufficient`) carry the honesty signal** — macro, not accuracy, is the headline |
| **Accuracy** | Overall correctness | Secondary, reported alongside F1 |
| **Confusion matrix** | *Where* it errs | The dangerous direction is `insufficient/refuted → supported` (false confidence); we track that cell explicitly |
| **ECE (before vs after recalibration)** | Calibration of confidence | **The headline calibration metric.** Raw scores are miscalibrated; we report ECE pre/post temperature-scaling or isotonic regression |
| **Brier score** | Calibration + sharpness combined | Complements ECE; penalizes confident-and-wrong |
| **AUROC** (supported vs not) | Threshold-independent discrimination | Separates ranking ability from the τ threshold choice |
| **Cohen's κ** vs human/judge labels | Agreement where labels come from a panel rather than gold | Reliability context for any non-gold evaluation |
| **Latency & cost per claim** | Operational profile | Core to the A-vs-B tradeoff — DeBERTa is cheap/fast, the LLM-judge is not; F1 alone wouldn't decide it |

> **Calibration:** how each verifier's raw confidence signal is obtained, recalibrated (**Platt scaling** by default, **isotonic** if needed), and evaluated via **ECE before/after** — including the **binary vs. per-class** probability choice — is detailed in `2026-06-11-calibration.md`.

---

## 3. Layer 2 — Pipeline evaluation

Once a verifier is selected and locked into the agent, we evaluate the **whole pipeline** end-to-end.

### 3.1 Benchmarks

| Tier | Datasets | Measures | Note |
|---|---|---|---|
| **Agentic task** (2a) | **GAIA, FRAMES, BrowseComp** | Final-answer correctness on hard, tool-requiring questions | Short verifiable answers → needs an **answer-extraction step** mapping our long report → the gold answer |
| **System attribution** | **ALCE** (ASQA, QAMPARI, ELI5), **ExpertQA** | Citation precision/recall + grounding on long-form output | Design Tier 2 |
| **Phenomenon stress** | **TruthfulQA**, a **conflict set**, **HotpotQA** (opt.) | Plausible-but-false; contradictory sources (Test Case 2); multi-hop | Design Tier 3 |
| **DRA-Bench** (2b) | **Ours** (curated, stratified gold) | Epistemic quality — claim-ledger correctness, calibration, and `expected_behavior` (clarify / report-insufficient / flag-contested / answer-confident) | Design Tier 4; the facet no public benchmark covers |

### 3.2 Metrics — the five pipeline axes

These are the axes defined in design §5.1. Listed using the working names plus the design's axis name where they differ.

| Axis | Metric(s) | Method | Ground truth |
|---|---|---|---|
| **Relevance** | Judge rubric score (citations relevant to query; report answers query) | Judge panel | No |
| **Grounding** | **Grounding rate** (% claims entailed by citations), **hallucination rate**, **citation precision/recall** | Verifier + labels (FEVER/SciFact/ALCE) | **Yes** |
| **Consistency** | Run-to-run claim overlap / entailment agreement across N runs | Multi-run comparison | No |
| **Quality** (language quality) | Judge rubric — coherence, comprehensiveness | Judge panel | No |
| **Formatting correctness** (subset of *instruction adherence*) | **Spec-checklist pass rate** on the query's explicit format/scope/modality constraints | Spec checklist + judge | Partial (spec) |

Plus two cross-cutting pipeline metrics:

| Metric | Captures | Source |
|---|---|---|
| **System-level calibration (ECE)** | Is the *surfaced* per-claim confidence calibrated on real reports? | DRA-Bench labeled claims |
| **Task accuracy** | Did the agent get the final answer right? | Agentic benchmarks (2a) |

> **Note on "formatting correctness" vs "instruction adherence":** the design's *instruction adherence* axis is broader — it covers format **and** scope **and** modality constraints. Formatting correctness is the format slice of it. We score the full axis via the spec checklist and report formatting as a named component.

### 3.3 Statistical rigor (applies to all Layer-2 comparisons)

From design §4 — every comparison carries reliability + significance context, not just a point estimate:

- **Judge reliability:** human validation on a sampled subset (report `n`) + **Cohen's κ**.
- **Significance:** **paired t-test** (continuous metrics), **McNemar** (paired binary), **Holm** correction for multiple comparisons.
- **Unit of analysis:** grounding at **claim-level** (N in thousands → well-powered); rubric axes at **prompt-level** (~100).

---

## 4. How the two layers connect — sequencing & the cross-check

The order is a **gate**, designed to isolate the verifier as the variable:

1. **Build** an initial verifier.
2. **Layer-1 benchmark** all verifier variants (A vs B, plus any others) on FEVER/SciFact → select the winner on **Macro-F1 + ECE**, with cost/latency as tiebreakers.
3. **Lock** the chosen verifier into the pipeline.
4. **Layer-2 benchmark** the full agent on the agentic + attribution + DRA-Bench suites.
5. **Cross-check ablation:** run the pipeline twice — once with Verifier A, once with Verifier B — and confirm the **Layer-1 winner is also the Layer-2 winner.**

**Why step 5 matters:** Layer-1 accuracy does **not** automatically predict Layer-2 quality. FEVER/SciFact are closed-corpus, clean, mostly single-hop; the pipeline feeds the verifier messy, retrieved, multi-passage evidence. "Best on FEVER" is therefore a *hypothesis* about end-to-end quality. If the two layers disagree, that is itself a finding worth reporting — component accuracy not transferring to system quality.

**Why agentic benchmarks aren't enough on their own:** GAIA/FRAMES/BrowseComp score a single short answer (facet 2a). They do **not** test the claim ledger, contested-claim handling, or calibration (facet 2b) — the things this architecture is actually about. That facet is why **DRA-Bench is not optional.**

---

## 5. Summary

| | Verifier (Layer 1) | Pipeline (Layer 2) |
|---|---|---|
| **Benchmarks** | FEVER, SciFact, VitaminC (opt: AVeriTeC, HoVer) | GAIA/FRAMES/BrowseComp · ALCE/ExpertQA/ASQA · TruthfulQA/conflict/HotpotQA · DRA-Bench |
| **Metrics** | Macro-F1, per-class P/R, confusion matrix, **ECE (pre/post)**, Brier, AUROC, κ, latency/cost | Relevance · Grounding (rate, hallucination, citation P/R) · Consistency · Quality · Formatting correctness · system ECE · task accuracy |
| **Purpose** | Pick the best verifier in isolation | Measure the whole agent — task accuracy **and** epistemic quality |
| **When** | Before integration | After the verifier is locked in |
