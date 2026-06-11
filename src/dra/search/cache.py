"""Persistent, TTL'd retrieval cache that wraps any SearchTool.

Repeated identical retrievals (same backend, query, k, and result-affecting
params) reuse cached passages instead of re-hitting the API — cheaper and
reproducible across eval runs. Entries expire after `ttl_seconds` (default 3
days) so stale web content is re-fetched. The wrapped backend stays unaware.
See docs/superpowers/specs/2026-06-11-retrieval-cache-design.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid

from dra.search.base import SearchResult, SearchTool

THREE_DAYS_S = 3 * 24 * 60 * 60  # 259200


class CachingSearchTool(SearchTool):
    """Wraps a SearchTool with a TTL'd JSON cache.

    Writes are atomic (temp file + ``os.replace``) and safe under concurrent
    writers — each writer uses a unique temp path so they never collide.
    """

    def __init__(self, inner: SearchTool, cache_dir: str,
                 ttl_seconds: int = THREE_DAYS_S, clock=time.time):
        self.inner = inner
        self.name = inner.name
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.clock = clock

    def cache_key_params(self) -> dict[str, object]:
        return self.inner.cache_key_params()

    def _key(self, query: str, k: int) -> str:
        payload = {
            "name": self.inner.name,
            "query": query,
            "k": k,
            "params": self.inner.cache_key_params(),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _path(self, query: str, k: int) -> str:
        return os.path.join(self.cache_dir, f"{self._key(query, k)}.json")

    def search(self, query: str, k: int = 10) -> SearchResult:
        path = self._path(query, k)
        cached = self._read_fresh(path)
        if cached is not None:
            return cached
        result = self.inner.search(query, k)
        self._write(path, query, k, result)
        return result

    def _read_fresh(self, path: str) -> "SearchResult | None":
        try:
            with open(path, encoding="utf-8") as f:
                entry = json.load(f)
            if self.clock() - float(entry["fetched_at"]) > self.ttl_seconds:
                return None  # stale
            result = SearchResult(**entry["result"])
            result.cost_usd = 0.0  # served from cache -> no API spend
            return result
        # missing file / bad JSON / missing key -> miss. (pydantic v2 ValidationError
        # subclasses ValueError, so an invalid cached result is also treated as a miss.)
        except (OSError, ValueError, KeyError):
            return None

    def _write(self, path: str, query: str, k: int, result: SearchResult) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        entry = {
            "name": self.inner.name,
            "query": query,
            "k": k,
            "params": self.inner.cache_key_params(),
            "fetched_at": self.clock(),
            "result": result.model_dump(),
        }
        tmp = f"{path}.{uuid.uuid4().hex}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
        os.replace(tmp, path)  # atomic on POSIX
