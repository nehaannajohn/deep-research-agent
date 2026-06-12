"""Phase 4 — live orchestrator + benchmark loaders (pure logic, fakes only).

Covers:
- `datasets/dra_bench.load_dra_bench` (inline JSONL fixture → EvalItems)
- `datasets/agentic.frames_row_to_item` (FRAMES row → EvalItem with gold)
- `harness.evaluate_item` / `harness.run_eval` end-to-end with injected fakes.

No network: `run_query`, the grounding judge, the panel, and the extractor are
all fakes. A canned `ResearchReport` flows through the real adapter + scorers.
"""
from __future__ import annotations

import json

import pytest

from dra.eval.pipeline.contracts import EvalItem
from dra.eval.pipeline.datasets.dra_bench import load_dra_bench
from dra.eval.pipeline.datasets.agentic import frames_row_to_item
from dra.eval.pipeline.harness import PipelineDeps, evaluate_item, run_eval

from dra.schemas import (
    Citation,
    Claim,
    Passage,
    ReportMetadata,
    ResearchReport,
)


# --------------------------------------------------------------------------- #
# DRA-Bench loader (inline JSONL fixture)
# --------------------------------------------------------------------------- #
def _dra_bench_jsonl() -> str:
    rows = [
        {
            "id": "dra-type1-000",
            "tier": "dra_bench",
            "query": "How does attention work?",
            "constraints": {},
            "expected_behavior": "answer_confident",
            "meta": {"type": "type1", "also_acceptable": []},
        },
        {
            "id": "dra-type3-000",
            "tier": "dra_bench",
            "query": "Is X better than Y?",
            "constraints": {},
            "expected_behavior": "flag_contested",
            "meta": {"type": "type3", "also_acceptable": []},
        },
        {
            "id": "dra-type4-000",
            "tier": "dra_bench",
            "query": "What is the airspeed of an unladen swallow?",
            "constraints": {},
            "expected_behavior": "report_insufficient",
            "meta": {"type": "type4", "also_acceptable": ["ask_clarification"]},
        },
        {
            "id": "dra-type5-000",
            "tier": "dra_bench",
            "query": "Map the NLP landscape.",
            "constraints": {"wants_visual": True},
            "expected_behavior": "answer_confident",
            "meta": {"type": "type5", "also_acceptable": []},
        },
    ]
    return "\n".join(json.dumps(r) for r in rows) + "\n"


def test_load_dra_bench_parses_jsonl(tmp_path):
    path = tmp_path / "prompts.jsonl"
    path.write_text(_dra_bench_jsonl(), encoding="utf-8")

    items = load_dra_bench(str(path))

    assert len(items) == 4
    assert all(isinstance(it, EvalItem) for it in items)
    assert [it.id for it in items] == [
        "dra-type1-000",
        "dra-type3-000",
        "dra-type4-000",
        "dra-type5-000",
    ]
    assert all(it.tier == "dra_bench" for it in items)
    # constraints + meta preserved
    type5 = items[3]
    assert type5.constraints == {"wants_visual": True}
    assert type5.meta["type"] == "type5"
    type4 = items[2]
    assert type4.expected_behavior == "report_insufficient"
    assert type4.meta["also_acceptable"] == ["ask_clarification"]


def test_load_dra_bench_skips_blank_lines(tmp_path):
    raw = _dra_bench_jsonl() + "\n   \n"
    path = tmp_path / "prompts.jsonl"
    path.write_text(raw, encoding="utf-8")
    items = load_dra_bench(str(path))
    assert len(items) == 4


# --------------------------------------------------------------------------- #
# FRAMES loader (pure row mapper)
# --------------------------------------------------------------------------- #
def test_frames_row_to_item_maps_gold_answer():
    row = {
        "Prompt": "What year did the Eiffel Tower open?",
        "Answer": "1889",
    }
    item = frames_row_to_item(row, idx=7)
    assert isinstance(item, EvalItem)
    assert item.tier == "agentic"
    assert item.query == "What year did the Eiffel Tower open?"
    assert item.gold_answer == "1889"
    assert item.id == "frames-007"


def test_frames_row_to_item_alternate_keys_and_aliases():
    # tolerant to lowercase keys + an aliases column.
    row = {
        "question": "Who wrote Hamlet?",
        "answer": "William Shakespeare",
        "aliases": ["Shakespeare"],
    }
    item = frames_row_to_item(row, idx=0)
    assert item.query == "Who wrote Hamlet?"
    assert item.gold_answer == "William Shakespeare"
    assert "Shakespeare" in item.gold_answer_aliases


# --------------------------------------------------------------------------- #
# Orchestrator end-to-end with fakes
# --------------------------------------------------------------------------- #
def _canned_report(query: str) -> ResearchReport:
    return ResearchReport(
        query=query,
        report_markdown="Paris is the capital of France. It is on the Seine.",
        claims=[
            Claim(
                id="c0",
                text="Paris is the capital of France.",
                section="intro",
                citations=[Citation(source_id="s1", span="Paris is the capital.")],
                verdict="supported",
                confidence=0.9,
            ),
            Claim(
                id="c1",
                text="It is on the Seine.",
                section="body",
                citations=[Citation(source_id="s2", span="on the Seine.")],
                verdict="supported",
                confidence=0.8,
            ),
        ],
        sources=[
            Passage(source_id="s1", text="Paris is the capital of France.", url="http://a"),
            Passage(source_id="s2", text="The city lies on the Seine.", url="http://b"),
        ],
        metadata=ReportMetadata(
            overall_confidence=0.85,
            coverage=0.9,
            descriptive_summary="Paris",
        ),
    )


