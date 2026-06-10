"""Exa neural search adapter (web + papers).

Assumed response shape (POST https://api.exa.ai/search with contents.text):
  {"results": [{"id","url","title","score","text", ...}]}
The HTTP client is injectable (a `requests`-like object with `.post`) so unit
tests pass canned payloads; live calls happen only in the manual bake-off run.
"""
from __future__ import annotations

import time

from dra.schemas import Passage
from dra.search.base import SearchResult, SearchTool

URL = "https://api.exa.ai/search"


class ExaSearch(SearchTool):
    name = "exa"

    def __init__(self, api_key: str, client=None):
        self.api_key = api_key
        self._client = client

    @property
    def client(self):
        if self._client is None:  # pragma: no cover - live path
            import requests

            self._client = requests
        return self._client

    def search(self, query: str, k: int = 10) -> SearchResult:
        t0 = time.monotonic()
        resp = self.client.post(
            URL,
            headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
            json={"query": query, "numResults": k, "contents": {"text": True}},
        )
        data = resp.json()
        passages = [
            Passage(
                source_id=r.get("id") or r.get("url", ""),
                text=(r.get("text") or "").strip(),
                url=r.get("url", ""),
                title=r.get("title") or "",
                score=float(r.get("score") or 0.0),
            )
            for r in data.get("results", [])[:k]
        ]
        return SearchResult(passages=passages, latency_s=time.monotonic() - t0)
