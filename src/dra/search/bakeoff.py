"""Phase-1 search bake-off: pick the retrieval backend with data, not vibes.

Pure, unit-tested metrics (`recall_at_k`, `score_tool`) + a live orchestration
(`run_bakeoff` / `main`) that hits real free-tier APIs. Decision criteria:
recall@k vs. known seed sources, LLM-judged passage relevance, latency.
Outcome may be one winner OR a route-by-type rule (academic vs. general).
"""
from __future__ import annotations

import json
import re
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
    u = u.split("#")[0].split("?")[0].rstrip("/")
    # canonicalize arxiv abs/pdf (+ version suffix) to one form so they match
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", u)
    if m:
        return f"arxiv.org/abs/{m.group(1)}"
    return u


def recall_at_k(returned_urls: list, seed_urls: list, k: int = 10) -> float:
    """Fraction of seed (known-relevant) URLs that appear in the top-k results."""
    if not seed_urls:
        return 0.0
    top = {normalize_url(u) for u in returned_urls[:k]}
    found = sum(1 for s in seed_urls if normalize_url(s) in top)
    return found / len(seed_urls)


JUDGE_TOP_N = 5  # judge relevance on the top-N passages only (cost control)


def _score_query(tool: SearchTool, q: dict, relevance_fn: Callable, k: int) -> dict:
    try:
        res = tool.search(q["query"], k=k)
    except Exception as exc:  # one API hiccup shouldn't kill the whole bake-off
        return {"domain": q.get("domain", "unknown"), "recall": 0.0,
                "relevance": 0.0, "latency": 0.0, "error": str(exc)[:80]}
    urls = [p.url for p in res.passages]
    judged = [p for p in res.passages if p.text][:JUDGE_TOP_N]
    rels = [relevance_fn(q["query"], p.text) for p in judged]
    return {
        "domain": q.get("domain", "unknown"),
        "recall": recall_at_k(urls, q.get("seed_sources", []), k),
        "relevance": mean(rels) if rels else 0.0,
        "latency": res.latency_s,
    }


def _aggregate(records: list, tool_name: str) -> dict:
    if not records:
        return {"tool": tool_name, "n": 0, "recall_at_k": 0.0, "mean_relevance": 0.0,
                "mean_latency_s": 0.0, "errors": 0}
    return {
        "tool": tool_name,
        "n": len(records),
        "recall_at_k": round(mean(r["recall"] for r in records), 4),
        "mean_relevance": round(mean(r["relevance"] for r in records), 4),
        "mean_latency_s": round(mean(r["latency"] for r in records), 4),
        "errors": sum(1 for r in records if r.get("error")),
    }


def score_tool(tool: SearchTool, queries: list, relevance_fn: Callable, k: int = 10) -> dict:
    """Aggregate recall@k, judged relevance, and latency for one tool."""
    return _aggregate([_score_query(tool, q, relevance_fn, k) for q in queries], tool.name)


def run_bakeoff(tools: dict, queries: list, relevance_fn: Callable, k: int = 10) -> dict:
    """Search + judge each tool x query ONCE; aggregate overall and per `domain`."""
    records = {name: [_score_query(t, q, relevance_fn, k) for q in queries] for name, t in tools.items()}
    overall = {name: _aggregate(recs, name) for name, recs in records.items()}
    by_domain: dict = {}
    for d in sorted({q.get("domain", "unknown") for q in queries}):
        by_domain[d] = {
            name: _aggregate([r for r in recs if r["domain"] == d], name)
            for name, recs in records.items()
        }
    return {"overall": overall, "by_domain": by_domain, "k": k}


# ---- live helpers (not unit-tested; require API access) ----

_RELEVANCE_PROMPT = (
    "Rate how relevant this passage is to the query on a 0.0-1.0 scale. "
    "Reply with ONLY the number.\n\nQuery: {query}\n\nPassage: {passage}"
)


def make_relevance_fn(judge) -> Callable:  # judge: dra.llm.bedrock.BedrockChat
    def fn(query: str, passage_text: str) -> float:
        out = judge.complete(_RELEVANCE_PROMPT.format(query=query, passage=passage_text[:2000]))
        m = re.search(r"\d*\.?\d+", out)
        if not m:
            return 0.0
        try:
            return max(0.0, min(1.0, float(m.group())))
        except ValueError:
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

    # Use the fast, non-reasoning generator (Mistral) to rate relevance in the bake-off.
    judge = BedrockChat(cfg.roles["generator"], region=cfg.region)
    results = run_bakeoff(tools, load_queries(), make_relevance_fn(judge))
    with open("data/bakeoff_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results["overall"], indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