class FakeRunQuery:
    def __init__(self, report_factory=_canned_report, raise_on=None):
        self._factory = report_factory
        self._raise_on = raise_on or set()

    def __call__(self, query: str) -> ResearchReport:
        if query in self._raise_on:
            raise RuntimeError(f"boom for {query!r}")
        return self._factory(query)


class FakeGroundingJudge:
    """Always returns 'supported' so grounding_rate is deterministic."""

    def verdict(self, claim_text, passages):
        return "supported"


class FakePanel:
    """Returns a fixed aggregate dict shaped like JudgePanel.score()."""

    def __init__(self, aggregate=4):
        self._aggregate = aggregate

    def score(self, rubric_prompt, *, seed, candidates=None):
        return {
            "aggregate": self._aggregate,
            "mean": float(self._aggregate),
            "majority": self._aggregate,
            "per_judge": [self._aggregate],
            "adjudicated": False,
        }


class FakeExtractor:
    def __init__(self, answer="Paris"):
        self._answer = answer

    def complete(self, prompt):
        return self._answer


def _agentic_item(item_id="frames-000", query="What is the capital of France?"):
    return EvalItem(
        id=item_id,
        tier="agentic",
        query=query,
        gold_answer="Paris",
    )


def _make_deps(raise_on=None):
    return PipelineDeps(
        run_query=FakeRunQuery(raise_on=raise_on),
        grounding_judge=FakeGroundingJudge(),
        panel=FakePanel(),
        extractor=FakeExtractor(),
    )


def test_evaluate_item_scores_all_axes():
    item = _agentic_item()
    deps = _make_deps()
    result = evaluate_item(item, deps, seed=13)

    assert result["id"] == "frames-000"
    assert result["tier"] == "agentic"
    # grounding axis
    assert result["grounding"]["grounding_rate"] == pytest.approx(1.0)
    assert result["grounding"]["hallucination_rate"] == pytest.approx(0.0)
    # relevance + quality from the fake panel
    assert result["relevance"]["aggregate"] == 4
    assert result["quality"]["aggregate"] == 4
    # task accuracy: gold "Paris" matched (rule fast-path via descriptive_summary)
    assert result["task_accuracy"]["correct"] is True
    assert result["extracted_answer"] == "Paris"


def test_evaluate_item_no_gold_skips_task_accuracy():
    item = EvalItem(id="x1", tier="stress", query="Ambiguous?")
    deps = _make_deps()
    result = evaluate_item(item, deps, seed=13)
    assert result["task_accuracy"] is None
    assert result["extracted_answer"] is None


def test_evaluate_item_formatting_constraint():
    item = EvalItem(
        id="t5",
        tier="dra_bench",
        query="Map it.",
        constraints={"wants_visual": True},
    )
    deps = _make_deps()
    result = evaluate_item(item, deps, seed=13)
    # canned report has no mermaid block -> formatting fails
    assert result["formatting"]["pass_rate"] == pytest.approx(0.0)


def test_run_eval_aggregates_and_writes(tmp_path):
    items = [
        _agentic_item("frames-000", "What is the capital of France?"),
        _agentic_item("frames-001", "Capital of France again?"),
    ]
    deps = _make_deps()
    summary = run_eval(items, deps, out_dir=str(tmp_path), seed=13)

    # files written
    assert (tmp_path / "per_item.json").exists()
    assert (tmp_path / "summary.json").exists()

    per_item = json.loads((tmp_path / "per_item.json").read_text())
    assert len(per_item) == 2

    # summary has overall + per-tier sections with the expected axis keys
    assert "overall" in summary
    assert "per_tier" in summary
    overall = summary["overall"]
    assert overall["n"] == 2
    assert "grounding_rate" in overall
    assert "hallucination_rate" in overall
    assert "relevance_mean" in overall
    assert "quality_mean" in overall
    assert "task_accuracy" in overall
    assert "abstention_rate" in overall
    assert "agentic" in summary["per_tier"]


def test_run_eval_skips_raising_item_not_fatal(tmp_path):
    items = [
        _agentic_item("frames-000", "good-query"),
        _agentic_item("frames-bad", "bad-query"),
        _agentic_item("frames-002", "another-good"),
    ]
    deps = _make_deps(raise_on={"bad-query"})
    summary = run_eval(items, deps, out_dir=str(tmp_path), seed=13)

    per_item = json.loads((tmp_path / "per_item.json").read_text())
    ids = {r["id"] for r in per_item}
    assert ids == {"frames-000", "frames-002"}  # raising item skipped
    assert summary["overall"]["n"] == 2
