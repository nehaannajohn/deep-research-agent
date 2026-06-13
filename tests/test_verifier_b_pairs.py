from __future__ import annotations

import random

from dra.eval.base import EvalExample
from dra.schemas import Passage
from dra.verify.train.pairs import TrainPair, example_to_pairs


def _ex(label, texts, eid="e0"):
    return EvalExample(
        example_id=eid, claim="C", gold_label=label,
        passages=[Passage(source_id=f"s{i}", text=t) for i, t in enumerate(texts)],
        meta={"dataset": "fever"},
    )


def test_supported_example_yields_one_pair_per_nonempty_passage():
    pairs = example_to_pairs(_ex("supported", ["p one", "  ", "p two"]))
    assert [p.label for p in pairs] == ["supported", "supported"]   # blank dropped
    assert [p.passage for p in pairs] == ["p one", "p two"]
    assert all(p.claim == "C" and p.source == "fever" for p in pairs)


def test_refuted_maps_through_unchanged():
    pairs = example_to_pairs(_ex("refuted", ["p"]))
    assert [p.label for p in pairs] == ["refuted"]


def test_insufficient_maps_to_nei():
    pairs = example_to_pairs(_ex("insufficient", ["non-entailing sentence"]))
    assert [p.label for p in pairs] == ["nei"]


def test_contested_folds_to_nei_for_the_head():
    pairs = example_to_pairs(_ex("contested", ["p"]))
    assert [p.label for p in pairs] == ["nei"]


def test_nei_with_no_passages_draws_from_negative_pool():
    pool = ["pool sentence A", "pool sentence B"]
    rng = random.Random(0)
    pairs = example_to_pairs(_ex("insufficient", []), neg_passage_pool=pool, rng=rng)
    assert len(pairs) == 1
    assert pairs[0].label == "nei"
    assert pairs[0].passage in pool


def test_nei_with_no_passages_and_no_pool_yields_nothing():
    assert example_to_pairs(_ex("insufficient", [])) == []
