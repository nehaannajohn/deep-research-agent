---
title: "Design vs. Landscape — Gap Analysis"
subtitle: "Deep Research Agent · our design document vs. the 2026 landscape report"
date: "2026-06-10"
---

# Design vs. Landscape — Gap Analysis (2026-06-10)

## Purpose

Compare our design document (`docs/superpowers/specs/2026-06-09-deep-research-agent-design.md`)
against the landscape report (`docs/research/deep-research-agent-landscape-report.md`) to (a)
surface ideas worth adopting and (b) record where we are genuinely differentiated. A backlog of
candidate improvements for future experiments — not a commitment.

**Caveat:** the landscape report was compiled alongside our design (it contains a "Pattern G:
Your DRA design" entry and a "Design Validation" appendix), so its praise is partly
self-referential. This analysis is the *critical* read — real gaps and real divergences, not the
report's self-validation.

## Actionable backlog — adopt / defend / defer

| # | Item | Source pattern/paper | Action | Rationale |
|---|------|----------------------|--------|-----------|
| 1 | **Adversarial "Skeptic" refutation step** for `weak`/`contested` claims | Pattern F (MARs, PROClaim) | **Adopt** (verifier slice) | Moves verification from "is it supported?" to "can it be broken?"; composes with our verdict routing. We only hint at this today ("seek disconfirming evidence"). |
| 2 | **Bound retrieval budget as an evidence-cited rule** | "Cited but Not Verified" (−42% acc, 2→150 calls) | **Adopt** (make explicit) | External validation of lean k=5 / max_iters≈3; promote the cap from a termination condition to a first-class design rule. |
| 3 | **Split generator role: claim-extractor vs. report-composer** | our generator-comparison finding | **Adopt** (design clarification) | Lean model wins claim extraction (faithfulness); a stronger model may still help final prose composition. The landscape blurs these. |
| 4 | **Step/process-level faithfulness signal** | VERITAS, HiPRAG, PRA | **Defer** (RL ext. + eval) | "Faithfulness ≠ correctness" — endpoint-only entailment misses unfaithful reasoning. Adds a reward/eval axis. |
| 5 | **On-demand retrieval** (skip search when a sub-q needs none) | Self-RAG `[Retrieval]` token | **Defer** | Retrieval-side cousin of "decompose only when needed"; efficiency win, not correctness. |
| 6 | **Search Intensity Scaling** (learned escalation of retrieval depth) | DeepDiver (NeurIPS) | **Defer** (RL appendix) | The learnable form of our rule-based k/maxChars escalation; design-only until training is in scope. |
| 7 | **Multi-perspective decomposition** for breadth queries | STORM | **Defer** | Improves coverage on "map the landscape"-type prompts (our tc4); decomposer enhancement. |
| 8 | **Judge-time compute scaling** | Verdict (2502.18018) | **Defer** (eval harness) | Raises judge-panel reliability when we build the offline eval. |
| 9 | **LangGraph for the Phase-3 loop** | landscape §3.1/§7.2 (strong rec) | **Defend or adopt** (decide) | Design names it; we leaned hand-rolled. Must justify either way ("what did the framework buy / cost?"). |
| 10 | **Source credibility scoring** | tarun7r/deep-research-agent | **Defer** | `reliability_note` exists in the schema but isn't actively scored. |

## Where we are differentiated / ahead

Per the landscape's own §6 (Gaps) and validation appendix — these are the field's *open* problems,
and our design addresses them:

- **The unified loop** — verification + calibrated confidence + adaptive retrieval *together* (3/3;
  Self-RAG, the closest, is 2/3). "Almost no deployed system" combines all three.
- **Calibrated per-claim confidence** (ECE + temperature/isotonic) — "none deployed, only academic."
- **Verbatim evidence, never summarized** · **enforced model independence** (`assert_independence()`)
  · **statistical rigor** (Cohen's κ / McNemar / Holm) — each a landscape gap with ~no OSS precedent.
- **Claim ledger with epistemic status** (supported/contested/insufficient; nothing silently dropped).
- **`expected_behavior`-labeled DRA-Bench** — grades *whether the system did the right thing*
  (clarify / report-insufficient / flag-contested), distinguishing plausible from correct.

**Empirical results this session that go beyond the report's generic advice:**

- **We contradicted the landscape's generator assumption with data.** Its §3.2 recommends a *big*
  model as generator for "best long-form quality." Our 3-judge-panel experiment found the opposite
  for *grounded claim extraction*: lean **Llama 4 Maverick (17B)** beats **Mistral Large 3 (675B)**
  on grounding (unanimous) — the big model over-reaches from parametric memory. Insight: the
  "generator" splits into claim-*extractor* (lean wins) vs. report-*composer* (big may help).
- **We measured retrieval depth/budget** (cumulative coverage → k=5) and excerpt budget (→ 2k)
  rather than asserting them; surfaced that Exa exposes no usable relevance score (rank-only).

## Divergences to decide consciously

- **LangGraph** — landscape strongly recommends; we leaned hand-rolled. Decide for Phase 3 and be
  ready to defend.
- **Model instances** — landscape suggests generator=Claude, verifier=GPT/Gemini; we use
  generator=Llama, verifier=Mistral, panel=GPT-OSS/Opus/DeepSeek. Same *principle* (family
  diversity), different instances — and ours are now empirically grounded, a stronger position.

## Top picks if we run another round

If/when we revisit: **(1) adversarial Skeptic step** and **(3) generator-role split** are the
highest-leverage, lowest-cost adoptions that strengthen the core thesis (verifiable grounding)
without new infrastructure. **(9) the LangGraph decision** should be settled before Phase 3 starts.
