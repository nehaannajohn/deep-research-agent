"""Tavily agentic web-search adapter.

Assumed response shape (POST https://api.tavily.com/search):
  {"results": [{"title","url","content","score","raw_content"}]}
Prefer `raw_content` (full text) over `content` (snippet) when present.
"""
from __future__ import annotations

import time

from dra.schemas import Passage
from dra.search.base import SearchResult, SearchTool

URL = "https://api.tavily.com/search"


class TavilySearch(SearchTool):
    name = "tavily"

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
            json={
                "api_key": self.api_key,
                "query": query,
                "max_results": k,
                "include_raw_content": True,
            },
        )
        data = resp.json()
        passages = [
            Passage(
                source_id=r.get("url", ""),
                text=((r.get("raw_content") or r.get("content")) or "").strip(),
                url=r.get("url", ""),
                title=r.get("title") or "",
                score=float(r.get("score") or 0.0),
            )
            for r in data.get("results", [])[:k]
        ]
        return SearchResult(passages=passages, latency_s=time.monotonic() - t0)
