---
title: "Adaptive Retrieval — confidence-gated loop with parallel repair"
subtitle: "Deep Research Agent · the capstone experiment: spend retrieval effort only where the verifier's calibrated confidence says it's needed"
date: "2026-06-14"
---

# Adaptive Retrieval — design

The final experiment of the project. It attacks the one ceiling every prior result converged on — **retrieval breadth / source quality**, not the verifier — by adding a feedback loop that re-retrieves *selectively*, only where evidence is weak.

## 1. What the data forced

Two findings on the `corrected_verifier` DRA-Bench reports reshaped the design:

1. **The verifier's *recommended action* is an unreliable trigger.** Recommendations come from a deterministic verdict→action map (`supported→accept`, `insufficient→gather_more`, `refuted→revise`, `contested→flag_contested`). But cross-checking each verdict against the independent grounding judge:
   - `accept` is **96% reliable** (3931 / 4099) — but it never triggers retrieval.
   - `gather_more` (insufficient) is **~49% reliable** (20 of 41) — a coin flip; half the "insufficient" claims are actually grounded.
   - `revise` (refuted) **~62%** (8 of 13).
   The verifier is reliable exactly where it does **not** trigger retrieval, and unreliable where it does — and the triggers are sparse (~1.2% of claims) and skewed to **type-4 (unanswerable)**, where more retrieval cannot help.
2. **Calibrated confidence is the trustworthy signal.** The verifier's confidence is well-calibrated (held-out ECE 0.031; the fine-tuned v0 is calibratable too). So the loop is driven by **confidence as a gate**, never by the discrete label.

**Design consequence:** do not route on the action recommendation. Use **low calibrated confidence** to decide *whether* to act and *when* to stop; let the *outcome* decide *which* repair to keep.

## 2. The loop (claim-level gate)

The gate is **per claim**, not per sub-question. A trigger-rate probe on DRA-Bench (50 queries, v0 + the new per-label calibration) settled this: taking the *min* confidence over a sub-question's ~8 claims trips **~62% of sub-questions** — blanket, not adaptive — because one weak claim among eight drags the whole section down. The individual weak claims are only **~22% of all claims at τ=0.7** (8% at 0.5, 14% at 0.6). So we trigger on the **claim** and repair the **claim**. Mean per-claim calibrated confidence is 0.76; the weak tail is concentrated in type-4 (no-answer) and type-2 (pros/cons).

For each claim whose calibrated predicted-label confidence is **below τ (=0.7)**, max **3 iterations**:

1. **Iteration 1 = the existing single pass** (frozen — every claim keeps its text + confidence; no regeneration).
2. For each below-τ claim, run **two repairs in parallel**, each targeting *that claim's proposition*:
   - **Reformulate** — draft a focused search query for the claim's specific assertion, re-retrieve (Exa), and re-verify the claim against the new evidence.
   - **Diversify sources** — route retrieval to a **different channel than Exa**, not more Exa records (a bigger Exa pull returns the same pool — useless). A **data-source recommender** (Sonnet), *told the incumbent evidence came from Exa's broad web index*, picks complementary connectors that add **non-overlapping** coverage (e.g. peer-reviewed literature via Semantic Scholar) and re-verifies against them. Source types we have no connector for (government statistics, clinical registries, …) are logged as **coverage gaps** — a retrieval-ceiling finding — not silently skipped.
   **Keep the candidate verdict with the highest calibrated confidence** — the incumbent included, so a repair must *beat* it to win. A repair may also legitimately *flip* a weakly-supported claim to refuted/contested; that is a correction, not a regression.
3. **Terminate a claim** when any holds: confidence ≥ **τ** · **no-progress** (Δconfidence < ε — neither repair beat the incumbent) · **max 3 iterations** · budget. A claim that never clears τ stays as-is, surfaced with its low confidence (the honest outcome).

Only below-τ claims iterate; the other ~78% stay frozen. At τ=0.7 this repairs **~22% of claims** (≈4.6 per query; ~84% of queries get *some* small targeted repair, but only one claim in five is ever re-retrieved) — selective *spend*, not blanket re-retrieval.

## 3. Why the fine-tuned verifier is the enabler

The loop needs a **calibrated confidence** signal **and** cheap **re-verification every iteration**. The fine-tuned **v0** cross-encoder supplies both — calibrated scores (Platt) and a ~free local forward pass. Re-verifying with the 3-LLM ensemble each iteration would be cost-prohibitive. So the Verifier-B work is the prerequisite that makes adaptive retrieval practical — the project's through-line: a small, calibrated, cheap verifier turns a static pipeline into an affordable feedback loop.

## 4. Key decisions & assumptions

- **Gate, not action-map.** Confidence decides *when* to act/stop; the repair is chosen by outcome (keep the higher-confidence candidate), so the unreliable `insufficient`/`refuted` labels are never acted on.
- **Verifier = fine-tuned v0** (calibrated + cheap re-verify). The ensemble would also calibrate but is too expensive to re-run per iteration.
- **Two repairs, outcome-selected.** Reformulation targets *wrong question framing*; source-diversification targets *thin/idiosyncratic sources* (the coverage ceiling). Running both and keeping the winner avoids guessing which failure mode applies.
- **Data-source recommender = Sonnet**, told the incumbent evidence is from Exa and asked for **complementary channels Exa does not cover** — it must add *new* sources, never re-query Exa. It selects from the available connectors (Semantic Scholar today); recommended source types we have no connector for are logged as coverage gaps. This is the mechanism that actually attacks the retrieval ceiling: a different *channel*, not a bigger Exa pull.
- **Targeted, frozen-upstream.** Reformulating/diversifying one sub-question must not disturb the other sub-questions' claims — they're reused untouched.
- **Cost behaviour is a designed outcome:** unanswerable → no-progress → early stop (low cost); answerable-but-thin → iterate to τ; settled → no iterations. The experiment reports iteration-cost **by DRA-Bench type** as a first-class result.
- **Thresholds:** `τ = 0.7` (claim-level), chosen from the trigger probe — fires on ~22% of claims, concentrated where retrieval can plausibly help; `ε` (no-progress) and `max_iters = 3` tuned on the pilot.

## 5. The experiment (see the implementation plan)

- **Pilot:** ~15–20 DRA-Bench queries spanning all 5 types (with at least one low-confidence sub-question) → compare pipeline **with vs without** adaptive retrieval on every Layer-2 metric + **iteration/latency cost by type**.
- **Decision gate:** improvement → run full DRA-Bench + FRAMES + TruthfulQA; no improvement / regression → analyze regressed samples, apply a minimal fix, re-run.
- **Headline questions:** (1) does adaptive retrieval beat the 1-iteration pipeline on Layer-2? (2) what is the cost-by-type curve — is effort spent where it should be (high on multi-perspective, low on settled and on unanswerable)?

*Related: the retrieval-ceiling finding (`limitations.md` #9 + `2026-06-13-layer2-eval-consolidated-findings.md`); the verifier that enables this (`2026-06-11-layer1-verifier-eval-findings.md` §4B); MVP architecture (`2026-06-14-mvp-architecture.md`), where this loop is the dashed Phase-3 edge.*
