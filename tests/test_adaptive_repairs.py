"""Unit tests for the two adaptive repairs' pure logic (LLM injected)."""
from __future__ import annotations

from dra.adaptive.reformulate import reformulate
from dra.adaptive.source_recommender import recommend_sources


class _LLM:
    def __init__(self, reply):
        self.reply = reply
        self.last_prompt = None

    def complete(self, prompt):
        self.last_prompt = prompt
        return self.reply


# ---- reformulate ----

def test_reformulate_returns_focused_query_and_sees_claim():
    llm = _LLM("transformer attention quadratic complexity sequence length evidence")
    q = reformulate("Self-attention is O(n^2) in sequence length", "How does attention scale?", llm)
    assert q == "transformer attention quadratic complexity sequence length evidence"
    assert "Self-attention is O(n^2)" in llm.last_prompt  # claim is in the prompt


def test_reformulate_strips_quotes_and_takes_first_line():
    llm = _LLM('"best query here"\nignored second line')
    assert reformulate("c", "s", llm) == "best query here"


def test_reformulate_falls_back_to_claim_when_empty():
    assert reformulate("the claim text", "s", _LLM("   ")) == "the claim text"


# ---- source recommender ----

def test_recommend_sources_parses_and_keeps_new_sources():
    reply = (
        'Here you go:\n[{"source": "data.worldbank.org", "kind": "official statistics", '
        '"covers": "GDP figures"}, {"source": "WHO (who.int)", "kind": "registry", '
        '"covers": "mortality"}]'
    )
    out = recommend_sources("What is the GDP impact?",
                            ["World Bank blog — blogs.worldbank.org"],
                            ["GDP fell 3% in 2020"], _LLM(reply))
    assert {r["source"] for r in out} == {"data.worldbank.org", "WHO (who.int)"}
    assert out[0]["kind"] == "official statistics"


def test_recommend_sources_drops_already_covered_domain():
    # recommendation domain already among existing Exa sources -> dropped
    reply = '[{"source": "who.int fact sheet", "kind": "x", "covers": "y"}]'
    out = recommend_sources("q", ["WHO — who.int"], ["claim"], _LLM(reply))
    assert out == []


def test_recommend_sources_empty_on_garbage():
    assert recommend_sources("q", [], ["c"], _LLM("no json here")) == []
