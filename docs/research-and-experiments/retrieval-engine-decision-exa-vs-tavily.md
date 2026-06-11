# Search-tool decision (Phase 1 bake-off)

**Date:** 2026-06-09 · **Decision: use Exa as the default retrieval backend.**

## Method
12 stratified queries (`data/bakeoff_queries.jsonl`) across `technical / general / hard-to-source`. For each tool × query: top-k retrieved, **recall@k** vs. known seed URLs (exact match, arxiv abs/pdf canonicalized), **judged relevance** of the top-5 passages (0–1, rated by Mistral Large 3), and **latency**. Aggregated overall + per domain (`data/bakeoff_results.json`).

## Results (overall)
| tool | recall@k | relevance | latency | errors |
|---|---|---|---|---|
| **exa** | **0.333** | **0.919** | **1.4s** | 0 |
| tavily | 0.250 | 0.764 | 3.5s | 0 |
| semantic_scholar | 0.000 | 0.000 | 0.2s | 0 |

Per-domain: Exa technical recall **0.80** / rel **0.98**; general rel 0.87; hard-to-source rel 0.89. Tavily technical recall 0.60 / rel 0.85; lower + ~2.5× slower elsewhere.

## Decision & rationale
- **Exa** is best on **every axis** (relevance, recall, latency) and is strong on **both** academic and general/web — so a single backend covers all domains for the MVP. No route-by-type needed now (routing remains in the full design).
- **Tavily** = viable fallback (works, but slower and lower relevance).
- **Semantic Scholar** = deprioritized: keyless calls are rate-limited (429), and it's redundant with Exa for papers. (Our run also hit a config footgun — an inline comment in `.env` was parsed as the API key → 403. Fixed in `.env.example`.)

## Multi-judge cross-check (relevance)
The bake-off relevance was single-judge (Mistral). We re-rated Exa vs. Tavily with the **panel** (GPT-OSS 120B, Opus 4.8, DeepSeek R1 — independent of Mistral) over 72 passages (`data/relevance_crosscheck.json`):

| Judge | Exa | Tavily |
|---|---|---|
| GPT-OSS 120B | 0.943 | 0.794 |
| Opus 4.8 | 0.914 | 0.819 |
| DeepSeek R1 | 0.819 | 0.692 |
| panel mean | 0.892 | 0.768 |
| Mistral (orig.) | 0.919 | 0.764 |

**All four judges rank Exa > Tavily** by a consistent ~0.12 margin; Mistral matches the panel mean (not an outlier). Inter-judge agreement (pairwise Pearson): 0.70–0.83. DeepSeek R1 is strictest but agrees on ordering. Decision confirmed.

## Caveats
- `recall@k` is exact-URL and only defined for queries with seed URLs (the technical set); **judged relevance is the cross-domain signal**.
- Small N (12 queries). Re-run if we expand the query set.

Wired as default in `src/dra/search/__init__.py::default_search_tool`.
