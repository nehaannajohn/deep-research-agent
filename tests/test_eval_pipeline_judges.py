"""Phase 2 — answer-extraction + blind judge panel + independent grounding judge.

All model dependencies (extractor, panel judges, grounding-judge llm) are
injected as fakes with canned behaviour. No live network. Mirrors the
fakes-only convention of Phase 1's scoring tests.
"""
from __future__ import annotations

from dra.schemas import Passage

from dra.eval.pipeline.contracts import GradableReport
from dra.eval.pipeline.judges.panel import JudgePanel
from dra.eval.pipeline.judges.grounding_judge import LLMGroundingJudge
from dra.eval.pipeline.judges.rubrics import relevance_rubric, quality_rubric
from dra.eval.pipeline.scoring.answer_extraction import extract_answer
from dra.eval.pipeline.scoring.relevance import score_relevance
from dra.eval.pipeline.scoring.quality import score_quality


# --------------------------------------------------------------------------- #
# answer extraction
# --------------------------------------------------------------------------- #
class FakeExtractor:
    """Records calls; returns a canned span (the LLM extraction path)."""

    def __init__(self, span: str):
        self.span = span
        self.calls: list[str] = []

    def complete(self, prompt: str, **kw) -> str:
        self.calls.append(prompt)
        return self.span


def test_extraction_rule_fast_path_summary_hit_no_model_call():
    report = GradableReport(
        query="What is the capital of France?",
        narrative_markdown="A long narrative discussing many things.",
        metadata={"descriptive_summary": "The capital of France is Paris."},
    )
    extractor = FakeExtractor("SHOULD NOT BE CALLED")
    ans = extract_answer(report, report.query, aliases=["Paris"], extractor=extractor)
    assert ans == "Paris"
    # fast path -> the extractor was never invoked
    assert extractor.calls == []


def test_extraction_rule_fast_path_first_sentence_hit():
    report = GradableReport(
        query="What is the capital of France?",
        narrative_markdown="Paris is the capital. It has many museums and parks.",
    )
    extractor = FakeExtractor("nope")
    ans = extract_answer(report, report.query, aliases=["Paris"], extractor=extractor)
    assert ans == "Paris"
    assert extractor.calls == []


def test_extraction_llm_path_returns_span():
    report = GradableReport(
        query="What is the capital of France?",
        narrative_markdown="A meandering narrative that never names the city plainly.",
        metadata={"descriptive_summary": "Discussion of European geography."},
    )
    extractor = FakeExtractor("Paris")
    ans = extract_answer(report, report.query, aliases=["Paris"], extractor=extractor)
    assert ans == "Paris"
    # no alias in summary/first sentence -> LLM extraction ran
    assert len(extractor.calls) == 1


def test_extraction_abstention_insufficient():
    report = GradableReport(
        query="What is the capital of Atlantis?",
        narrative_markdown="The report does not commit to any answer here.",
    )
    extractor = FakeExtractor("INSUFFICIENT")
    ans = extract_answer(report, report.query, extractor=extractor)
    assert ans == "INSUFFICIENT"


# --------------------------------------------------------------------------- #
# judge panel
# --------------------------------------------------------------------------- #
class FakeJudge:
    """A panel judge: returns a canned {score, justification}; records prompts."""

    def __init__(self, score: int, justification: str = "ok"):
        self.score = score
        self.justification = justification
        self.prompts: list[str] = []

    def complete_json(self, prompt: str, **kw) -> dict:
        self.prompts.append(prompt)
        return {"score": self.score, "justification": self.justification}


def test_panel_mean_and_majority_aggregate():
    panel = JudgePanel([FakeJudge(4), FakeJudge(4), FakeJudge(5)])
    out = panel.score("RUBRIC PROMPT", seed=1)
    assert out["per_judge"] == [4, 4, 5]
    assert out["mean"] == (4 + 4 + 5) / 3
    assert out["majority"] == 4  # two 4s vs one 5
    assert out["aggregate"] == 4
    assert out["adjudicated"] is False


def test_panel_adjudication_triggers_on_divergence():
    # spread = 5 - 1 = 4 > threshold(2) -> adjudicated
    panel = JudgePanel([FakeJudge(1), FakeJudge(3), FakeJudge(5)])
    out = panel.score("RUBRIC PROMPT", seed=1)
    assert out["adjudicated"] is True


def test_panel_no_adjudication_when_judges_agree():
    panel = JudgePanel([FakeJudge(4), FakeJudge(4), FakeJudge(5)])
    out = panel.score("RUBRIC PROMPT", seed=1)
    # spread = 1 <= threshold -> no adjudication
    assert out["adjudicated"] is False


