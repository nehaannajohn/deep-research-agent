"""Convert an `EvalExample` (claim + N passages + 4-way label) into the
cross-encoder's `(claim, single-passage, 3-way label)` training pairs.

One pair per (claim, gold passage): the cross-encoder scores ONE passage at a
time (the multi-passage max-aggregation lives at inference, `cross_encoder.py`).
NEI examples that carry no passage draw a non-entailing passage from a pool so
the model still sees a (claim, irrelevant-evidence) -> nei signal.
"""
from __future__ import annotations

import random
from typing import Optional

from pydantic import BaseModel

from dra.eval.base import EvalExample
from dra.verify.train import TO3


class TrainPair(BaseModel):
    claim: str
    passage: str
    label: str          # one of LABEL3
    source: str = ""    # provenance tag (dataset / "synthetic" / "curriculum")


def example_to_pairs(
    ex: EvalExample,
    *,
    neg_passage_pool: Optional[list[str]] = None,
    rng: Optional[random.Random] = None,
) -> list[TrainPair]:
    """`EvalExample` -> list of single-passage `TrainPair`s (3-way label)."""
    label = TO3.get(ex.gold_label, "nei")
    src = str(ex.meta.get("dataset", ""))
    texts = [p.text for p in ex.passages if (p.text or "").strip()]

    if texts:
        return [TrainPair(claim=ex.claim, passage=t, label=label, source=src) for t in texts]

    # No passage on the example. Only NEI is recoverable (attach an irrelevant
    # passage); supported/refuted with no evidence is unusable -> drop.
    if label == "nei" and neg_passage_pool:
        r = rng or random.Random(0)
        return [TrainPair(claim=ex.claim, passage=r.choice(neg_passage_pool),
                          label="nei", source=src)]
    return []
