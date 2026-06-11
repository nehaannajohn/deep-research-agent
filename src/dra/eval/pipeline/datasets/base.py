"""Loader ABC + a trivial fixture loader (proves the EvalItem contract round-trips).

Tier-specific loaders (FRAMES/ALCE/TruthfulQA/DRA-Bench) subclass `Loader` in
later phases. `load_fixture` / `FixtureLoader` turn plain dicts into `EvalItem`s
with no network — the fake-tested seam the rest of the harness builds on.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from dra.eval.pipeline.contracts import EvalItem


def load_fixture(items: list[dict]) -> list[EvalItem]:
    """Turn a list of plain dicts into validated `EvalItem`s, order preserved."""
    return [EvalItem(**row) for row in items]


class Loader(ABC):
    """Abstract benchmark loader. Subclasses set `name` and implement `load`."""

    name: str = ""

    @abstractmethod
    def load(self, *args, **kwargs) -> list[EvalItem]:
        """Return this dataset's items as `EvalItem`s."""
        raise NotImplementedError


class FixtureLoader(Loader):
    """A `Loader` over an in-memory list of dict rows — for tests and smoke runs."""

    name = "fixture"

    def __init__(self, rows: list[dict], name: str | None = None):
        self._rows = rows
        if name is not None:
            self.name = name

    def load(self, *args, **kwargs) -> list[EvalItem]:
        return load_fixture(self._rows)
