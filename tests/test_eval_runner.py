"""Runner + prediction-caching tests: fakes only, no Bedrock/network."""
from __future__ import annotations

import json

from dra.eval.base import EvalExample
from dra.eval.runner import cost_summary, run_predictions
from dra.verify.base import VerifierResult


class FakeVerifier:
    """Counts verify() calls; returns a deterministic VerifierResult keyed on the claim.

    Optionally raises on a specific claim (to exercise skip-on-exception) and/or
    exposes a `model_calls` attribute (to exercise defensive capture).
    """

    def __init__(self, *, raise_on=None, model_calls=None, label="supported",
                 confidence=0.8, recommendation="accept", votes=None):
        self.calls = 0
        self._raise_on = raise_on
        self.model_calls = model_calls  # may be None -> not exposed meaningfully
        self._label = label
        self._confidence = confidence
        self._recommendation = recommendation
        self._votes = votes or {"a": 2, "b": 1}

    def verify(self, claim, passages):
        self.calls += 1
        if self._raise_on is not None and claim == self._raise_on:
            raise RuntimeError("boom")
        return VerifierResult(
            label=self._label,
            confidence=self._confidence,
            reasoning="because",
            recommendation=self._recommendation,
            votes=dict(self._votes),
        )


def _examples(n=3):
    return [
        EvalExample(example_id=f"ex{i}", claim=f"claim {i}", passages=[],
                    gold_label="supported")
        for i in range(n)
    ]


_KEY = dict(verifier_id="A", dataset="fever", split="test",
            dataset_revision="rev1", sample_seed=13)


def test_cache_miss_then_hit_then_refresh(tmp_path):
    v = FakeVerifier()
    exs = _examples(3)

    # Miss: invokes the verifier once per example, writes a file.
    rows1 = run_predictions(v, exs, cache_dir=str(tmp_path), **_KEY)
    assert len(rows1) == 3
    assert v.calls == 3
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1

    # Hit: same key -> returns identical rows WITHOUT touching the verifier.
    rows2 = run_predictions(v, exs, cache_dir=str(tmp_path), **_KEY)
    assert v.calls == 3  # unchanged
    assert rows2 == rows1

    # Refresh: forces recompute -> verifier called again. Rows match on every
    # stable field (latency_ms is wall time and legitimately varies per run).
    rows3 = run_predictions(v, exs, cache_dir=str(tmp_path), refresh=True, **_KEY)
    assert v.calls == 6
    stable = lambda rs: [{k: v for k, v in r.items() if k != "latency_ms"} for r in rs]
    assert stable(rows3) == stable(rows1)


def test_cache_file_is_valid_jsonl(tmp_path):
    v = FakeVerifier()
    run_predictions(v, _examples(2), cache_dir=str(tmp_path), **_KEY)
    path = next(tmp_path.glob("*.jsonl"))
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # each line is a standalone JSON object


def test_skip_on_exception(tmp_path):
    exs = _examples(3)
    v = FakeVerifier(raise_on="claim 1")  # middle example blows up
    rows = run_predictions(v, exs, cache_dir=str(tmp_path), **_KEY)
    assert v.calls == 3  # all attempted
    ids = [r["example_id"] for r in rows]
    assert ids == ["ex0", "ex2"]  # ex1 skipped, run did not crash


def test_row_shape_sourced_from_result(tmp_path):
    v = FakeVerifier(model_calls=4, label="refuted", confidence=0.55,
                     recommendation="revise", votes={"x": 3})
    ex = EvalExample(example_id="ex0", claim="c", passages=[],
                     gold_label="insufficient")
    rows = run_predictions(v, [ex], cache_dir=str(tmp_path), **_KEY)
    row = rows[0]
    assert set(row) >= {
        "example_id", "gold", "pred", "confidence", "recommendation",
        "votes", "latency_ms", "model_calls",
    }
    assert row["example_id"] == "ex0"
    assert row["gold"] == "insufficient"
    assert row["pred"] == "refuted"
    assert row["confidence"] == 0.55
    assert row["recommendation"] == "revise"
    assert row["votes"] == {"x": 3}
    assert row["model_calls"] == 4
    assert isinstance(row["latency_ms"], float) and row["latency_ms"] >= 0.0


def test_model_calls_none_when_unavailable(tmp_path):
    v = FakeVerifier(model_calls=None)
    rows = run_predictions(v, _examples(1), cache_dir=str(tmp_path), **_KEY)
    assert rows[0]["model_calls"] is None


def test_cost_summary_closed_form():
    rows = [
        {"example_id": "a", "model_calls": 3, "latency_ms": 100.0},
        {"example_id": "b", "model_calls": 1, "latency_ms": 300.0},
    ]
    price_table = {"A": 0.5}  # $/call
    out = cost_summary(rows, price_table, verifier_id="A")
    # cost = (3 + 1) calls * 0.5 = 2.0 ; mean per claim = 1.0
    assert out["total_cost"] == 2.0
    assert out["mean_cost"] == 1.0
    assert out["total_model_calls"] == 4
    # latency: total 400, mean 200
    assert out["total_latency_ms"] == 400.0
    assert out["mean_latency_ms"] == 200.0
    assert out["n"] == 2


def test_parallel_matches_sequential_and_preserves_order(tmp_path):
    exs = _examples(12)
    seq = run_predictions(FakeVerifier(), exs, cache_dir=str(tmp_path / "seq"),
                          max_workers=1, **_KEY)
    par = run_predictions(FakeVerifier(), exs, cache_dir=str(tmp_path / "par"),
                          max_workers=4, **_KEY)
    # Order is preserved (input order) under concurrency, for cache determinism.
    assert [r["example_id"] for r in par] == [f"ex{i}" for i in range(12)]
    # Identical on every stable field (latency_ms is wall time and varies).
    stable = lambda rs: [{k: v for k, v in r.items() if k != "latency_ms"} for r in rs]
    assert stable(par) == stable(seq)


def test_parallel_skip_on_exception_preserves_remaining(tmp_path):
    v = FakeVerifier(raise_on="claim 3")
    rows = run_predictions(v, _examples(6), cache_dir=str(tmp_path),
                           max_workers=4, **_KEY)
    # ex3 skipped; the rest survive in input order despite concurrency.
    assert [r["example_id"] for r in rows] == ["ex0", "ex1", "ex2", "ex4", "ex5"]


def test_cost_summary_handles_missing_model_calls():
    rows = [
        {"example_id": "a", "model_calls": None, "latency_ms": 50.0},
        {"example_id": "b", "model_calls": 2, "latency_ms": 50.0},
    ]
    out = cost_summary(rows, {"A": 1.0}, verifier_id="A")
    # None model_calls contributes 0 cost / 0 calls but still counts as a claim.
    assert out["total_model_calls"] == 2
    assert out["total_cost"] == 2.0
    assert out["mean_cost"] == 1.0  # 2.0 / 2 claims
    assert out["n"] == 2
