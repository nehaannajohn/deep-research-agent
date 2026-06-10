# Stage 1 Verdict — Decomposition: KEEP (conditional split, validated)

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

**Implication for Stage 2:** run the maxCharacters sweep WITH decomposition
(`python -m experiments.decomposition_retrieval charsweep`, no `--no-decompose`).
