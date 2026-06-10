"""Semantic Scholar academic-search adapter.

Assumed response shape (GET .../graph/v1/paper/search):
  {"data": [{"paperId","title","abstract","url","year","authors":[{"name"}]}]}
NOTE: returns abstracts (not full text) — adequate for the bake-off's document
selection; full-text fetch for evidence spans is a later concern.
"""
from __future__ import annotations

import time

from dra.schemas import Passage
from dra.search.base import SearchResult, SearchTool

URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,url,year,authors"


class SemanticScholarSearch(SearchTool):
    name = "semantic_scholar"

    def __init__(self, api_key: str = "", client=None):
        self.api_key = api_key  # optional; free without a key (rate-limited)
        self._client = client

    @property
    def client(self):
        if self._client is None:  # pragma: no cover - live path
            import requests

            self._client = requests
        return self._client

    def search(self, query: str, k: int = 10) -> SearchResult:
        t0 = time.monotonic()
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        resp = self.client.get(
            URL,
            params={"query": query, "limit": k, "fields": FIELDS},
            headers=headers,
        )
        data = resp.json()
        passages = [
            Passage(
                source_id=r.get("paperId", ""),
                text=(r.get("abstract") or "").strip(),
                url=r.get("url", ""),
                title=r.get("title") or "",
                score=0.0,  # API returns relevance order, not a score
            )
            for r in data.get("data", [])[:k]
        ]
        return SearchResult(passages=passages, latency_s=time.monotonic() - t0)
