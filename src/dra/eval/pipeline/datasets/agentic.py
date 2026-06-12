"""Agentic-tier loaders — FRAMES primary (spec §3, plan Phase 4, D3).

FRAMES (HF ``google/frames-benchmark``) is a multi-hop factual QA benchmark: each
row carries a question + a short gold answer, which is exactly the agentic-tier
shape (route to ``run_query`` → extract a short answer → EM/alias/judge vs gold).

`frames_row_to_item` is the **pure** mapper (fixture-tested): it is tolerant of
the documented FRAMES column names (``Prompt``/``Answer``) and common lowercase
variants (``question``/``answer``), and lifts an aliases column if present.
`load_frames` is the **live** loader (``# pragma: no cover``) — it streams the HF
dataset, samples ``n`` rows under ``seed``, and maps each via the pure mapper. It
is written resiliently so an unavailable HF id / shape never crashes import.

TODO (DEFERRED follow-up, plan Phase 4/stress): TruthfulQA (ships gold), the
conflict set, and the ALCE attribution loaders are a separate slice — not built
here.
"""
from __future__ import annotations

from typing import List

from dra.eval.pipeline.contracts import EvalItem

__all__ = ["frames_row_to_item", "load_frames"]

# Candidate column names in priority order (documented FRAMES first, then variants).
_QUESTION_KEYS = ("Prompt", "prompt", "Question", "question", "query")
_ANSWER_KEYS = ("Answer", "answer", "gold_answer", "Gold")
_ALIAS_KEYS = ("aliases", "Aliases", "answer_aliases", "alias")


def _first(row: dict, keys) -> "str | None":
    """Return the first present, non-empty value among `keys` (else None)."""
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def frames_row_to_item(row: dict, *, idx: int) -> EvalItem:
    """Map one FRAMES row to an agentic-tier `EvalItem` (pure).

    `idx` makes the id stable/unique (``frames-<idx:03d>``) since FRAMES rows do
    not all carry an explicit id. Aliases are lifted if the row exposes them.
    """
    question = _first(row, _QUESTION_KEYS) or ""
    answer = _first(row, _ANSWER_KEYS)
    aliases = _first(row, _ALIAS_KEYS) or []
    if isinstance(aliases, str):
        aliases = [aliases]

    return EvalItem(
        id=f"frames-{idx:03d}",
        tier="agentic",
        query=str(question),
        gold_answer=None if answer is None else str(answer),
        gold_answer_aliases=[str(a) for a in aliases],
        meta={"source": "frames"},
    )


def load_frames(n: int | None = None, *, seed: int = 13) -> List[EvalItem]:  # pragma: no cover - live HF download
    """Load + sample FRAMES from HuggingFace, mapped to `EvalItem`s (live).

    Resilient: if the documented HF id/split/shape is unavailable, this raises a
    clear error rather than corrupting the harness — the pure `frames_row_to_item`
    above is what the unit tests cover.
    """
    from datasets import load_dataset  # imported lazily; not a unit-test dep

    ds = load_dataset("google/frames-benchmark", split="test")
    if n is not None:
        ds = ds.shuffle(seed=seed).select(range(min(n, len(ds))))
    return [frames_row_to_item(dict(row), idx=i) for i, row in enumerate(ds)]
