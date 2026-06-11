"""Exa neural search adapter (web + papers).

Retrieves query-targeted verbatim *highlights* (the excerpts within each document
most relevant to the query), not full pages — this keeps evidence focused and
context small while preserving the verbatim-evidence invariant. `max_chars` caps
the highlight budget per source (Exa default is 4000; range 100–10000).

Assumed response shape (POST https://api.exa.ai/search with contents.highlights):
  {"results": [{"id","url","title","score","highlights":[...], "text"?, ...}]}
Falls back to `text` when a result has no `highlights` (e.g. canned bake-off
payloads). The HTTP client is injectable (a `requests`-like object with `.post`)
so unit tests pass canned payloads; live calls happen only in manual runs.
"""
from __future__ import annotations

import time

from dra.schemas import Passage
from dra.search.base import SearchResult, SearchTool

URL = "https://api.exa.ai/search"


class ExaSearch(SearchTool):
    name = "exa"

    def __init__(self, api_key: str, client=None, max_chars: int = 1000):
        self.api_key = api_key
        self._client = client
        self.max_chars = max_chars

    def cache_key_params(self) -> dict[str, object]:
        return {"max_chars": self.max_chars}

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
            json={
                "query": query,
                "numResults": k,
                "contents": {"highlights": {"query": query, "maxCharacters": self.max_chars}},
            },
        )
        data = resp.json()
        passages = []
        for r in data.get("results", [])[:k]:
            highlights = [h.strip() for h in (r.get("highlights") or []) if h and h.strip()]
            text = "\n…\n".join(highlights) if highlights else (r.get("text") or "").strip()
            passages.append(
                Passage(
                    source_id=r.get("id") or r.get("url", ""),
                    text=text,
                    url=r.get("url", ""),
                    title=r.get("title") or "",
                    score=float(r.get("score") or 0.0),
                )
            )
        return SearchResult(passages=passages, latency_s=time.monotonic() - t0)
