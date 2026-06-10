# Stage 2 Verdict — maxCharacters: 2000

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
