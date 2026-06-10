from dra.schemas import Passage
from dra.search.base import SearchResult, SearchTool


class FakeTool(SearchTool):
    name = "fake"

    def __init__(self, passages):
        self._passages = passages

    def search(self, query, k=10):
        return SearchResult(passages=self._passages[:k])


def test_search_tool_returns_searchresult():
    tool = FakeTool([Passage(source_id="s1", text="t", url="u")])
    res = tool.search("q", k=5)
    assert isinstance(res, SearchResult)
    assert res.passages[0].source_id == "s1"


def test_k_limits_results():
    tool = FakeTool([Passage(source_id=f"s{i}", text="t") for i in range(10)])
    assert len(tool.search("q", k=3).passages) == 3


def test_default_search_tool_is_exa():
    from dra.config import Config
    from dra.search import default_search_tool

    cfg = Config(region="us-east-1", roles={}, panel_models=[], exa_key="k")
    assert default_search_tool(cfg).name == "exa"
