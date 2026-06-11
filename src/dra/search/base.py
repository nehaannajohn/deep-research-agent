"""The `search()` tool contract.

Retrieval is a *delegated* capability: every backend (Exa, Tavily, Semantic
Scholar, …) implements this one interface, so the rest of the system depends on
the contract, not the vendor. We own how we *call* search; the tool owns ranking.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from dra.schemas import Passage


class SearchResult(BaseModel):
    passages: list[Passage] = Field(default_factory=list)
    latency_s: float = 0.0
    cost_usd: float = 0.0


class SearchTool(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, k: int = 10) -> SearchResult:
        """Return up to `k` ranked passages with provenance for `query`."""
        raise NotImplementedError

    def cache_key_params(self) -> dict[str, object]:
        """Result-affecting params beyond (query, k) that must enter a cache key.
        Default: none. Backends override when an instance setting changes results."""
        return {}
