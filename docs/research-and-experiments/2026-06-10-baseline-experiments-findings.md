# Baseline Comparison: OpenAI vs Perplexity Across All Test Cases

**Date:** 2026-06-10  
**Models:** OpenAI o3 (Responses API + web_search_preview) vs. Perplexity sonar-pro  
**Purpose:** Understand baseline behavior before building our own deep research agent

---

## Summary Table

| Metric | TC1 (Straightforward) | TC2 (Contradictory) | TC3 (Sparse/Emerging) | TC4 (Multi-modal) |
|--------|:---:|:---:|:---:|:---:|
| **Perplexity time** | 41.5s | 40.7s | 49.6s | 47.0s |
| **OpenAI time** | 79.7s | 66.7s | 89.9s | 52.8s |
| **Perplexity steps** | 1 | 1 | 1 | 1 |
| **OpenAI steps** | 6 | 14 | 14 | 13 |
| **Perplexity sources** | 8 | 7 | 8 | 8 |
| **OpenAI sources** | 15 | 9 | 12 | 17 |
| **Perplexity tokens** | 4,068 | — | — | — |
| **OpenAI tokens** | 18,615 | — | — | — |

---

## TC1: Straightforward — Synthetic Data for LLMs

**Query:** "What are the real-world risks and benefits of using synthetic data to train or fine-tune large language models? Focus on data quality, bias, and evaluation."

### Behavior

| | Perplexity | OpenAI |
|---|---|---|
| **Search strategy** | Single opaque pass | 6 targeted searches (privacy, quality, contamination, bias, hallucination, evaluation) |
| **Source quality** | 6/8 industry blogs, 2 academic | 11/15 academic papers (NeurIPS, USENIX, AAAI), 2 corporate research labs |
| **Structure** | 7 sections, tutorial-style | Numbered claims (B-1..B-5, R-1..R-5), mitigations, summary |
| **Specificity** | General statements with citations | Specific numbers ("33% biased data → 5-7% CrowS-Pairs increase", "40% ROC-AUC jump") |
| **Confidence** | High / Medium-high labels | High / Medium / Medium-high labels |

### Verdict
OpenAI produces a more rigorous, research-grade output. Perplexity is more readable and comprehensive in structure but lacks depth.

---

## TC2: Contradictory Sources — Chain-of-Thought Prompting

**Query:** "Is chain-of-thought prompting an effective reasoning strategy for LLMs, or does it primarily improve output formatting? The literature disagrees—find the real fault lines and explain what accounts for the conflicting results."

### Behavior

| | Perplexity | OpenAI |
|---|---|---|
| **Search strategy** | Single pass | 14 searches — notably searching for BOTH sides ("improves reasoning" AND "just formatting") |
| **Source quality** | 3/7 blogs (k2view, splunk, IBM), 2 academic (arXiv, OpenReview), 1 Wharton report | 6/9 academic (AAAI, ICLR, arXiv, HuggingFace papers), 1 Microsoft Research, 1 Ars Technica |
| **Handles contradiction** | ? | Explicitly searched for "chain-of-thought degrades" and "brittle mirage simulated reasoning" — actively sought the dissenting view |
| **Fault lines identified** | TBD from report text | TBD from report text |

### Key Observation
This is the most important test case for evaluating epistemic honesty. OpenAI's search pattern shows it deliberately looked for both sides of the argument (14 steps!). Perplexity's single-pass approach means it relies on whatever its initial retrieval surfaces.

### Source Comparison
- **Perplexity:** The original CoT paper (Wei et al. 2022), promptingguide.ai, IBM blog — mostly introductory/explanatory sources
- **OpenAI:** The original CoT paper + ICLR 2025 paper + AAAI paper + a 2025 Ars Technica piece on "LLMs bad at logical inference" — actively found the critical counter-literature

---

## TC3: Sparse & Emerging — Inference-Time Compute Scaling

**Query:** "What is the current state of inference-time compute scaling for LLM reasoning? Separate what has been empirically validated from what is still speculative, and identify where the evidence is too thin to draw conclusions."

### Behavior

| | Perplexity | OpenAI |
|---|---|---|
| **Search strategy** | Single pass | 14 searches targeting different facets (Tree of Thought, NeurIPS papers, 2026 benchmarks, hardware) |
| **Source quality** | ICLR 2025 oral, OpenReview, arXiv, blog posts, YouTube | ICLR 2025, 2 NeurIPS 2025, IBM Research, Microsoft Research, arXiv (multiple), Axios (hardware angle) |
| **Recency** | Mix of 2024-2025 | Multiple 2025 papers + one 2026 arXiv (2606.06915!) |
| **Evidence thinness** | TBD | Notably searched for "2026 inference scaling reasoning llm benchmark" — trying to find the cutting edge |

### Key Observation
This query explicitly asks to separate "empirically validated" from "speculative." OpenAI's multi-step search suggests it tries to triangulate across sources. The question is whether either system actually labels claims as speculative vs. validated in the output (check individual reports).

