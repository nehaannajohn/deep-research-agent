"""DRA-Bench loader — JSONL of serialized `EvalItem`s back into `EvalItem`s.

The DRA-Bench prompts are synthesized + user-reviewed (see
`gold/synth_prompts.py`) and persisted as one JSON object per line. Each line is
a serialized `EvalItem` (``id, tier, query, constraints, expected_behavior,
meta`` and any other EvalItem fields). This loader is a pure parse — it never
calls a model — so it is fixture-tested on a tiny inline JSONL, not the real
gitignored ``eval/`` file.
"""
from __future__ import annotations

import json
from typing import List

from dra.eval.pipeline.contracts import EvalItem

__all__ = ["load_dra_bench"]


def load_dra_bench(path: str = "eval/dra_bench/prompts.jsonl") -> List[EvalItem]:
    """Parse the DRA-Bench JSONL at `path` into validated `EvalItem`s.

    Each non-blank line is a serialized `EvalItem`; order is preserved. Blank /
    whitespace-only lines are skipped. Pydantic validation raises on a malformed
    row, surfacing a bad prompt file early rather than silently dropping it.
    """
    items: List[EvalItem] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            items.append(EvalItem(**json.loads(line)))
    return items
