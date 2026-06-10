from dra.schemas import Passage
from dra.search.base import SearchResult, SearchTool
from dra.search.bakeoff import normalize_url, recall_at_k, run_bakeoff, score_tool


def test_normalize_url():
    assert normalize_url("http://www.X.com/") == "x.com"
    assert normalize_url("https://arxiv.org/abs/2201.11903") == "arxiv.org/abs/2201.11903"


def test_normalize_url_canonicalizes_arxiv():
    abs_url = normalize_url("http://arxiv.org/abs/2201.11903")
    pdf_url = normalize_url("https://arxiv.org/pdf/2201.11903v1")
    assert abs_url == pdf_url == "arxiv.org/abs/2201.11903"


def test_recall_at_k_counts_seeds_found():
    returned = ["http://a", "http://b", "http://c"]
    seeds = ["http://a", "http://c", "http://z"]
    assert recall_at_k(returned, seeds, k=3) == 2 / 3


def test_recall_at_k_respects_k():
    returned = ["http://x", "http://y", "http://a"]
    assert recall_at_k(returned, ["http://a"], k=2) == 0.0  # 'a' is at index 2, beyond k=2


def test_recall_at_k_no_seeds_is_zero():
    assert recall_at_k(["http://a"], [], k=5) == 0.0


class _Tool(SearchTool):
    def __init__(self, name, passages):
        self.name = name
        self._p = passages

    def search(self, query, k=10):
        return SearchResult(passages=self._p[:k], latency_s=0.01)


def test_score_tool_aggregates():
    tool = _Tool("t", [Passage(source_id="s1", text="body", url="http://a")])
    queries = [{"query": "q", "seed_sources": ["http://a"], "domain": "technical"}]
    out = score_tool(tool, queries, relevance_fn=lambda q, p: 1.0, k=10)
    assert out["tool"] == "t"
    assert out["recall_at_k"] == 1.0
    assert out["mean_relevance"] == 1.0


def test_run_bakeoff_splits_by_domain():
    tool = _Tool("t", [Passage(source_id="s1", text="body", url="http://a")])
    queries = [
        {"query": "q1", "seed_sources": ["http://a"], "domain": "technical"},
        {"query": "q2", "seed_sources": [], "domain": "general"},
    ]
    res = run_bakeoff({"t": tool}, queries, relevance_fn=lambda q, p: 0.5, k=10)
    assert set(res["by_domain"]) == {"technical", "general"}
    assert res["overall"]["t"]["n"] == 2
