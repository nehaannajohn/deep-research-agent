# Stage 3+4 Verdict — k (records per sub-question): 5

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
