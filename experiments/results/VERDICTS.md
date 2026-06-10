# Retrieval Experiments — Consolidated Verdicts (2026-06-10)

All three decisions from the staged decomposition + retrieval experiments, in one place.
Per-stage source files: `stage1_decomposition/VERDICT_decomposition.md`,
`stage2_charsweep/VERDICT_maxchars.md`, `stage4_kcoverage/VERDICT_k.md`.
Full write-up: `docs/experiments/2026-06-10-retrieval-experiments-findings.md` (+ PDF).

## Settled defaults

| Parameter | Value | Settled by |
|---|---|---|
| Query decomposition | **ON** (flexible 1…N; split only for distinct evidence) | Experiment 1 (Stage 1) |
| Excerpt budget (maxCharacters) | **2,000** | Experiment 2 (Stage 2) |
| Retrieval depth (k) | **5** per sub-question | Experiment 3 (Stages 3–4) |

---

## Stage 1 Verdict — Decomposition: KEEP (conditional split, validated)

**Decision:** Keep query decomposition. The flexible decomposer splits multi-faceted
queries into distinct sub-questions and passes genuinely atomic queries through
unchanged — both behaviors confirmed live.

**Evidence (A/B at 2k excerpt budget, four brief test cases):** decomposition (Arm B)
surfaced 3–4× more unique sources than the single-query arm (A=8 vs B=27–36) with low
overlap (Jaccard 0.02–0.19), and inspection showed the extra sources are *relevant*,
including canonical primaries the broad query misses (e.g. tc2 Arm B retrieved the
original CoT paper [2201.11903] under its "evidence CoT improves reasoning" sub-question;
Arm A's top hit was a secondary reflection). Sub-questions were genuinely distinct, not
padding. The contradiction case (tc2) was the standout: it split into pro-evidence /
con-evidence / methodological-differences / conditions / reconciliation — deliberately
retrieving both poles plus the explanation, exactly how a contradiction should be
researched. The earlier hypothesis that decomposition would *hurt* tc2 was wrong.

**Atomic-query check (the "return 1" path):** two single-fact probes — *"maximum context
window of Llama 4 Maverick"* and *"year the Transformer paper was published"* — each
returned exactly **1 sub-question, unchanged**. The decomposer does not over-split atomic
queries.

---

## Stage 2 Verdict — maxCharacters: 2000

**Decision:** Set the per-record excerpt budget to **2,000 characters** (Exa highlights).

**Evidence (decomposition on; budgets 1k/2k/4k):** the source *set* is stable across
budgets (~25–37 per query) — `maxCharacters` only changes how much text per source, not
which sources. Total evidence text scales ~linearly (1k≈30k chars/query, 2k≈60–77k,
4k≈120–158k). Comparing the same source's excerpt across budgets:

- **1k** already returns substantive, on-topic spans (e.g. concrete empirical numbers),
  not front-matter — the Phase-2 `text[:600]` starvation is gone.
- **2k** adds genuinely useful framing (definitions, related-work context, comparative
  findings) with little redundancy.
- **4k** roughly doubles text with diminishing returns — marginal content is mostly
  methodology detail and begins overlapping what 2k already captured; most context-hungry.

**Why 2k:** smallest budget that reliably captures the substantive span (results *and*
framing) that 1k occasionally clips, without 4k's redundancy and context bloat. 1k is a
strong leaner alternative; 4k is not worth doubling the budget. Per synthesis call this is
~k×2k chars (with k=5 → ~10k chars ≈ 2.5k tokens), comfortably within the generator's context.

---

## Stage 3+4 Verdict — k (records per sub-question): 5

**Decision:** Set the default retrieval depth to **k = 5** records per sub-question
(at maxCharacters = 2k, decomposition on).

**Why a judged signal was needed:** Exa returns a *ranked* list but **no usable relevance
score** — the default/auto search omits `score` entirely, and `type:neural`'s "score" is
exactly normalized rank (`1.0, 0.889, …, 0`), carrying no magnitude. So "Exa-score
fall-off" is impossible; we judged relevance/coverage with an independent model
(Llama 4 Maverick, ≠ the Mistral generator).

**Stage 3 — per-record relevance by rank (0/1/2):** essentially flat and high through
rank 10; 100% of records at least partially relevant at every k; mean relevance drifts only
~3% from k=5 (1.86) to k=10 (1.81). No quality cliff — Exa keeps returning on-topic records.

**Stage 4 — cumulative coverage (completeness of the COMBINED top-k evidence, 0–100):**
the deciding measure. Coverage is flat across k — average 82.1 (k=5) / 81.6 (k=8) / 81.6
(k=10); **marginal lift 5→8 ≈ 0 and 8→10 = 0** for all four queries. The "missing aspect"
is **identical at k=5 and k=10** (e.g. "quantitative analysis", "meta-analysis",
"empirical comparison") — records 6–10 do not close the gap; they are pure redundancy for
answering the question.

**Why 5:** both metrics agree that records beyond 5 add cost (synthesis + verification load)
with no coverage gain. 5 × ~4–5 sub-questions ≈ 20–25 relevant sources/query — ample. The
Phase-3 verification loop escalates k (or reformulates) for the rare sub-question that needs it.

**Secondary insight:** the coverage ceiling (~80–85, not 100) is **not a k problem** — the
residual gap is a different *type* of evidence (meta-analytic synthesis / quantitative
comparison) that retrieving more of the same ranked list will never supply. Closing it is a
job for query reformulation in the adaptive loop, not a larger k.
