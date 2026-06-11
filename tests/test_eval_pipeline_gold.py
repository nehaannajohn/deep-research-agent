"""Phase G — DRA-Bench gold synthesizer (pure assembly + parse, fakes only).

Covers `gold/synth_prompts.py` (type specs + pure `build_prompt_item`) and
`gold/fable_reference.py` (`FABLE_PROMPT` + pure `parse_reference`). The live
LLM calls (`synthesize_prompts`, `generate_reference`) are `# pragma: no cover`
and never exercised here — only the pure assembly path is asserted. No network.
"""
from __future__ import annotations

import pytest

from dra.eval.pipeline.contracts import EvalItem, GradableReport
from dra.eval.pipeline.gold.synth_prompts import (
    TYPE_SPECS,
    also_acceptable,
    build_prompt_item,
    expected_behavior_for,
    synthesize_prompts,
)
from dra.eval.pipeline.gold.fable_reference import (
    FABLE_PROMPT,
    parse_reference,
)


# --- type spec mappings --------------------------------------------------

def test_five_type_specs_present():
    keys = {s["key"] for s in TYPE_SPECS}
    assert keys == {"type1", "type2", "type3", "type4", "type5"}
    for spec in TYPE_SPECS:
        assert spec["label"]
        assert spec["description"]
        assert spec["expected_behavior"]


@pytest.mark.parametrize(
    "type_key,expected",
    [
        ("type1", "answer_confident"),
        ("type2", "answer_confident"),
        ("type3", "flag_contested"),
        ("type4", "report_insufficient"),
        ("type5", "answer_confident"),
    ],
)
def test_expected_behavior_for(type_key, expected):
    assert expected_behavior_for(type_key) == expected


@pytest.mark.parametrize(
    "type_key,expected",
    [
        ("type1", []),
        ("type2", []),
        ("type3", []),
        ("type4", ["ask_clarification"]),
        ("type5", []),
    ],
)
def test_also_acceptable(type_key, expected):
    assert also_acceptable(type_key) == expected


# --- build_prompt_item (pure) -------------------------------------------

def test_build_prompt_item_basic_fields():
    item = build_prompt_item("type1", "What is attention in transformers?", 7)
    assert isinstance(item, EvalItem)
    assert item.id == "dra-type1-007"
    assert item.tier == "dra_bench"
    assert item.query == "What is attention in transformers?"
    assert item.expected_behavior == "answer_confident"
    assert item.meta["type"] == "type1"
    assert item.meta["also_acceptable"] == []
    assert item.constraints == {}


def test_build_prompt_item_type5_carries_visual_constraint():
    item = build_prompt_item("type5", "Compare X and Y in a table.", 0)
    assert item.id == "dra-type5-000"
    assert item.constraints == {"wants_visual": True}
    assert item.expected_behavior == "answer_confident"
    assert item.meta["type"] == "type5"


def test_build_prompt_item_type3_flags_contested():
    item = build_prompt_item("type3", "Is X better than Y? Both sides.", 12)
    assert item.expected_behavior == "flag_contested"
    assert item.meta["also_acceptable"] == []


def test_build_prompt_item_type4_records_clarification_alternative():
    item = build_prompt_item("type4", "Ambiguous unanswerable prompt", 3)
    assert item.id == "dra-type4-003"
    assert item.expected_behavior == "report_insufficient"
    assert item.meta["also_acceptable"] == ["ask_clarification"]


# --- parse_reference (pure, fake decomposer) ----------------------------

def _fake_decomposer(markdown: str) -> list:
    assert markdown  # the markdown is what gets decomposed
    return [
        "Transformers use self-attention.",
        "BERT is bidirectional.",
        "GPT is autoregressive.",
    ]


def test_parse_reference_builds_gradable_report():
    md = "# Report\n\nTransformers use self-attention. BERT is bidirectional."
    report = parse_reference("What is a transformer?", md, _fake_decomposer)

    assert isinstance(report, GradableReport)
    assert report.query == "What is a transformer?"
    assert report.narrative_markdown == md
    assert report.metadata == {"source": "fable_reference"}
    assert report.sources == []

    assert [c.text for c in report.claims] == [
        "Transformers use self-attention.",
        "BERT is bidirectional.",
        "GPT is autoregressive.",
    ]
    assert [c.id for c in report.claims] == ["fable-000", "fable-001", "fable-002"]
    for c in report.claims:
        assert c.verdict is None
        assert c.citations == []


def test_fable_prompt_is_minimal_and_includes_query():
    prompt = FABLE_PROMPT("How do diffusion models work?")
    assert "How do diffusion models work?" in prompt
    assert "Markdown" in prompt or "markdown" in prompt


# --- synthesize_prompts smoke (fake llm; pure assembly asserted) --------

def test_synthesize_prompts_smoke_with_fake_llm():
    class _FakeLLM:
        def complete(self, prompt: str) -> str:
            # one query per line; assembly is what we assert
            return "Query A\nQuery B"

    items = synthesize_prompts(_FakeLLM(), per_type=2)
    assert len(items) == 10  # 5 types x 2
    assert all(isinstance(it, EvalItem) for it in items)
    assert all(it.tier == "dra_bench" for it in items)
    # type5 visual constraint preserved through synthesis
    type5 = [it for it in items if it.meta["type"] == "type5"]
    assert type5 and all(it.constraints == {"wants_visual": True} for it in type5)
