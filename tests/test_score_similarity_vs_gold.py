"""Unit tests for the similarity-to-gold re-score (pure helpers, fakes only)."""
from __future__ import annotations

from experiments.code.score_similarity_vs_gold import (
    aggregate,
    decompose_gold,
    gold_gradable,
    score_pair,
    type_of,
)

from dra.eval.pipeline.contracts import GradableClaim, GradableReport


def _our_report(*texts: str) -> GradableReport:
    return GradableReport(
        query="q",
        claims=[GradableClaim(id=f"c{i}", text=t) for i, t in enumerate(texts)],
    )


def test_type_of_parses_dra_bench_id():
    assert type_of("dra-type3-033") == "type3"
    assert type_of("dra-type1-000") == "type1"
    assert type_of("weird") == "unknown"


def test_decompose_gold_uses_injected_decomposer_and_drops_blanks():
    calls: list[str] = []

    def fake_decomposer(md: str) -> list[str]:
        calls.append(md)
        return ["claim one", "  ", "claim two"]

    out = decompose_gold("# Heading\nbody", fake_decomposer)
    assert out == ["claim one", "claim two"]  # blank dropped
    assert calls == ["# Heading\nbody"]


def test_decompose_gold_empty_input_skips_decomposer():
    def boom(_md: str) -> list[str]:  # must not be called
        raise AssertionError("decomposer called on empty input")

    assert decompose_gold("   ", boom) == []


def test_gold_gradable_wraps_texts_as_claims():
    g = gold_gradable("the query", ["a", "b"])
    assert g.query == "the query"
    assert [c.id for c in g.claims] == ["g0", "g1"]
    assert [c.text for c in g.claims] == ["a", "b"]


def test_score_pair_is_recall_of_gold_claims():
    # entail iff the gold claim text appears (substring) in some report claim.
    def entail(gold_text: str, our_texts: list[str]) -> bool:
        return any(gold_text in t for t in our_texts)

    ours = _our_report("rent control reduces supply", "prices rise downtown")
    gold = gold_gradable("q", ["rent control reduces supply", "vacancy rates climb"])

    res = score_pair(ours, gold, entail)
    assert res["covered"] == 1
    assert res["total_reference"] == 2
    assert res["similarity"] == 0.5
    assert res["missing"] == ["vacancy rates climb"]


def test_aggregate_means_overall_and_per_type():
    results = [
        {"id": "dra-type3-000", "type": "type3", "similarity": 1.0,
         "covered": 2, "total_reference": 2},
        {"id": "dra-type3-001", "type": "type3", "similarity": 0.0,
         "covered": 0, "total_reference": 3},
        {"id": "dra-type4-000", "type": "type4", "similarity": 0.5,
         "covered": 1, "total_reference": 2},
    ]
    agg = aggregate(results)
    assert agg["n"] == 3
    assert agg["n_scored"] == 3
    assert agg["similarity_mean"] == (1.0 + 0.0 + 0.5) / 3
    assert agg["covered_total"] == 3
    assert agg["reference_total"] == 7
    assert agg["per_type"]["type3"]["n"] == 2
    assert agg["per_type"]["type3"]["similarity_mean"] == 0.5
    assert agg["per_type"]["type4"]["similarity_mean"] == 0.5


def test_aggregate_excludes_items_with_no_gold_claims():
    results = [
        {"id": "dra-type1-000", "type": "type1", "similarity": None,
         "covered": 0, "total_reference": 0},
        {"id": "dra-type1-001", "type": "type1", "similarity": 0.8,
         "covered": 4, "total_reference": 5},
    ]
    agg = aggregate(results)
    assert agg["n"] == 2
    assert agg["n_scored"] == 1
    assert agg["n_no_gold"] == 1
    assert agg["similarity_mean"] == 0.8
