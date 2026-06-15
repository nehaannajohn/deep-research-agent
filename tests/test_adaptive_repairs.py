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

def test_reformulate_rewords_subquery_using_weak_claims():
    llm = _LLM("transformer attention quadratic complexity sequence length evidence")
    q = reformulate("How does attention scale?",
                    ["Self-attention is O(n^2) in sequence length"], llm)
    assert q == "transformer attention quadratic complexity sequence length evidence"
    # both the sub-question and the weak claim are in the prompt
    assert "How does attention scale?" in llm.last_prompt
    assert "Self-attention is O(n^2)" in llm.last_prompt


def test_reformulate_strips_quotes_and_takes_first_line():
    llm = _LLM('"best query here"\nignored second line')
    assert reformulate("subq", ["c"], llm) == "best query here"


def test_reformulate_falls_back_to_subquestion_when_empty():
    assert reformulate("the original sub-question", ["c"], _LLM("   ")) == "the original sub-question"


# ---- source recommender ----

def test_recommend_sources_returns_net_new_fetchable_urls():
    reply = (
        'Here you go:\n[{"url": "https://data.worldbank.org/indicator/NY.GDP", '
        '"kind": "official statistics", "covers": "GDP figures"}, '
        '{"url": "https://www.who.int/data/gho", "kind": "registry", "covers": "mortality"}]'
    )
    out = recommend_sources("What is the GDP impact?",
                            ["https://www.who.int/health-topics"],   # WHO already cited
                            ["GDP fell 3% in 2020"], _LLM(reply))
    # who.int host already cited (www. prefix stripped) -> dropped; worldbank net-new -> kept
    assert [r["url"] for r in out] == ["https://data.worldbank.org/indicator/NY.GDP"]
    assert out[0]["kind"] == "official statistics"


def test_recommend_prompt_includes_cited_urls_and_net_new_instruction():
    llm = _LLM("[]")
    recommend_sources("q", ["https://example.com/a"], ["claim x"], llm)
    assert "https://example.com/a" in llm.last_prompt
    assert "NET-NEW" in llm.last_prompt


def test_recommend_sources_rejects_non_urls_and_dupes():
    reply = ('[{"url": "who.int", "kind": "k", "covers": "c"},'          # not http -> reject
             ' {"url": "https://nih.gov/x", "kind": "k", "covers": "c"},'
             ' {"url": "https://nih.gov/x", "kind": "k", "covers": "c"}]')  # dup -> once
    out = recommend_sources("q", [], ["c"], _LLM(reply))
    assert [r["url"] for r in out] == ["https://nih.gov/x"]


def test_recommend_sources_empty_on_garbage():
    assert recommend_sources("q", [], ["c"], _LLM("no json here")) == []
