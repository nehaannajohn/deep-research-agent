# Calibration Strategy — Deep Research Agent

> **Compiled:** 2026-06-11
> **Scope:** How we produce calibrated per-claim confidence across the different verifier models (white-box and black-box), and how we evaluate calibrated vs. raw confidence.
> **Context:** Supports the transparency thesis — confidence is surfaced per claim and drives the τ threshold, so it must *mean* something. Raw scores are typically miscalibrated; we never surface them directly. Companion: `2026-06-11-evaluation-strategy.md`.

---

## 1. Calibration is post-hoc — it never needs model weights

Recalibration is a **transformation applied to the model's output scores**, fit on a held-out labeled set. The calibrator is a tiny separate model (1–2 parameters) trained on `(raw_score, was_it_correct?)` pairs. **It never touches the underlying model's weights** — true for the fine-tuned DeBERTa (we freeze it and calibrate its softmax) and equally true for a closed foundation model.

So "no weight access" is **not** an obstacle to calibration. The only thing weight/white-box access changes is the **source of the raw confidence signal** (§2). The recalibration step (§3) is identical regardless.

---

## 2. Where the raw confidence signal comes from (per model)

| Verifier | Access | Raw signal | Notes |
|---|---|---|---|
| **B — DeBERTa cross-encoder** | White-box | Softmax probability over verdict classes | Direct; the cleanest signal |
| **A — foundation LLM judge** | Black-box (no weights) | **Self-consistency agreement** (default) — sample the judge N times at temp > 0; fraction agreeing = confidence | Best-calibrated black-box option; already the chosen design for Verifier A |
| **A — foundation LLM judge** | Black-box | Token logprob of the `supported`/`true` token (if the API exposes logprobs) | Cleaner than verbalized when available |
| **A — foundation LLM judge** | Black-box | Verbalized confidence ("0–100") | Weak fallback — clusters on round numbers, overconfident; recalibratable but noisy |

For a model we can't open up, we elicit a proxy signal (preferably self-consistency agreement) and treat the model as a black-box score generator.

---

## 3. Recalibration method

Fit on a **held-out calibration split** with ground-truth labels (FEVER / SciFact — the same Layer-1 data; calibration needs labels regardless of model access).

- **Default: Platt scaling** — logistic regression on the raw score. Robust, low-data, the natural fit for a black-box scalar (agreement fraction or verbalized number).
- **If needed: isotonic regression** — non-parametric, monotonic, more flexible. Use when Platt under-fits the reliability curve, but it needs more calibration data and can overfit small sets.
- **Temperature scaling — only where logits exist.** It scales pre-softmax logits, so it applies to the DeBERTa (and logprob signals), not to a pure agreement/verbalized signal. For those, use Platt/isotonic.

**Default decision: Platt scaling everywhere; fall back to isotonic per model only if its reliability diagram shows non-logistic shape.**

---

## 4. Binary vs. per-class probability

Verdicts are multi-class: `{supported, refuted, insufficient, contested}`. Two options for what we calibrate:

| Approach | What it calibrates | When | Status |
|---|---|---|---|
| **Binary** (default) | Collapse to "supported vs. not"; calibrate a single scalar | MVP — enough for the τ threshold and the report's per-claim confidence; simple and defensible | **Default** |
| **Per-class** | Calibrated probability for each verdict class | When we need trustworthy probabilities on `contested` / `insufficient`, not just `supported` | Post-MVP extension |

Per-class is done via **one-vs-rest Platt** (one calibrator per class) or, for a jointly-normalized distribution, **Dirichlet / vector scaling**. Deferred to the design's extension scope; binary is the MVP choice.

---

## 5. Evaluating calibration (calibrated vs. non-calibrated)

The headline question: *does recalibration actually improve calibration?* We measure it on a held-out **test** split (separate from the calibration-fit split).

| Metric | Role |
|---|---|
| **ECE (Expected Calibration Error)** | **Primary.** Reported **before vs. after** recalibration — the headline number. Lower = better calibrated |
| **Brier score** | Combined calibration + sharpness; guards against a trivially-flat calibrator |
| **Reliability diagram** | Qualitative — how close predicted confidence tracks empirical accuracy (the diagonal) |

**Success criterion:** post-recalibration ECE drops materially and the reliability diagram moves toward the diagonal, without Brier degrading (which would signal lost sharpness). This is the calibration arm of **Experiment #1** in the design (Verifier A vs B: F1 + ECE before/after).

---

## 6. Defaults at a glance

| Question | Default |
|---|---|
| Need weights to calibrate? | **No** — post-hoc, on output scores |
| Raw signal for black-box LLM judge | **Self-consistency agreement** (logprobs if exposed; verbalized as weak fallback) |
| Recalibration method | **Platt scaling**; isotonic if reliability curve demands it |
| Logits required? | Only for temperature scaling (white-box / logprob signals) |
| Binary or per-class | **Binary** for MVP; per-class (one-vs-rest Platt / Dirichlet) post-MVP |
| Evaluation metric | **ECE before/after** (primary) + Brier + reliability diagram |
| Calibration-fit data | Held-out split of **FEVER / SciFact** (needs labels) |
