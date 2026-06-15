"""Unit tests for the Sonnet-reference scoring driver (pure helpers, fakes)."""
from __future__ import annotations

from experiments.code.score_reference import (
    aggregate,
    build_gradable,
    score_reference_item,
    type_of,
)


class FakePanel:
    """Returns a fixed aggregate score; records the prompts it saw."""

    def __init__(self, score: float):
        self._score = score
        self.prompts: list[str] = []

    def score(self, prompt: str, *, seed: int) -> dict:
        self.prompts.append(prompt)
        return {"aggregate": self._score, "per_judge": [self._score]}


def test_type_of():
    assert type_of("dra-type3-033") == "type3"
    assert type_of("nope") == "unknown"


def test_build_gradable_carries_narrative_and_constraints():
    g = build_gradable("q", "# Report\nbody", {"wants_visual": True})
    assert g.query == "q"
    assert g.narrative_markdown == "# Report\nbody"
    assert g.constraints == {"wants_visual": True}
    assert g.claims == []  # claims irrelevant to relevance/quality/formatting


def test_score_reference_item_runs_three_axes():
    panel = FakePanel(4.0)
    # a table satisfies a format=table constraint deterministically
    md = "intro\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    res = score_reference_item("q", md, {"format": "table"}, panel, seed=13)
    assert res["relevance"]["aggregate"] == 4.0
    assert res["quality"]["aggregate"] == 4.0
    assert res["formatting"]["pass_rate"] == 1.0  # table present
    assert len(panel.prompts) == 2  # relevance + quality (formatting is rule-based)


def test_aggregate_overall_and_per_type():
    results = [
        {"id": "dra-type1-000", "type": "type1",
         "relevance": {"aggregate": 5.0}, "quality": {"aggregate": 4.0},
         "formatting": {"pass_rate": None}},
        {"id": "dra-type1-001", "type": "type1",
         "relevance": {"aggregate": 3.0}, "quality": {"aggregate": 4.0},
         "formatting": {"pass_rate": 1.0}},
        {"id": "dra-type5-000", "type": "type5",
         "relevance": {"aggregate": 4.0}, "quality": {"aggregate": 2.0},
         "formatting": {"pass_rate": 0.0}},
    ]
    agg = aggregate(results)
    assert agg["n"] == 3
    assert agg["relevance_mean"] == (5.0 + 3.0 + 4.0) / 3
    assert agg["quality_mean"] == (4.0 + 4.0 + 2.0) / 3
    # formatting mean excludes the None
    assert agg["formatting_pass_rate"] == (1.0 + 0.0) / 2
    assert agg["per_type"]["type1"]["n"] == 2
    assert agg["per_type"]["type1"]["relevance_mean"] == 4.0
    assert agg["per_type"]["type5"]["quality_mean"] == 2.0
