"""Phase 3 — statistics toolkit + system adapters (pure logic, fakes only).

Closed-form fixtures; no network. Covers `stats/reliability.py`,
`stats/significance.py`, `scoring/decompose.py`, and `adapters/{dra,perplexity,openai}.py`.
"""
from __future__ import annotations

import math

import pytest

from dra.eval.pipeline.stats.reliability import cohen_kappa, human_validation_summary
from dra.eval.pipeline.stats.significance import (
    holm,
    mcnemar,
    paired_t,
    unit_of_analysis,
)
from dra.eval.pipeline.scoring.decompose import decompose_report
from dra.eval.pipeline.adapters.dra import to_gradable as dra_to_gradable
from dra.eval.pipeline.adapters.perplexity import PerplexityAdapter
from dra.eval.pipeline.adapters.openai import OpenAIAdapter

from dra.schemas import (
    Citation,
    Claim,
    Passage,
    ResearchReport,
    ReportMetadata,
)


# --------------------------------------------------------------------------- #
# reliability
# --------------------------------------------------------------------------- #
def test_cohen_kappa_known_value():
    # a/b chosen so po=0.75, pe=0.5 -> kappa = 0.5 exactly.
    a = [1, 1, 0, 0]
    b = [1, 0, 0, 0]
    assert cohen_kappa(a, b) == pytest.approx(0.5)


def test_cohen_kappa_perfect_agreement():
    assert cohen_kappa(["x", "y", "z"], ["x", "y", "z"]) == pytest.approx(1.0)


def test_human_validation_summary_agreement_and_n():
    panel = ["a", "a", "b", "b", "c"]
    human = ["a", "b", "b", "b", "c"]  # 4/5 agree
    out = human_validation_summary(panel, human)
    assert out["n"] == 5
    assert out["agreement"] == pytest.approx(0.8)


# --------------------------------------------------------------------------- #
# significance — paired-t
# --------------------------------------------------------------------------- #
def test_paired_t_sign_and_n():
    a = [0.9, 0.8, 0.85, 0.95, 0.7]
    b = [0.6, 0.52, 0.5, 0.66, 0.45]  # a consistently higher, varied diffs
    out = paired_t(a, b)
    assert out["n"] == 5
    expected_md = sum(x - y for x, y in zip(a, b)) / 5
    assert out["mean_diff"] == pytest.approx(expected_md, abs=1e-9)
    assert out["statistic"] > 0  # a > b
    assert out["p_value"] < 0.05  # strongly significant


# --------------------------------------------------------------------------- #
# significance — McNemar (exact vs chi-square paths)
# --------------------------------------------------------------------------- #
def test_mcnemar_exact_path_small_discordant():
    # A right / B wrong vs A wrong / B right -> b=2, c=6, b+c=8 (<25) -> exact.
    a_correct = [1, 1, 0, 0, 0, 0, 0, 0, 1, 1]
    b_correct = [0, 0, 1, 1, 1, 1, 1, 1, 1, 1]
    out = mcnemar(a_correct, b_correct)
    assert out["b"] == 2  # A right, B wrong
    assert out["c"] == 6  # A wrong, B right
    assert out["method"] == "exact"
    from scipy.stats import binomtest

    assert out["p_value"] == pytest.approx(binomtest(2, 8, 0.5).pvalue)


def test_mcnemar_chi2_path_large_discordant():
    # b=20, c=10, b+c=30 (>=25) -> chi-square w/ continuity correction.
    a_correct = [1] * 20 + [0] * 10
    b_correct = [0] * 20 + [1] * 10
    out = mcnemar(a_correct, b_correct)
    assert out["b"] == 20
    assert out["c"] == 10
    assert out["method"] == "chi2"
    expected_stat = ((abs(20 - 10) - 1) ** 2) / (20 + 10)  # 81/30 = 2.7
    assert out["statistic"] == pytest.approx(expected_stat)
    from scipy.stats import chi2

    assert out["p_value"] == pytest.approx(chi2.sf(expected_stat, 1))


# --------------------------------------------------------------------------- #
# significance — Holm
# --------------------------------------------------------------------------- #
def test_holm_partial_reject_and_monotonic():
    # sorted: 0.01, 0.03, 0.04 ; thresholds 0.0167, 0.025, 0.05
    # 0.01 < 0.0167 reject ; 0.03 > 0.025 stop -> b,c not rejected.
    pvals = {"a": 0.01, "b": 0.03, "c": 0.04}
    out = holm(pvals, alpha=0.05)
    assert out["a"]["reject"] is True
    assert out["b"]["reject"] is False
    assert out["c"]["reject"] is False
    # p_adj monotonic non-decreasing in p order
    adj = [out["a"]["p_adj"], out["b"]["p_adj"], out["c"]["p_adj"]]
    assert adj == sorted(adj)
    # smallest p_adj = 0.01 * 3
    assert out["a"]["p_adj"] == pytest.approx(0.03)


