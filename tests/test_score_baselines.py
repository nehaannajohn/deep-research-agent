"""Baseline-scoring driver tests (fakes only, no network).

Covers:
- `score_gradable` is behavior-preserving: scoring a fixture `GradableReport`
  with fake judges/panel/extractor returns exactly what `evaluate_item`
  produces for the same report (proves the refactor out of `evaluate_item`).
- the baseline driver's pure helpers: source normalization, the keyword
  matcher, `score_record` (saved record -> GradableReport -> per-item dict via
  a fake adapter/decomposer/matcher) and aggregation over fake per-item results.

No network: the decomposer, matcher, judges, panel and extractor are all fakes;
a canned saved-response record flows through the real adapter + score_gradable.
"""
from __future__ import annotations

import json

import pytest

from dra.eval.pipeline.adapters.perplexity import PerplexityAdapter
from dra.eval.pipeline.contracts import (
    EvalItem,
    GradableClaim,
    GradableReport,
)
from dra.eval.pipeline.harness import PipelineDeps, evaluate_item, score_gradable
from dra.schemas import Citation, Claim, Passage, ReportMetadata, ResearchReport


# --------------------------------------------------------------------------- #
# Shared fakes (mirror tests/test_eval_pipeline_harness.py)
# --------------------------------------------------------------------------- #
class FakeGroundingJudge:
    def verdict(self, claim_text, passages):
        return "supported"


class FakePanel:
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


def _deps():
    return PipelineDeps(
        run_query=lambda q: None,  # unused by score_gradable
        grounding_judge=FakeGroundingJudge(),
        panel=FakePanel(),
        extractor=FakeExtractor(),
    )


# --------------------------------------------------------------------------- #
# score_gradable is behavior-identical to evaluate_item's scoring half
# --------------------------------------------------------------------------- #
def _canned_report(query="What is the capital of France?") -> ResearchReport:
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
            overall_confidence=0.85, coverage=0.9, descriptive_summary="Paris"
        ),
    )


def test_score_gradable_returns_expected_axis_keys():
    item = EvalItem(id="frames-000", tier="agentic", query="What is the capital of France?",
                    gold_answer="Paris")
    from dra.eval.pipeline.adapters.dra import to_gradable

    g = to_gradable(_canned_report(), constraints=item.constraints)
    result = score_gradable(g, item, _deps(), seed=13)

    assert set(result) >= {
        "id", "tier", "grounding", "relevance", "quality", "formatting",
        "task_accuracy", "extracted_answer", "ece", "expected_behavior",
        "expected_behavior_match",
    }
    assert result["grounding"]["grounding_rate"] == pytest.approx(1.0)
    assert result["relevance"]["aggregate"] == 4


def test_score_gradable_matches_evaluate_item_for_same_report():
    """The refactor is behavior-preserving: feeding evaluate_item's own gradable
    report into score_gradable yields the identical per-item dict."""
    item = EvalItem(id="frames-000", tier="agentic", query="What is the capital of France?",
                    gold_answer="Paris")

    # evaluate_item generates the report via run_query, adapts, then scores.
    deps_eval = PipelineDeps(
        run_query=lambda q: _canned_report(q),
        grounding_judge=FakeGroundingJudge(),
        panel=FakePanel(),
        extractor=FakeExtractor(),
    )
    via_evaluate_item = evaluate_item(item, deps_eval, seed=13)

    # score_gradable on the *same* adapted report must match exactly.
    from dra.eval.pipeline.adapters.dra import to_gradable

    g = to_gradable(_canned_report(item.query), constraints=item.constraints)
    via_score_gradable = score_gradable(g, item, _deps(), seed=13)

    assert via_score_gradable == via_evaluate_item


# --------------------------------------------------------------------------- #
# Driver pure helpers
# --------------------------------------------------------------------------- #
def _ppx_record() -> dict:
    """A saved Perplexity response (collect_dra_baselines.write_record shape)."""
    return {
        "id": "dra-type1-011",
        "provider": "perplexity",
        "query": "How do large language models learn in context?",
        "narrative": "LLMs learn in context. Few-shot prompting steers them.",
        "sources": [
            "https://news.mit.edu/in-context",
            "https://openreview.net/forum",
        ],
        "citations": ["https://news.mit.edu/in-context"],
        "raw": {
            "search_results": [
                {
                    "title": "Machine-learning mystery | MIT News",
                    "url": "https://news.mit.edu/in-context",
                    "snippet": "Large language models learn in context from a few examples.",
                },
                {
                    "title": "Few-shot prompting",
                    "url": "https://openreview.net/forum",
                    "snippet": "Few-shot prompting steers model behavior at inference.",
                },
            ]
        },
    }