def test_panel_is_blind_no_system_identity_in_prompt():
    judges = [FakeJudge(4), FakeJudge(4)]
    panel = JudgePanel(judges)
    panel.score("Score this REPORT for relevance.", seed=7)
    for j in judges:
        for p in j.prompts:
            low = p.lower()
            assert "deep research agent" not in low
            assert "perplexity" not in low
            assert "fable" not in low


def test_panel_order_deterministic_under_seed():
    candidates = ["report-A", "report-B", "report-C"]
    j1 = FakeJudge(4)
    p1 = JudgePanel([j1])
    p1.score("base prompt", seed=42, candidates=candidates)
    j2 = FakeJudge(4)
    p2 = JudgePanel([j2])
    p2.score("base prompt", seed=42, candidates=candidates)
    # same seed -> identical (shuffled) prompt presentation
    assert j1.prompts == j2.prompts
    # a different seed generally yields a different order presentation
    j3 = FakeJudge(4)
    p3 = JudgePanel([j3])
    p3.score("base prompt", seed=0, candidates=candidates)
    # a different seed yields a different presentation order (seed 0 != seed 42)
    assert j3.prompts != j1.prompts


# --------------------------------------------------------------------------- #
# independent grounding judge
# --------------------------------------------------------------------------- #
class FakeLLM:
    """Injected llm for the grounding judge: returns a canned raw string."""

    def __init__(self, raw: str):
        self.raw = raw
        self.calls: list[str] = []

    def complete(self, prompt: str, **kw) -> str:
        self.calls.append(prompt)
        return self.raw


def test_grounding_judge_maps_canned_verdict():
    llm = FakeLLM('{"label": "supported", "reasoning": "passages entail it"}')
    judge = LLMGroundingJudge(llm)
    v = judge.verdict("Paris is the capital of France.",
                      [Passage(source_id="s1", text="Paris is the capital of France.")])
    assert v == "supported"
    assert len(llm.calls) == 1


def test_grounding_judge_no_passages_is_insufficient():
    llm = FakeLLM('{"label": "supported"}')
    judge = LLMGroundingJudge(llm)
    v = judge.verdict("An uncited claim.", [])
    assert v == "insufficient"
    # no model call needed when there are no passages
    assert llm.calls == []


def test_grounding_judge_resilient_to_malformed_json():
    llm = FakeLLM("the model truncated mid-thought and never closed the brace {")
    judge = LLMGroundingJudge(llm)
    v = judge.verdict("Some claim.", [Passage(source_id="s1", text="evidence")])
    # does not crash; falls back to a safe label
    assert v == "insufficient"


def test_grounding_judge_coerces_unknown_label():
    llm = FakeLLM('{"label": "totally-made-up"}')
    judge = LLMGroundingJudge(llm)
    v = judge.verdict("Some claim.", [Passage(source_id="s1", text="evidence")])
    assert v == "insufficient"


def test_grounding_judge_satisfies_protocol():
    from dra.eval.pipeline.scoring.grounding import GroundingJudge

    llm = FakeLLM('{"label": "refuted"}')
    judge: GroundingJudge = LLMGroundingJudge(llm)
    assert judge.verdict("c", [Passage(source_id="s1", text="x")]) == "refuted"


# --------------------------------------------------------------------------- #
# relevance / quality wrappers
# --------------------------------------------------------------------------- #
class FakePanel:
    """Records the rubric prompt it was handed; returns a canned aggregate dict."""

    def __init__(self, aggregate: int = 4):
        self.aggregate = aggregate
        self.prompts: list[str] = []

    def score(self, rubric_prompt: str, *, seed: int, **kw) -> dict:
        self.prompts.append(rubric_prompt)
        return {"aggregate": self.aggregate, "mean": float(self.aggregate),
                "majority": self.aggregate, "per_judge": [self.aggregate],
                "adjudicated": False}


def test_relevance_wrapper_calls_through_to_panel():
    report = GradableReport(query="q", narrative_markdown="some report body")
    panel = FakePanel(aggregate=5)
    out = score_relevance(report, "q", panel, seed=3)
    assert out["aggregate"] == 5
    assert len(panel.prompts) == 1
    # it built a relevance rubric (mentions the query/relevance)
    assert "relevance" in panel.prompts[0].lower()


def test_quality_wrapper_calls_through_to_panel():
    report = GradableReport(query="q", narrative_markdown="some report body")
    panel = FakePanel(aggregate=3)
    out = score_quality(report, "q", panel, seed=3)
    assert out["aggregate"] == 3
    assert len(panel.prompts) == 1
    assert "quality" in panel.prompts[0].lower()


def test_rubric_builders_produce_1_to_5_prompts():
    report = GradableReport(query="q", narrative_markdown="body")
    rp = relevance_rubric(report, "q")
    qp = quality_rubric(report, "q")
    for p in (rp, qp):
        assert "1" in p and "5" in p
        assert "justification" in p.lower()