def test_holm_all_reject():
    pvals = {"x": 0.001, "y": 0.002, "z": 0.003}
    out = holm(pvals, alpha=0.05)
    assert all(out[k]["reject"] for k in pvals)


def test_unit_of_analysis_tags():
    assert unit_of_analysis("grounding") == "claim-level"
    assert unit_of_analysis("relevance") == "prompt-level"
    assert unit_of_analysis("task_accuracy") == "prompt-level"


# --------------------------------------------------------------------------- #
# decompose (injected fake decomposer)
# --------------------------------------------------------------------------- #
def test_decompose_report_uses_injected_decomposer():
    calls = {}

    def fake_decomposer(narrative):
        calls["narrative"] = narrative
        return ["claim one", "claim two"]

    out = decompose_report("Some narrative markdown.", fake_decomposer)
    assert out == ["claim one", "claim two"]
    assert calls["narrative"] == "Some narrative markdown."


# --------------------------------------------------------------------------- #
# adapters — dra
# --------------------------------------------------------------------------- #
def _fixture_report() -> ResearchReport:
    return ResearchReport(
        query="What is X?",
        report_markdown="# Title\n\nX is a thing.",
        claims=[
            Claim(
                id="c0",
                text="X is a thing.",
                section="intro",
                citations=[Citation(source_id="s1", span="X is a thing.")],
                verdict="supported",
                confidence=0.9,
            ),
            Claim(
                id="c1",
                text="X is also Y.",
                section="body",
                citations=[Citation(source_id="s2", span="X is Y.")],
                verdict="insufficient",
                confidence=0.3,
            ),
        ],
        sources=[
            Passage(source_id="s1", text="X is a thing.", url="http://a", title="A"),
            Passage(source_id="s2", text="X is Y.", url="http://b", title="B"),
        ],
        metadata=ReportMetadata(
            overall_confidence=0.7,
            coverage=0.8,
            instruction_adherence={"format": "ok"},
            run_id="r1",
        ),
    )


def test_dra_to_gradable_field_map():
    report = _fixture_report()
    g = dra_to_gradable(report, constraints={"format": "markdown"})

    assert g.query == "What is X?"
    assert g.narrative_markdown == "# Title\n\nX is a thing."
    assert len(g.claims) == 2

    c0 = g.claims[0]
    assert c0.id == "c0"
    assert c0.text == "X is a thing."
    assert c0.verdict == "supported"
    assert c0.confidence == pytest.approx(0.9)
    assert c0.citations[0].source_id == "s1"

    assert [p.source_id for p in g.sources] == ["s1", "s2"]
    assert g.constraints == {"format": "markdown"}
    # metadata carries the report metadata
    assert g.metadata["overall_confidence"] == pytest.approx(0.7)
    assert g.metadata["instruction_adherence"] == {"format": "ok"}


def test_dra_to_gradable_default_constraints():
    g = dra_to_gradable(_fixture_report())
    assert g.constraints == {}


# --------------------------------------------------------------------------- #
# adapters — perplexity (fake decomposer + fake matcher)
# --------------------------------------------------------------------------- #
def _fake_raw_response():
    return {
        "query": "Tell me about X.",
        "narrative": "X is great. X is also fast.",
        "sources": [
            Passage(source_id="u1", text="X is great.", url="http://x1"),
            Passage(source_id="u2", text="X is fast.", url="http://x2"),
        ],
    }


def test_perplexity_adapter_builds_claims_verdict_none():
    raw = _fake_raw_response()

    def fake_decomposer(narrative):
        assert narrative == raw["narrative"]
        return ["X is great.", "X is also fast."]

    def fake_matcher(claim_text, sources):
        # match each claim to the source whose text shares its first word
        first = claim_text.split()[0].lower()
        return [
            Citation(source_id=p.source_id, span=p.text)
            for p in sources
            if first in p.text.lower()
        ]

    adapter = PerplexityAdapter(decomposer=fake_decomposer, matcher=fake_matcher)
    g = adapter.to_gradable(raw)

    assert g.query == "Tell me about X."
    assert g.narrative_markdown == "X is great. X is also fast."
    assert len(g.claims) == 2
    for c in g.claims:
        # verdict/confidence left for the independent grounding judge downstream
        assert c.verdict is None
        assert c.confidence is None
    # citations come from the injected matcher
    assert g.claims[0].citations[0].source_id == "u1"
    assert [p.source_id for p in g.sources] == ["u1", "u2"]


def test_openai_adapter_shape_parity():
    raw = _fake_raw_response()

    def fake_decomposer(narrative):
        return ["X is great."]

    def fake_matcher(claim_text, sources):
        return [Citation(source_id=sources[0].source_id, span=sources[0].text)]

    adapter = OpenAIAdapter(decomposer=fake_decomposer, matcher=fake_matcher)
    g = adapter.to_gradable(raw)
    assert len(g.claims) == 1
    assert g.claims[0].verdict is None
    assert g.claims[0].citations[0].source_id == "u1"
