# Verifier Selection — Decision (CONFIRMED at Layer 1)

**Date:** 2026-06-11 · **Experiment:** `experiments/verifier_comparison.py` · **Bench:** 60 panel-validated adversarial examples (supported 16 · refuted 15 · insufficient 16 · contested 13), built from the 4 brief cases.

## Decision

**Selected verifier (CONFIRMED): the 3-model ENSEMBLE `{Sonnet, Mistral, Amazon Nova}`** — majority-vote label, cross-model **agreement** as the (raw) confidence.

> **CONFIRMED at Layer 1 (2026-06-11).** The provisional selection was validated on the real benchmarks — FEVER (n=1000) + SciFact (n=300) + 75/dataset constructed contested — and the ranking did **not** change. 4-way macro-F1 **0.845** (FEVER) / **0.842** (SciFact); held-out ECE **0.102 → 0.031**; **AUROC 0.936**; conservative error profile (small false-confidence cells; misses go to `refuted`, not `supported`); contested precision ~1.0 with **zero** false positives. Full write-up + caveats — including the contested **upper-bound** construction — in [`docs/research-and-experiments/2026-06-11-layer1-verifier-eval-findings.md`](../../../docs/research-and-experiments/2026-06-11-layer1-verifier-eval-findings.md). The final A-vs-B word waits on the **Layer-2 cross-check** once Verifier B (DeBERTa) lands.

## Results

| candidate | macro-F1 | reasoning q | rec q | latency (60 ex) | confidence values |
|---|---|---|---|---|---|
| **ensemble** | **1.000** | **4.53** | **4.39** | 193s | {0.667, 1.0} |
| nova | 1.000 | 3.62 | 3.82 | 193s | {0.6, 1.0} |
| sonnet | 0.983 | 4.48 | 4.35 | 582s | {1.0} |
| mistral | 0.935 | 4.24 | 4.18 | 178s | {0.6, 0.8, 1.0} |

## Why the ensemble

Macro-F1 **saturated** (two candidates perfect, a third 0.983), so label accuracy did **not** discriminate. On the axes that did:
- **Reasoning/recommendation quality** (the signal that feeds the adaptive loop): ensemble best (4.53 / 4.39).
- **Confidence informativeness:** the ensemble is the only candidate whose confidence carries signal — it drops to **0.667 exactly on the contended cases** and is 1.0 elsewhere. The solos' self-consistency confidence saturates; **Sonnet's is a useless constant 1.0** (it was even 1.0 on its one wrong prediction — confidently wrong).
- **Error correction:** on the `insufficient` cases at bench indices 6/10/13, **Mistral systematically mislabels `insufficient → supported`** (the dangerous false-confidence direction); the ensemble **outvotes** that error (Sonnet+Nova) and its 0.667 confidence flags the disagreement.

Nova ties on labels but has the weakest reasoning and near-flat confidence; Mistral has the real label weakness; Sonnet is strong but 3× slower and its confidence is non-informative.

## Caveats (carried to Layer 1)

1. **Bench saturation:** the 60 examples survived a panel-agreement gate, so they're by-construction clear-cut → macro-F1 can't discriminate. The real test is FEVER/SciFact (high-N). (`limitations.md #1`.)
2. **Mild self-preference risk on quality:** the quality panel includes **Opus (Anthropic)** and the ensemble contains **Sonnet (Anthropic)** — the accepted, diluted overlap.
3. **Quality is single-vote, n=180, no significance testing.** (`limitations.md #1`.)
4. **Cost:** the ensemble runs 3 models per claim (1 call each) — comparable latency to a solo at N=5 here, but it is 3 model calls in-loop per verification.

## Artifacts
- `summary.json` — per-candidate macro-F1 / per-class / quality / latency.
- `bench.json` — the 60 validated examples (intended label + panel labels).
- `comparison_sample.{md,csv}`, `comparison_sample_detailed.json` — 20-example side-by-side (pred·conf·recommendation·reasoning).
- `confidence_stats.json` — per-candidate confidence (mean, when-correct, when-wrong).