def _openai_record() -> dict:
    """A saved OpenAI response: sources are URLs, titles via annotations."""
    return {
        "id": "dra-type1-011",
        "provider": "openai",
        "query": "How do large language models learn in context?",
        "narrative": "LLMs learn in context. Few-shot prompting steers them.",
        "sources": ["https://aiwiki.ai/in_context"],
        "citations": ["https://aiwiki.ai/in_context"],
        "raw": {
            "choices": [
                {
                    "message": {
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url_citation": {
                                    "title": "In-Context Learning | AI Wiki",
                                    "url": "https://aiwiki.ai/in_context",
                                },
                            }
                        ]
                    }
                }
            ]
        },
    }


def test_normalize_sources_perplexity_uses_search_result_snippets():
    from experiments.code.score_baselines import normalize_sources

    passages = normalize_sources(_ppx_record())
    assert all(isinstance(p, Passage) for p in passages)
    assert len(passages) == 2
    # title + snippet carried so the matcher/judge have real text
    first = passages[0]
    assert first.url == "https://news.mit.edu/in-context"
    assert "in context" in first.text.lower()
    assert "MIT News" in first.title
    # stable source ids
    assert first.source_id


def test_normalize_sources_openai_uses_annotation_titles():
    from experiments.code.score_baselines import normalize_sources

    passages = normalize_sources(_openai_record())
    assert len(passages) == 1
    assert passages[0].url == "https://aiwiki.ai/in_context"
    assert "AI Wiki" in passages[0].title


def test_normalize_sources_falls_back_to_urls_only():
    from experiments.code.score_baselines import normalize_sources

    rec = {"sources": ["http://x.example", "http://y.example"], "raw": {}}
    passages = normalize_sources(rec)
    assert [p.url for p in passages] == ["http://x.example", "http://y.example"]
    assert all(isinstance(p, Passage) for p in passages)


def test_keyword_matcher_links_claim_to_overlapping_source():
    from experiments.code.score_baselines import keyword_matcher, normalize_sources

    sources = normalize_sources(_ppx_record())
    cits = keyword_matcher("Large language models learn in context.", sources)
    assert cits  # matched at least one source
    assert all(isinstance(c, Citation) for c in cits)
    # the MIT snippet (in-context) should be the match, not the few-shot one
    matched_ids = {c.source_id for c in cits}
    assert sources[0].source_id in matched_ids


def test_keyword_matcher_no_overlap_returns_empty():
    from experiments.code.score_baselines import keyword_matcher, normalize_sources

    sources = normalize_sources(_ppx_record())
    assert keyword_matcher("Quantum entanglement violates Bell inequalities.", sources) == []


def test_score_record_end_to_end_with_fakes():
    """A saved record -> real PerplexityAdapter (fake decomposer + the real
    keyword matcher) -> score_gradable -> a per-item dict with all axes."""
    from experiments.code.score_baselines import keyword_matcher, normalize_sources, score_record

    record = _ppx_record()
    item = EvalItem(
        id="dra-type1-011",
        tier="dra_bench",
        query=record["query"],
        expected_behavior="answer_confident",
    )

    # fake decomposer: narrative -> two atomic claims (real run uses a Bedrock model)
    def fake_decomposer(narrative):
        return [
            "Large language models learn in context.",
            "Few-shot prompting steers them.",
        ]

    adapter = PerplexityAdapter(decomposer=fake_decomposer, matcher=keyword_matcher)
    result = score_record(record, item, adapter, _deps(), seed=13)

    assert result["id"] == "dra-type1-011"
    assert result["tier"] == "dra_bench"
    assert result["grounding"]["n_claims"] == 2
    # both claims matched a source -> grounded under the fake judge
    assert result["grounding"]["grounding_rate"] == pytest.approx(1.0)
    assert result["relevance"]["aggregate"] == 4
    assert result["expected_behavior"] == "answer_confident"


