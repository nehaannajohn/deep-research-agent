from __future__ import annotations

import random

from dra.eval.base import EvalExample
from dra.schemas import Passage
from dra.verify.train.curriculum import ablation_ladder


def _supported(texts):
    return EvalExample(
        example_id="e", claim="C", gold_label="supported",
        passages=[Passage(source_id=f"s{i}", text=t) for i, t in enumerate(texts)],
        meta={"dataset": "fever"},
    )


def test_full_gold_is_supported_ablated_rungs_are_nei():
    distractors = ["unrelated 1", "unrelated 2"]
    rng = random.Random(0)
    pairs = ablation_ladder(_supported(["g1", "g2"]), distractor_pool=distractors, rng=rng)
    assert any(p.label == "supported" for p in pairs)
    assert any(p.label == "nei" for p in pairs)
    sup = [p.passage for p in pairs if p.label == "supported"][0]
    assert "g1" in sup and "g2" in sup
    assert all(p.source == "curriculum" for p in pairs)


def test_non_supported_examples_are_skipped():
    ex = EvalExample(example_id="e", claim="C", gold_label="refuted",
                     passages=[Passage(source_id="s", text="p")], meta={})
    assert ablation_ladder(ex, distractor_pool=["d"], rng=random.Random(0)) == []


def test_single_gold_passage_skips_partial_rung():
    pairs = ablation_ladder(_supported(["only"]), distractor_pool=["d1"], rng=random.Random(0))
    labels = sorted({p.label for p in pairs})
    assert labels == ["nei", "supported"]
