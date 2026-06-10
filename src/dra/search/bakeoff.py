"""Phase-1 search bake-off: pick the retrieval backend with data, not vibes.

Pure, unit-tested metrics (`recall_at_k`, `score_tool`) + a live orchestration
(`run_bakeoff` / `main`) that hits real free-tier APIs. Decision criteria:
recall@k vs. known seed sources, LLM-judged passage relevance, latency.
Outcome may be one winner OR a route-by-type rule (academic vs. general).
"""
from __future__ import annotations

import json
from statistics import mean
from typing import Callable

from dra.search.base import SearchTool


def normalize_url(u: str) -> str:
    u = (u or "").strip().lower()
    for pre in ("https://", "http://"):
        if u.startswith(pre):
            u = u[len(pre):]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def recall_at_k(returned_urls: list, seed_urls: list, k: int = 10) -> float:
    """Fraction of seed (known-relevant) URLs that appear in the top-k results."""
    if not seed_urls:
        return 0.0
    top = {normalize_url(u) for u in returned_urls[:k]}
    found = sum(1 for s in seed_urls if normalize_url(s) in top)
    return found / len(seed_urls)


def score_tool(tool: SearchTool, queries: list, relevance_fn: Callable, k: int = 10) -> dict:
    """Aggregate recall@k, mean judged relevance, and latency for one tool."""
    recalls, relevances, latencies = [], [], []
    for q in queries:
        res = tool.search(q["query"], k=k)
        urls = [p.url for p in res.passages]
        recalls.append(recall_at_k(urls, q.get("seed_sources", []), k))
        rels = [relevance_fn(q["query"], p.text) for p in res.passages if p.text]
        relevances.append(mean(rels) if rels else 0.0)
        latencies.append(res.latency_s)
    return {
        "tool": tool.name,
        "n": len(queries),
        "recall_at_k": round(mean(recalls), 4) if recalls else 0.0,
        "mean_relevance": round(mean(relevances), 4) if relevances else 0.0,
        "mean_latency_s": round(mean(latencies), 4) if latencies else 0.0,
    }


def run_bakeoff(tools: dict, queries: list, relevance_fn: Callable, k: int = 10) -> dict:
    """Score every tool overall and per `domain` stratum."""
    overall = {name: score_tool(t, queries, relevance_fn, k) for name, t in tools.items()}
    by_domain: dict = {}
    domains = sorted({q.get("domain", "unknown") for q in queries})
    for d in domains:
        subset = [q for q in queries if q.get("domain") == d]
        by_domain[d] = {name: score_tool(t, subset, relevance_fn, k) for name, t in tools.items()}
    return {"overall": overall, "by_domain": by_domain, "k": k}


# ---- live helpers (not unit-tested; require API access) ----

_RELEVANCE_PROMPT = (
    "Rate how relevant this passage is to the query on a 0.0-1.0 scale. "
    "Reply with ONLY the number.\n\nQuery: {query}\n\nPassage: {passage}"
)


def make_relevance_fn(judge) -> Callable:  # judge: dra.llm.bedrock.BedrockChat
    def fn(query: str, passage_text: str) -> float:
        out = judge.complete(_RELEVANCE_PROMPT.format(query=query, passage=passage_text[:2000]))
        try:
            return max(0.0, min(1.0, float(out.strip().split()[0])))
        except (ValueError, IndexError):
            return 0.0

    return fn


def load_queries(path: str = "data/bakeoff_queries.jsonl") -> list:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main():  # pragma: no cover - live integration entry point
    from dra.config import load_config
    from dra.llm.bedrock import BedrockChat
    from dra.search.exa import ExaSearch
    from dra.search.semantic_scholar import SemanticScholarSearch
    from dra.search.tavily import TavilySearch

    cfg = load_config()
    tools = {}
    if cfg.exa_key:
        tools["exa"] = ExaSearch(cfg.exa_key)
    if cfg.tavily_key:
        tools["tavily"] = TavilySearch(cfg.tavily_key)
    tools["semantic_scholar"] = SemanticScholarSearch(cfg.semantic_scholar_key)

    judge = BedrockChat(cfg.panel_models[0] if cfg.panel_models else cfg.roles["generator"], region=cfg.region)
    results = run_bakeoff(tools, load_queries(), make_relevance_fn(judge))
    with open("data/bakeoff_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results["overall"], indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
