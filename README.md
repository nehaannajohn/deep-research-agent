# Deep Research Agent (DRA)

A **transparent, reliable** deep-research agent: it decomposes a question, retrieves
evidence, extracts atomic claims, **verifies each claim against its cited sources**,
flags genuine cross-source contradictions, and composes a grounded report where every
sentence is traceable to a verified claim — with per-claim confidence surfaced.

```
query → plan → (route → Exa search → synthesize claims → verify) per sub-question
      → contradiction resolution → compose report (narrative + table/diagram)
```

The verifier is the differentiator: a small, calibrated, fine-tuned cross-encoder
(**Verifier B / v0**) that matches a 3-model LLM-judge panel on accuracy at ~130× lower
latency, and supplies the calibrated confidence that powers an optional **adaptive
retrieval** loop (re-retrieve only the low-confidence claims).

---

## Setup

Requires Python ≥ 3.11 and AWS Bedrock access (LLMs) + an Exa API key (retrieval).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # installs the `dra` package + dev tools (pytest, scipy, datasets)
cp .env.example .env             # then fill in credentials (see below)
```

**`.env` essentials** (see `.env.example` for the full list + model IDs):

| Variable | Purpose |
|---|---|
| `AWS_REGION`, `AWS_PROFILE` *(or static keys)* | Bedrock auth for the generator, verifier ensemble, and judge panel |
| `BEDROCK_GENERATOR_MODEL` / `_INLOOP_JUDGE_MODEL` / `_PANEL_MODELS` / `_VERIFIER_MODELS` | model IDs by role (kept in distinct families for independence) |
| `EXA_API_KEY` | retrieval (default backend) |
| `PERPLEXITY_API_KEY` | optional — only for the commercial-baseline comparison |

> The `eval/` datasets and trained verifier checkpoints are gitignored (large; regenerated/trained on the eval host) — **except `eval/dra_bench/`**, the curated benchmark, which is tracked.

---

## Run the agent on a question

```bash
python -m dra.cli "What are the real-world risks and benefits of synthetic data for training LLMs?"
```
Prints the grounded markdown report (narrative + per-claim verdict/confidence table + sources).

---

## Run the evaluations

The project evaluates in **two layers**: Layer 1 tests the verifier in isolation; Layer 2
tests the whole pipeline. All experiment drivers live in `experiments/code/`.

### Layer 1 — verifier in isolation (FEVER + SciFact)
3-way macro-F1 + calibration (ECE/Brier) + AUROC + latency for the fine-tuned cross-encoder.
Requires a trained checkpoint (`experiments/code/train.py`) and a GPU:
```bash
CUDA_VISIBLE_DEVICES=0 python -m experiments.code.eval_layer1 --variant v0
```

### Layer 2 — whole-pipeline eval (DRA-Bench / FRAMES / TruthfulQA)
Runs the full pipeline over a benchmark and scores every axis (EBM, grounding, relevance,
quality, formatting, task-accuracy). Pick the verifier via `--arm`:
```bash
# DRA-Bench, corrected LLM-judge ensemble:
python -m experiments.code.run_pipeline_eval --arm corrected_verifier --dataset dra_bench --workers 6
# DRA-Bench with the chosen trained verifier (v0):
python -m experiments.code.run_pipeline_eval --arm verifier_b_v0    --dataset dra_bench --workers 6
# Broad benchmarks:
python -m experiments.code.run_pipeline_eval --arm verifier_b_v0    --dataset frames --n 100
```
`--arm`: `with_verifier · without_verifier · corrected_verifier · verifier_b_v0 · verifier_b_v1 · verifier_b_v0_adaptive`

Task-accuracy uses a full-report judge (no exact-match artifact):
```bash
python -m experiments.code.rescore_task_accuracy --dataset frames --arms <result-dirs...>
```

Run the unit-test suite (no network/GPU): `pytest`

---

## Results

### Layer 1 — a small trained verifier matches the 3-model panel, ~130× faster
Combined FEVER + SciFact, n = 1,300. *macro-F1 = balanced accuracy · ECE = calibration error (lower better) · AUROC = ranking quality (higher better).*

| Verifier | macro-F1 | ECE ↓ | AUROC ↑ | latency p50 | speed-up |
|---|---|---|---|---|---|
| Three-model LLM panel | 0.815 | 0.031 | 0.936 | 2,485 ms | 1× |
| **v0 — DeBERTa-v3 (calibrated)** ✓ | **0.839** | 0.039 | **0.966** | **19 ms** | **130×** |
| v1 — DeBERTa-v3 (calibrated) | 0.834 | 0.059 | 0.962 | 19 ms | 132× |

**v0 is the chosen verifier** — it matches the panel's macro-F1 with the best ranking (AUROC) and comparable calibration, at a fraction of the cost. (v1's extra in-distribution training over-tuned it toward refutation; see `docs/archive/`.)

### Layer 2 — DRA-Bench, vs. Perplexity & OpenAI
DRA-Bench is our custom 250-prompt benchmark (5 question types) for *epistemic behavior*. Relevance/Quality are a blind 3-judge panel (1–5); "Follows format" is honoring explicit table/diagram/length requests.

| System (DRA-Bench) | Relevance | Quality | Follows format |
|---|---|---|---|
| **Ours (corrected)** | 4.66 | 4.11 | **1.00** |
| **Ours (v0 — chosen verifier)** | 4.57 | 4.03 | **1.00** |
| Perplexity (`sonar-pro`) | 4.74 | 4.94 | 0.60 |
| OpenAI (`gpt-4o-search-preview`) | 4.58 | 4.46 | 0.60 |
| *Claude Sonnet reference (ceiling)* | *4.85* | *4.90* | *0.60* |

We're on par for relevance; the commercial systems write more fluently (higher panel quality),
while **we lead decisively on following format instructions (1.00 vs 0.60)** and — unlike a
black box — expose **per-claim grounding and honest contestation**, which can't be measured on
them. Full results, significance tests, and the FRAMES/TruthfulQA tables are in `docs/archive/2026-06-13-layer2-eval-consolidated-findings.md`.

---

## Sample reports

See **[`docs/sample_reports/`](docs/sample_reports/)** for pipeline-generated reports (v0 verifier),
one per DRA-Bench question type — deep-NLP, pros-and-cons, contested, no-answer, and multi-format
(table + diagram). *(Mermaid diagrams render automatically on GitHub.)*

---

## Repository layout

```
src/dra/            the product — runnable pipeline + verifier + eval framework
  loop.py · planner · router · synthesis · verify/ · contradiction · report · adaptive/ · search/ · llm/
  eval/             evaluation framework (Layer-1 + Layer-2 harness, judges, scoring, stats)
eval/dra_bench/     the DRA-Bench dataset (tracked)
experiments/
  code/             experiment drivers (run_pipeline_eval, eval_layer1, train, rescore, …)
  results/          experiment output artifacts
docs/
  sample_reports/   example pipeline outputs (this README links here)
  archive/          findings + design docs (the full experimental record)
tests/              pytest suite
```
