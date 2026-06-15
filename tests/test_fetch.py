"""Unit tests for the query-targeted URL fetch connector (canned Exa payloads)."""
from __future__ import annotations

from dra.search.fetch import ExaContentsFetcher


class _Client:
    """Fake requests-like client returning a canned /contents payload, and
    recording the last request body so we can assert the query was passed."""
    def __init__(self, payload=None, raise_exc=False):
        self.payload = payload or {}
        self.raise_exc = raise_exc
        self.last_json = None

    def post(self, url, headers=None, json=None):
        self.last_json = json
        if self.raise_exc:
            raise RuntimeError("network down")
        return _Resp(self.payload)


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def test_fetch_returns_query_relevant_highlights():
    payload = {"results": [{"id": "u1", "url": "https://who.int/data",
                            "title": "WHO Data", "highlights": ["mortality fell 3%", "in 2020"]}]}
    c = _Client(payload)
    f = ExaContentsFetcher("k", client=c)
    p = f.fetch("https://who.int/data", "global mortality 2020")
    assert p is not None
    assert "mortality fell 3%" in p.text and "in 2020" in p.text
    assert p.url == "https://who.int/data"
    # the sub-question is sent to Exa as the highlight query (relevance filter)
    assert c.last_json["contents"]["highlights"]["query"] == "global mortality 2020"
    assert c.last_json["ids"] == ["https://who.int/data"]


def test_fetch_falls_back_to_text_when_no_highlights():
    payload = {"results": [{"id": "u", "url": "https://x.org", "text": "  full body text  "}]}
    p = ExaContentsFetcher("k", client=_Client(payload)).fetch("https://x.org", "q")
    assert p.text == "full body text"


def test_fetch_none_on_empty_results_or_text():
    assert ExaContentsFetcher("k", client=_Client({"results": []})).fetch("https://x", "q") is None
    empty_text = {"results": [{"id": "u", "url": "https://x", "text": "   "}]}
    assert ExaContentsFetcher("k", client=_Client(empty_text)).fetch("https://x", "q") is None


def test_fetch_none_on_exception():
    assert ExaContentsFetcher("k", client=_Client(raise_exc=True)).fetch("https://x", "q") is None


def test_fetch_many_skips_failures():
    # first URL ok, second raises -> only the first comes back
    ok = {"results": [{"id": "u1", "url": "https://a", "highlights": ["good"]}]}

    class _Mixed:
        def __init__(self):
            self.n = 0

        def post(self, url, headers=None, json=None):
            self.n += 1
            if self.n == 1:
                return _Resp(ok)
            raise RuntimeError("boom")

    out = ExaContentsFetcher("k", client=_Mixed()).fetch_many(["https://a", "https://b"], "q")
    assert [p.url for p in out] == ["https://a"]
