"""Pipeline entry point.

Phase 0: a no-op skeleton that proves the end-to-end wiring and the report
contract. The real plan→route→search→synthesize→verify→adapt loop (built on
LangGraph) arrives in Phases 2-3.
"""
from __future__ import annotations

from dataclasses import dataclass

from dra.schemas import ResearchReport


@dataclass
class StubDeps:
    """Placeholder dependency bundle (search/synthesis/verifier injected later)."""


def run_query(query: str, deps=None) -> ResearchReport:
    return ResearchReport(query=query)
