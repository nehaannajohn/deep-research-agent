"""URL fetch connector — retrieve a specific recommended page's RELEVANT content.

The adaptive "diversify sources" repair gets concrete URLs from the source
recommender (sources outside Exa's search results) and needs the content AT those
URLs. This is a fetch, not a search: no ranking, just "get that page." But a
recommended page (a data portal, a long report) can be huge, so the fetch is
**query-targeted** — Exa `/contents` with `highlights` keyed to the sub-question
returns only the verbatim excerpts relevant to it, not the whole page. Same
highlight mechanism as ExaSearch, pointed at a specific URL; it preserves the
verbatim-evidence invariant and keeps context small.

Fails soft: a dead/empty/garbled URL (Sonnet can hallucinate URLs) yields None, so
the loop simply gets no extra evidence from it rather than crashing.

The HTTP client is injectable (a `requests`-like object with `.post`) so unit tests
pass canned payloads; live calls happen only in manual/EC2 runs.
"""
from __future__ import annotations

from dra.schemas import Passage

URL = "https://api.exa.ai/contents"


class ExaContentsFetcher:
    name = "exa_contents"

    def __init__(self, api_key: str, client=None, max_chars: int = 1500,
                 highlights_per_url: int = 5):
        self.api_key = api_key
        self._client = client
        self.max_chars = max_chars
        self.highlights_per_url = highlights_per_url

    @property
    def client(self):
        if self._client is None:  # pragma: no cover - live path
            import requests

            self._client = requests
        return self._client

    def fetch(self, url: str, query: str) -> Passage | None:
        """Fetch `url` and return a Passage of the excerpts most relevant to
        `query` (verbatim highlights), or None if the page can't be retrieved or
        yields no usable text."""
        try:
            resp = self.client.post(
                URL,
                headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
                json={
                    "ids": [url],
                    "contents": {"highlights": {
                        "query": query,
                        "maxCharacters": self.max_chars,
                        "highlightsPerUrl": self.highlights_per_url,
                    }},
                },
            )
            results = resp.json().get("results") or []
        except Exception:
            return None
        if not results:
            return None
        r = results[0]
        highlights = [h.strip() for h in (r.get("highlights") or []) if h and h.strip()]
        text = "\n…\n".join(highlights) if highlights else (r.get("text") or "").strip()[:self.max_chars]
        if not text:
            return None
        return Passage(source_id=r.get("id") or url, text=text,
                       url=r.get("url") or url, title=r.get("title") or "", score=0.0)

    def fetch_many(self, urls: list[str], query: str) -> list[Passage]:
        """Fetch each URL (query-targeted); skip the ones that fail/empty."""
        out = []
        for u in urls:
            p = self.fetch(u, query)
            if p is not None:
                out.append(p)
        return out
