"""Tests for the text-level Expected-Behavior-Match (EBM) judge (fakes only)."""
from __future__ import annotations

from dra.eval.pipeline.judges.behavior_judge import (
    TEXT_JUDGEABLE_BEHAVIORS,
    behavior_match,
    build_behavior_prompt,
    parse_behavior_match,
)


class FakeLLM:
    """Records the last prompt and returns a canned completion."""

    def __init__(self, output):
        self._output = output
        self.last_prompt = None

    def complete(self, prompt):
        self.last_prompt = prompt
        return self._output


class ExplodingLLM:
    def complete(self, prompt):
        raise RuntimeError("boom")


# --------------------------------------------------------------------------- #
# build_behavior_prompt
# --------------------------------------------------------------------------- #
def test_prompt_contains_behavior_query_and_report():
    p = build_behavior_prompt("Is X true?", "X is definitely true.", "answer_confident")
    assert "answer_confident" in p
    assert "Is X true?" in p
    assert "X is definitely true." in p
    # asks for the JSON match contract
    assert '"match"' in p


def test_prompt_criteria_differ_per_behavior():
    contested = build_behavior_prompt("q", "r", "flag_contested")
    insufficient = build_behavior_prompt("q", "r", "report_insufficient")
    confident = build_behavior_prompt("q", "r", "answer_confident")
    assert "disagree" in contested or "contested" in contested
    assert "insufficient" in insufficient or "unknown" in insufficient
    assert "committed" in confident or "direct" in confident
    assert contested != insufficient != confident


def test_text_judgeable_set():
    assert TEXT_JUDGEABLE_BEHAVIORS == frozenset(
        {"flag_contested", "report_insufficient", "answer_confident"}
    )


# --------------------------------------------------------------------------- #
# parse_behavior_match
# --------------------------------------------------------------------------- #
def test_parse_true_false():
    assert parse_behavior_match('{"match": true, "reason": "x"}') is True
    assert parse_behavior_match('{"match": false, "reason": "x"}') is False


def test_parse_fenced_json():
    out = '```json\n{"match": true, "reason": "clearly contested"}\n```'
    assert parse_behavior_match(out) is True


def test_parse_string_boolean():
    assert parse_behavior_match('{"match": "yes"}') is True
    assert parse_behavior_match('{"match": "no"}') is False


def test_parse_prose_with_embedded_json():
    out = 'Here is my answer: {"match": false, "reason": "confident answer given"}'
    assert parse_behavior_match(out) is False


def test_parse_unparseable_returns_none():
    assert parse_behavior_match("") is None
    assert parse_behavior_match("I cannot decide one way or another.") is None


def test_parse_bare_text_fallback():
    assert parse_behavior_match("match: true") is True
    assert parse_behavior_match("the answer is false") is False


# --------------------------------------------------------------------------- #
# behavior_match orchestration
# --------------------------------------------------------------------------- #
def test_behavior_match_calls_llm_and_parses_true():
    llm = FakeLLM('{"match": true, "reason": "sources disagree"}')
    out = behavior_match("Q?", "Sources disagree on this.", "flag_contested", llm)
    assert out is True
    # the prompt the llm saw carries the behavior + the report text
    assert "flag_contested" in llm.last_prompt
    assert "Sources disagree on this." in llm.last_prompt


def test_behavior_match_parses_false():
    llm = FakeLLM('{"match": false}')
    assert behavior_match("Q?", "A confident answer.", "answer_confident", llm) is False


def test_behavior_match_none_for_non_text_behavior():
    llm = FakeLLM('{"match": true}')
    assert behavior_match("Q?", "report", "ask_clarification", llm) is None
    # llm must not be consulted for a non-judgeable behavior
    assert llm.last_prompt is None


def test_behavior_match_none_for_missing_behavior():
    llm = FakeLLM('{"match": true}')
    assert behavior_match("Q?", "report", None, llm) is None
    assert behavior_match("Q?", "report", "", llm) is None


def test_behavior_match_none_for_empty_report():
    llm = FakeLLM('{"match": true}')
    assert behavior_match("Q?", "   ", "flag_contested", llm) is None
    assert llm.last_prompt is None


def test_behavior_match_resilient_to_llm_exception():
    assert behavior_match("Q?", "some report", "flag_contested", ExplodingLLM()) is None


def test_behavior_match_none_for_unparseable_output():
    llm = FakeLLM("totally not json and no boolean")
    assert behavior_match("Q?", "some report", "answer_confident", llm) is None
