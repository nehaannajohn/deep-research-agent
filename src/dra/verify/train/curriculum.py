"""Evidence-ablated curriculum for monotonicity (design §1.4 step 3, §1.6).

For a SUPPORTED example with gold passages, emit:
  - full-gold      (all gold sentences concatenated)         -> supported
  - partial-gold   (a proper, non-empty subset of gold)      -> nei
  - distractor-only(sampled non-gold passages)               -> nei
The "none" rung (empty evidence) is represented by the distractor-only rung's
NEI signal plus the base NEI data; an empty-passage training row is skipped by
the tokenizer, so we use distractor-only as the concrete low rung. Together these
teach p_supported to rise only when sufficient gold evidence is present.
"""
from __future__ import annotations

import random
from typing import Optional

from dra.eval.base import EvalExample
from dra.verify.train.pairs import TrainPair


def ablation_ladder(
    ex: EvalExample,
    *,
    distractor_pool: list[str],
    rng: Optional[random.Random] = None,
) -> list[TrainPair]:
    """Build the {full-gold:supported, partial-gold:nei, distractor:nei} rungs."""
    if ex.gold_label != "supported":
        return []
    gold = [p.text for p in ex.passages if (p.text or "").strip()]
    if not gold:
        return []
    r = rng or random.Random(0)
    out: list[TrainPair] = []

    # full-gold -> supported
    out.append(TrainPair(claim=ex.claim, passage=" ".join(gold),
                         label="supported", source="curriculum"))

    # partial-gold -> nei (only when there is a proper non-empty subset)
    if len(gold) >= 2:
        k = r.randint(1, len(gold) - 1)
        subset = r.sample(gold, k)
        out.append(TrainPair(claim=ex.claim, passage=" ".join(subset),
                             label="nei", source="curriculum"))

    # distractor-only -> nei
    if distractor_pool:
        out.append(TrainPair(claim=ex.claim, passage=r.choice(distractor_pool),
                             label="nei", source="curriculum"))
    return out