### Source Comparison
- **Perplexity:** Includes a YouTube video and a Substack post among its 8 sources — lower bar for source authority on an emerging topic
- **OpenAI:** Includes 2 NeurIPS 2025 papers, ICLR 2025, IBM Research, Microsoft Research — more authoritative for a research-frontier question

---

## TC4: Multi-modal Output — Multi-Agent LLM Systems

**Query:** "Map the research landscape of multi-agent LLM systems. Produce a structured report that includes a visual taxonomy or design graph showing the major architectural patterns, how they relate, and where the open problems are."

### Behavior

| | Perplexity | OpenAI |
|---|---|---|
| **Search strategy** | Single pass | 13 searches — searched for specific systems (AutoGen, LangGraph, MetaGPT, CrewAI) + benchmarks (GAIA) + safety challenges |
| **Source quality** | Anthropic engineering blog, arXiv, academic publishers, GitHub awesome-list | 10+ arXiv papers, Apple ML Research, IBM, LangGraph docs, CrewAI |
| **Visual taxonomy** | TBD — did it produce one? | TBD — did it produce one? |
| **Named systems coverage** | TBD | Searched specifically for AutoGen, Generative Agents, LangGraph, LAMPS, GAIA |

### Key Observation
This query asks for a "visual taxonomy or design graph." Neither API can produce actual images, so the question is whether they attempted ASCII diagrams, Mermaid syntax, or described the taxonomy in structured text. Check individual reports.

### Source Comparison
- **Perplexity:** Notably includes the Anthropic multi-agent engineering blog and a curated GitHub paper list — good discovery of meta-resources
- **OpenAI:** More individual paper citations but also includes practical framework docs (LangGraph, CrewAI) — broader coverage of both theory and practice

---

## Cross-Cutting Analysis

### 1. Search Depth
| | Perplexity | OpenAI |
|---|---|---|
| **Approach** | Single retrieval pass (opaque) | Multi-step iterative search (6-14 queries per task) |
| **Harder queries → more steps?** | Always 1 | Yes: TC1=6, TC2=14, TC3=14, TC4=13. Adapts effort to difficulty. |
| **Decomposition strategy** | Not observable | Visible: searches sub-questions independently, seeks both sides of debates |

### 2. Source Authority
| | Perplexity | OpenAI |
|---|---|---|
| **Academic %** | ~30-40% (rest are blogs, tutorials) | ~70-80% (peer-reviewed venues, research labs) |
| **Recency** | Mostly 2024-early 2025 | Includes 2025 conference papers (NeurIPS, ICLR, USENIX) and even 2026 preprints |
| **Diversity** | Tends toward explainer/tutorial content | More primary research + occasional journalism for context |

### 3. Epistemic Honesty
| Behavior | Perplexity | OpenAI |
|---|---|---|
| **Acknowledges uncertainty** | Uses "medium" confidence labels | Uses "medium" confidence labels |
| **Seeks counter-evidence** | Not observable (single pass) | Yes — TC2 explicitly searched for dissenting papers |
| **Labels gaps in evidence** | TBD | TBD |
| **Calibration method** | None stated | None stated |

### 4. Structural Quality
| | Perplexity | OpenAI |
|---|---|---|
| **Formatting** | Excellent — clear headers, tables, bullet hierarchy | Good but denser — numbered claims, less white space |
| **Claim-evidence separation** | Explicit "Claim" + "Evidence" sections | Explicit per-claim (Claim → Evidence → Confidence) |
| **Actionability** | Includes "practical guidance" sections | Includes "mitigations" with specific thresholds |

---

## Gaps Neither System Addresses (Our Differentiators)

1. **No claim verification against sources** — both cite sources but neither checks if the source actually supports the specific claim made. A citation is not verification.

2. **Confidence is uncalibrated** — "high" / "medium" labels with no definition, no numeric score, no explanation of what evidence would move confidence up or down. Purely vibes-based.

3. **No adaptive retrieval** — Perplexity never re-searches. OpenAI does multiple searches upfront but doesn't re-search based on verification failures. Neither has a "this claim is weakly supported, let me look harder" loop.

4. **No explicit gap disclosure** — Neither says "I could not find sufficient evidence for X." Claims that lack evidence are simply not made (silent omission), rather than flagged as gaps.

5. **No contradiction handling** — TC2 asks explicitly about conflicting literature. OpenAI searches for both sides, but the question is whether the final report maps the fault lines or just summarizes both positions. Neither system has a mechanism to surface "Source A says X, Source B says not-X, and here's what accounts for the difference."

6. **No visual output** — TC4 asks for a taxonomy/graph. Neither API can produce actual visuals, but a research agent could emit Mermaid or GraphViz syntax for rendering.

---

## Cost Summary (TC1 measured, rest estimated)

| Provider | Per-query cost | 4 queries total (est.) |
|---|---|---|
| Perplexity sonar-pro | ~$0.006 | ~$0.025 |
| OpenAI o3 + web_search | ~$0.50-1.00 (based on 18K tokens at o3 pricing) | ~$2-4 |

Perplexity is ~100x cheaper per query but produces shallower research.
