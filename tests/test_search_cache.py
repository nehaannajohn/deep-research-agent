"""CachingSearchTool unit tests — fake inner tool, no live calls."""
import json
import os

from dra.schemas import Passage
from dra.search.base import SearchResult, SearchTool
from dra.search.cache import CachingSearchTool


class FakeInner(SearchTool):
    name = "fake"

    def __init__(self, max_chars=2000):
        self.calls = 0
        self.max_chars = max_chars

    def cache_key_params(self) -> dict[str, object]:
        return {"max_chars": self.max_chars}

    def search(self, query: str, k: int = 10) -> SearchResult:
        self.calls += 1
        return SearchResult(
            passages=[Passage(source_id=f"s{self.calls}", text=f"text:{query}",
                              url="http://x", title="T", score=0.5)],
            latency_s=1.23,
            cost_usd=0.007,
        )


def test_miss_then_hit(tmp_path):
    inner = FakeInner()
    tool = CachingSearchTool(inner, cache_dir=str(tmp_path))
    r1 = tool.search("q", k=5)
    r2 = tool.search("q", k=5)
    assert inner.calls == 1  # second served from cache
    assert [p.source_id for p in r2.passages] == [p.source_id for p in r1.passages]
    assert r2.passages[0].text == r1.passages[0].text


def test_hit_zeros_cost_preserves_passages(tmp_path):
    inner = FakeInner()
    tool = CachingSearchTool(inner, cache_dir=str(tmp_path))
    first = tool.search("q", k=5)
    assert first.cost_usd == 0.007  # live result keeps real cost
    hit = tool.search("q", k=5)
    assert hit.cost_usd == 0.0  # cache hit = no spend
    assert hit.passages[0].url == first.passages[0].url
    assert hit.passages[0].score == first.passages[0].score


def test_key_sensitivity(tmp_path):
    inner = FakeInner()
    tool = CachingSearchTool(inner, cache_dir=str(tmp_path))
    tool.search("q", k=5)
    tool.search("q", k=8)      # different k -> miss
    tool.search("other", k=5)  # different query -> miss
    assert inner.calls == 3
    inner2 = FakeInner(max_chars=1000)
    tool2 = CachingSearchTool(inner2, cache_dir=str(tmp_path))
    tool2.search("q", k=5)     # different max_chars (via params) -> separate entry
    assert inner2.calls == 1


def test_name_and_params_delegate(tmp_path):
    inner = FakeInner(max_chars=1500)
    tool = CachingSearchTool(inner, cache_dir=str(tmp_path))
    assert tool.name == "fake"
    assert tool.cache_key_params() == {"max_chars": 1500}


def test_writes_valid_json_entry(tmp_path):
    inner = FakeInner()
    tool = CachingSearchTool(inner, cache_dir=str(tmp_path))
    tool.search("q", k=5)
    files = [f for f in os.listdir(tmp_path) if f.endswith(".json")]
    assert len(files) == 1
    entry = json.loads((tmp_path / files[0]).read_text())
    assert entry["query"] == "q" and entry["k"] == 5
    assert entry["params"] == {"max_chars": 2000}
    assert "fetched_at" in entry and "result" in entry


def test_ttl_expiry_refetches(tmp_path):
    inner = FakeInner()
    now = {"t": 1000.0}
    tool = CachingSearchTool(inner, cache_dir=str(tmp_path),
                             ttl_seconds=100, clock=lambda: now["t"])
    tool.search("q", k=5)
    now["t"] = 1050.0  # within ttl
    tool.search("q", k=5)
    assert inner.calls == 1  # still cached
    now["t"] = 1101.0  # past ttl
    tool.search("q", k=5)
    assert inner.calls == 2  # stale -> refetched


def test_corrupt_file_refetches(tmp_path):
    inner = FakeInner()
    tool = CachingSearchTool(inner, cache_dir=str(tmp_path))
    tool.search("q", k=5)  # writes a valid entry
    for fname in os.listdir(tmp_path):
        (tmp_path / fname).write_text("{not valid json")
    tool.search("q", k=5)
    assert inner.calls == 2  # corrupt -> treated as miss


def test_default_search_tool_wraps_when_enabled():
    from dra.config import load_config
    from dra.search import default_search_tool
    cfg = load_config(env={"EXA_API_KEY": "k"})
    tool = default_search_tool(cfg)
    assert isinstance(tool, CachingSearchTool)
    assert tool.name == "exa"
    assert tool.ttl_seconds == 259200


def test_default_search_tool_bare_when_disabled():
    from dra.config import load_config
    from dra.search import default_search_tool
    from dra.search.exa import ExaSearch
    cfg = load_config(env={"EXA_API_KEY": "k", "DRA_RETRIEVAL_CACHE": "0"})
    tool = default_search_tool(cfg)
    assert isinstance(tool, ExaSearch)