def test_aggregate_over_two_fake_results():
    from experiments.code.score_baselines import aggregate

    def fake_item(gr, rel, qual):
        return {
            "id": f"i{gr}",
            "tier": "dra_bench",
            "grounding": {"grounding_rate": gr, "hallucination_rate": 1 - gr},
            "relevance": {"aggregate": rel},
            "quality": {"aggregate": qual},
            "formatting": {"pass_rate": 1.0},
            "task_accuracy": None,
            "expected_behavior_match": None,
        }

    summary = aggregate([fake_item(1.0, 4, 5), fake_item(0.5, 2, 3)])
    assert summary["n"] == 2
    assert summary["grounding_rate"] == pytest.approx(0.75)
    assert summary["relevance_mean"] == pytest.approx(3.0)
    assert summary["quality_mean"] == pytest.approx(4.0)
    assert summary["hallucination_rate"] == pytest.approx(0.25)


def test_load_record_reads_json(tmp_path):
    from experiments.code.score_baselines import load_record

    p = tmp_path / "dra-type1-011.json"
    p.write_text(json.dumps(_ppx_record()), encoding="utf-8")
    rec = load_record(str(p))
    assert rec["id"] == "dra-type1-011"
    assert rec["provider"] == "perplexity"


# --------------------------------------------------------------------------- #
# baseline_grounding: judged against the FULL source set, N/A when no text
# --------------------------------------------------------------------------- #
def _gradable(claims, sources):
    return GradableReport(query="q", claims=claims, sources=sources)


def test_baseline_grounding_applicable_judges_all_sources():
    """Text-bearing sources -> the judge runs per claim over ALL sources;
    grounding/hallucination rates reflect the verdicts; precision/recall None."""
    from experiments.code.score_baselines import baseline_grounding

    sources = [
        Passage(source_id="s0", text="Paris is the capital of France.", url="http://a"),
        Passage(source_id="s1", text="The city lies on the Seine.", url="http://b"),
    ]
    claims = [
        GradableClaim(id="c0", text="Paris is the capital of France."),
        GradableClaim(id="c1", text="It is on the Seine."),
        GradableClaim(id="c2", text="Unrelated fabricated claim."),
    ]

    seen_passages = []

    class CountingJudge:
        def verdict(self, claim_text, passages):
            seen_passages.append(list(passages))
            return "supported" if "Paris" in claim_text or "Seine" in claim_text else "insufficient"

    out = baseline_grounding(_gradable(claims, sources), CountingJudge())
    assert out["applicable"] is True
    assert out["n_claims"] == 3
    assert out["grounding_rate"] == pytest.approx(2 / 3)
    assert out["hallucination_rate"] == pytest.approx(1 / 3)
    assert out["citation_precision"] is None
    assert out["citation_recall"] is None
    # every claim was judged against the FULL text-bearing source set
    assert all(len(p) == 2 for p in seen_passages)


def test_baseline_grounding_na_when_no_text_sources_and_judge_not_called():
    """OpenAI title-only sources (no Passage text) -> N/A, judge never called."""
    from experiments.code.score_baselines import baseline_grounding

    sources = [
        Passage(source_id="s0", text="", url="http://a", title="In-Context Learning"),
        Passage(source_id="s1", text="", url="http://b", title="Few-shot"),
    ]
    claims = [GradableClaim(id="c0", text="LLMs learn in context.")]

    class ExplodingJudge:
        def verdict(self, claim_text, passages):
            raise AssertionError("judge must not be called when grounding is N/A")

    out = baseline_grounding(_gradable(claims, sources), ExplodingJudge())
    assert out == {"applicable": False}


def test_score_record_openai_grounding_na_but_other_axes_present():
    """OpenAI-style record (title-only sources) -> grounding N/A, but
    relevance/quality/formatting are still reported."""
    from experiments.code.score_baselines import keyword_matcher, score_record
    from dra.eval.pipeline.adapters.openai import OpenAIAdapter

    record = _openai_record()
    item = EvalItem(id="dra-type1-011", tier="dra_bench", query=record["query"])

    def fake_decomposer(narrative):
        return ["LLMs learn in context.", "Few-shot prompting steers them."]

    adapter = OpenAIAdapter(decomposer=fake_decomposer, matcher=keyword_matcher)
    result = score_record(record, item, adapter, _deps(), seed=13)

    assert result["grounding"] == {"applicable": False}
    assert result["relevance"]["aggregate"] == 4
    assert result["quality"]["aggregate"] == 4
    assert "pass_rate" in result["formatting"]
