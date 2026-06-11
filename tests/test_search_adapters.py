"""Adapter unit tests — canned payloads via injected fake clients (no live calls)."""
from dra.search.exa import ExaSearch
from dra.search.semantic_scholar import SemanticScholarSearch
from dra.search.tavily import TavilySearch


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class FakePost:
    def __init__(self, payload):
        self.payload = payload
        self.last = None

    def post(self, url, headers=None, json=None):
        self.last = {"url": url, "headers": headers, "json": json}
        return FakeResp(self.payload)


class FakeGet:
    def __init__(self, payload):
        self.payload = payload
        self.last = None

    def get(self, url, params=None, headers=None):
        self.last = {"url": url, "params": params, "headers": headers}
        return FakeResp(self.payload)


def test_exa_maps_results_and_strips_text():
    http = FakePost({"results": [
        {"id": "e1", "url": "http://a", "title": "A", "score": 0.9, "text": "  body a  "},
        {"id": "e2", "url": "http://b", "title": "B", "score": 0.5, "text": "body b"},
    ]})
    res = ExaSearch(api_key="k", client=http).search("q", k=2)
    assert [p.source_id for p in res.passages] == ["e1", "e2"]
    assert res.passages[0].text == "body a"
    assert http.last["json"]["numResults"] == 2


def test_exa_uses_highlights_and_joins_excerpts():
    http = FakePost({"results": [
        {"id": "e1", "url": "http://a", "title": "A", "score": 0.9,
         "highlights": ["frag one", "frag two"]},
        {"id": "e2", "url": "http://b", "title": "B", "score": 0.5,
         "highlights": ["only frag"]},
    ]})
    res = ExaSearch(api_key="k", client=http, max_chars=500).search("scaling laws", k=2)
    assert "frag one" in res.passages[0].text and "frag two" in res.passages[0].text
    assert res.passages[1].text == "only frag"
    hl = http.last["json"]["contents"]["highlights"]
    assert hl["query"] == "scaling laws"
    assert hl["maxCharacters"] == 500


def test_tavily_prefers_raw_content():
    http = FakePost({"results": [
        {"url": "http://a", "title": "A", "score": 0.7, "content": "snippet", "raw_content": "full text"},
        {"url": "http://b", "title": "B", "score": 0.3, "content": "only snippet"},
    ]})
    res = TavilySearch(api_key="k", client=http).search("q", k=2)
    assert res.passages[0].text == "full text"
    assert res.passages[1].text == "only snippet"
    assert res.passages[0].source_id == "http://a"
    assert http.last["headers"]["Authorization"] == "Bearer k"  # modern bearer auth


def test_semantic_scholar_maps_abstract_and_sends_key():
    http = FakeGet({"data": [
        {"paperId": "p1", "title": "T1", "abstract": " abstract one ", "url": "http://s/p1", "year": 2023},
        {"paperId": "p2", "title": "T2", "abstract": None, "url": "http://s/p2"},
    ]})
    res = SemanticScholarSearch(api_key="kk", client=http).search("q", k=2)
    assert res.passages[0].source_id == "p1"
    assert res.passages[0].text == "abstract one"
    assert res.passages[1].text == ""  # missing abstract -> empty, not crash
    assert http.last["headers"]["x-api-key"] == "kk"
    assert http.last["params"]["limit"] == 2


def test_exa_cache_key_params_exposes_max_chars():
    assert ExaSearch(api_key="k", max_chars=2000).cache_key_params() == {"max_chars": 2000}


def test_searchtool_default_cache_key_params_is_empty():
    assert SemanticScholarSearch(api_key="k").cache_key_params() == {}
