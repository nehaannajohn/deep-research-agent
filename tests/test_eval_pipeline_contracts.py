"""Phase 0 — Layer-2 pipeline-eval contracts + offline invariant.

Pure, no-network tests for the system-agnostic core (GradableReport /
GradableClaim / EvalItem) and the fixture loader, plus the one-directional
dependency guard: the live loop (`dra.loop`) MUST NOT pull in the offline
harness (`dra.eval.pipeline`).
"""
from __future__ import annotations

import subprocess
import sys

from dra.schemas import Citation, Passage

from dra.eval.pipeline.contracts import EvalItem, GradableClaim, GradableReport
from dra.eval.pipeline.datasets.base import FixtureLoader, Loader, load_fixture


def _passage() -> Passage:
    return Passage(source_id="s1", text="Paris is the capital of France.", url="http://x")


def _citation() -> Citation:
    return Citation(source_id="s1", span="capital of France")


def test_gradable_report_round_trips_real_schema_types():
    claim = GradableClaim(
        id="c1",
        text="Paris is the capital of France.",
        citations=[_citation()],
    )
    report = GradableReport(
        query="What is the capital of France?",
        narrative_markdown="# Answer\nParis.",
        claims=[claim],
        sources=[_passage()],
    )

    assert report.query == "What is the capital of France?"
    assert report.claims[0].text == "Paris is the capital of France."
    assert report.claims[0].citations[0].source_id == "s1"
    assert report.sources[0].source_id == "s1"
    # verdict / confidence default to None on an unverified/black-box claim.
    assert claim.verdict is None
    assert claim.confidence is None
    # collection defaults are independent, not shared.
    assert report.constraints == {}
    assert report.metadata == {}


def test_gradable_claim_accepts_verdict_label():
    claim = GradableClaim(
        id="c2", text="x", citations=[], verdict="supported", confidence=0.9
    )
    assert claim.verdict == "supported"
    assert claim.confidence == 0.9


def test_eval_item_defaults():
    item = EvalItem(id="i1", tier="agentic", query="Q?")
    assert item.tier == "agentic"
    assert item.constraints == {}
    assert item.gold_answer is None
    assert item.gold_answer_aliases == []
    assert item.reference_claims == []
    assert item.seed_sources == []
    assert item.expected_behavior is None
    assert item.label_corpus is None
    # defaults are not shared across instances.
    other = EvalItem(id="i2", tier="stress", query="Q2?")
    item.gold_answer_aliases.append("x")
    assert other.gold_answer_aliases == []


def test_eval_item_each_tier():
    for tier in ("agentic", "attribution", "stress", "dra_bench"):
        item = EvalItem(id=f"i-{tier}", tier=tier, query="Q?")
        assert item.tier == tier


def test_load_fixture_turns_dicts_into_eval_items():
    rows = [
        {"id": "a", "tier": "agentic", "query": "Q1", "gold_answer": "42"},
        {
            "id": "b",
            "tier": "dra_bench",
            "query": "Q2",
            "expected_behavior": "flag_contested",
            "constraints": {"format": "table"},
        },
    ]
    items = load_fixture(rows)
    assert [i.id for i in items] == ["a", "b"]
    assert all(isinstance(i, EvalItem) for i in items)
    assert items[0].gold_answer == "42"
    assert items[1].expected_behavior == "flag_contested"
    assert items[1].constraints == {"format": "table"}


def test_fixture_loader_is_a_loader():
    loader = FixtureLoader([{"id": "a", "tier": "agentic", "query": "Q1"}])
    assert isinstance(loader, Loader)
    assert loader.name
    items = loader.load()
    assert len(items) == 1
    assert items[0].id == "a"


def test_offline_invariant_loop_does_not_import_pipeline_harness():
    """The live loop must not pull in the offline eval harness.

    Run in a subprocess so this test's own imports (which include
    `dra.eval.pipeline`) cannot pollute the result.
    """
    code = (
        "import sys; import dra.loop; "
        "bad = [m for m in sys.modules if m.startswith('dra.eval.pipeline')]; "
        "print(bad); "
        "sys.exit(1 if bad else 0)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"dra.loop imported offline harness modules: {proc.stdout.strip()}\n"
        f"stderr: {proc.stderr.strip()}"
    )
