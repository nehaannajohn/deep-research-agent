"""Phase 1 — Layer-2 pipeline-eval scoring primitives (pure, fake-tested).

No live network. Every model dependency (grounding judge, entailment fn,
equivalence judge) is injected as a fake with canned, closed-form behaviour so
each metric can be asserted exactly.
"""
from __future__ import annotations

from dra.schemas import Citation, Passage

from dra.eval.pipeline.contracts import GradableClaim, GradableReport
from dra.eval.pipeline.scoring import (
    score_formatting,
    score_grounding,
    score_similarity,
    score_task_accuracy,
    system_ece,
)


# --------------------------------------------------------------------------- #
# grounding
# --------------------------------------------------------------------------- #
class FakeJudge:
    """Independent grounding judge: returns a canned verdict per claim text.

    Records every call so the test can confirm it (NOT the in-loop verifier)
    drove the score.
    """

    def __init__(self, verdicts: dict):
        self.verdicts = verdicts
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def verdict(self, claim_text: str, passages: list[Passage]) -> str:
        self.calls.append((claim_text, tuple(p.source_id for p in passages)))
        return self.verdicts[claim_text]


def _grounding_report() -> GradableReport:
    sources = [
        Passage(source_id="s1", text="Paris is the capital of France."),
        Passage(source_id="s2", text="The Seine flows through Paris."),
        Passage(source_id="s3", text="Unrelated text about cats."),
    ]
    claims = [
        # supported, single good citation
        GradableClaim(id="c1", text="Paris is the capital of France.",
                      citations=[Citation(source_id="s1", span="capital")]),
        # cited but judge says insufficient -> hallucination
        GradableClaim(id="c2", text="Paris has 50 million residents.",
                      citations=[Citation(source_id="s3", span="cats")]),
        # uncited -> hallucination
        GradableClaim(id="c3", text="The Eiffel Tower is 2km tall.", citations=[]),
        # supported, two citations one of which the judge does not confirm
        GradableClaim(id="c4", text="The Seine flows through Paris.",
                      citations=[Citation(source_id="s2", span="Seine"),
                                 Citation(source_id="s3", span="cats")]),
    ]
    return GradableReport(query="Tell me about Paris", claims=claims, sources=sources)


def test_grounding_rates_and_citation_metrics_exact():
    report = _grounding_report()
    judge = FakeJudge({
        "Paris is the capital of France.": "supported",
        "Paris has 50 million residents.": "insufficient",
        "The Eiffel Tower is 2km tall.": "supported",  # uncited still counts as hallucination
        "The Seine flows through Paris.": "supported",
    })
    out = score_grounding(report, judge, reference_claims=["Paris is the capital of France.",
                                                           "Lyon is in France."])

    assert out["n_claims"] == 4
    # supported holistic verdict: c1, c3(uncited but judge supported), c4 -> 3/4
    assert out["grounding_rate"] == 3 / 4
    # hallucination = insufficient (c2) + uncited (c3) = 2/4
    assert out["hallucination_rate"] == 2 / 4
    # the independent judge, not a verifier, produced every verdict
    assert len(judge.calls) >= 4


def test_grounding_uncited_claim_counts_as_hallucination():
    report = _grounding_report()
    judge = FakeJudge({
        "Paris is the capital of France.": "supported",
        "Paris has 50 million residents.": "supported",
        "The Eiffel Tower is 2km tall.": "supported",
        "The Seine flows through Paris.": "supported",
    })
    out = score_grounding(report, judge)
    # all judged supported, but c3 is uncited -> still hallucination
    assert out["hallucination_rate"] == 1 / 4
    per = {c["id"]: c for c in out["per_claim"]}
    assert per["c3"]["uncited"] is True
    assert per["c3"]["hallucinated"] is True


def test_grounding_recall_none_without_reference():
    out = score_grounding(_grounding_report(),
                          FakeJudge({c.text: "supported" for c in _grounding_report().claims}))
    assert out["citation_recall"] is None


def test_grounding_recall_keyword_overlap():
    report = _grounding_report()
    judge = FakeJudge({c.text: "supported" for c in report.claims})
    out = score_grounding(report, judge,
                          reference_claims=["Paris is the capital of France.",
                                            "Penguins live in Antarctica."])
    # only the first reference claim is covered by the report's claims -> 1/2
    assert out["citation_recall"] == 1 / 2


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #
def test_formatting_checklist_pass_fail_and_skip():
    md = (
        "# Report on transformers and attention\n\n"
        "Here is a diagram:\n\n"
        "```mermaid\ngraph TD; A-->B;\n```\n\n"
        "| Model | Year |\n| --- | --- |\n| BERT | 2018 |\n\n"
        "This report discusses transformers in depth."
    )
    report = GradableReport(query="q", narrative_markdown=md)
    constraints = {
        "wants_visual": True,             # mermaid present -> ok
        "format": "table",                # table present -> ok
        "max_words": 5,                   # body has > 5 words -> fail
        "focus_topics": ["transformers", "quantum"],  # transformers yes, quantum no -> fail
        "tone": "academic",              # fuzzy/unknown -> skip (applicable False)
    }
    out = score_formatting(report, constraints)

    per = {c["name"]: c for c in out["per_constraint"]}
    assert per["wants_visual"]["ok"] is True
    assert per["format"]["ok"] is True
    assert per["max_words"]["ok"] is False
    assert per["focus_topics"]["ok"] is False
    # fuzzy constraint skipped, not counted
    assert per["tone"]["applicable"] is False
    assert out["applicable"] == 4
    assert out["satisfied"] == 2
    assert out["pass_rate"] == 2 / 4


def test_formatting_no_applicable_constraints():
    report = GradableReport(query="q", narrative_markdown="hello")
    out = score_formatting(report, {"tone": "playful"})
    assert out["applicable"] == 0
    assert out["pass_rate"] is None


# --------------------------------------------------------------------------- #
# similarity
# --------------------------------------------------------------------------- #
def test_similarity_entailment_overlap_exact():
    report = GradableReport(query="q", claims=[
        GradableClaim(id="a", text="Transformers use self-attention."),
        GradableClaim(id="b", text="BERT is bidirectional."),
    ])
    reference = GradableReport(query="q", claims=[
        GradableClaim(id="r1", text="Self-attention is core to transformers."),
        GradableClaim(id="r2", text="GPT is autoregressive."),
        GradableClaim(id="r3", text="BERT reads bidirectionally."),
    ])

    def fake_entail(hypothesis: str, premises: list[str]) -> bool:
        # r1 entailed by the attention claim, r3 by the BERT claim, r2 by neither
        mapping = {
            "Self-attention is core to transformers.": True,
            "GPT is autoregressive.": False,
            "BERT reads bidirectionally.": True,
        }
        return mapping[hypothesis]

    out = score_similarity(report, reference, fake_entail)
    assert out["total_reference"] == 3
    assert out["covered"] == 2
    assert out["similarity"] == 2 / 3
    assert out["missing"] == ["GPT is autoregressive."]


# --------------------------------------------------------------------------- #
# task accuracy
# --------------------------------------------------------------------------- #
def test_task_accuracy_exact_match():
    out = score_task_accuracy("Paris", "paris")
    assert out == {"correct": True, "abstained": False, "method": "em"}


def test_task_accuracy_alias_hit():
    out = score_task_accuracy("USA", "United States", aliases=["U.S.", "USA"])
    assert out["correct"] is True
    assert out["method"] == "alias"


def test_task_accuracy_judge_near_miss():
    class FakeEquiv:
        def equivalent(self, a: str, b: str) -> bool:
            return True

    out = score_task_accuracy("four", "4", equivalence_judge=FakeEquiv())
    assert out["correct"] is True
    assert out["method"] == "judge"


def test_task_accuracy_judge_says_no():
    class FakeEquiv:
        def equivalent(self, a: str, b: str) -> bool:
            return False

    out = score_task_accuracy("dogs", "cats", equivalence_judge=FakeEquiv())
    assert out["correct"] is False
    assert out["method"] == "judge"


def test_task_accuracy_abstention_insufficient():
    out = score_task_accuracy("INSUFFICIENT", "Paris")
    assert out == {"correct": None, "abstained": True, "method": "abstain"}


def test_task_accuracy_abstention_none():
    out = score_task_accuracy(None, "Paris")
    assert out["abstained"] is True
    assert out["correct"] is None


# --------------------------------------------------------------------------- #
# calibration (system ECE)
# --------------------------------------------------------------------------- #
class _GoldClaim:
    """A claim carrying its gold verdict for calibration scoring."""

    def __init__(self, verdict, confidence, gold_verdict):
        self.verdict = verdict
        self.confidence = confidence
        self.gold_verdict = gold_verdict


def test_system_ece_matches_layer1_ece():
    from dra.eval.calibrate import ece as layer1_ece

    # build claims: outcome = 1 iff verdict == gold_verdict
    claims = [
        _GoldClaim("supported", 0.9, "supported"),
        _GoldClaim("supported", 0.8, "refuted"),
        _GoldClaim("refuted", 0.6, "refuted"),
        _GoldClaim("supported", 0.3, "refuted"),
    ]

    out = system_ece(claims, bins=15)
    probs = [0.9, 0.8, 0.6, 0.3]
    outcomes = [1, 0, 1, 0]
    assert out["n"] == 4
    assert abs(out["ece"] - layer1_ece(probs, outcomes, bins=15)) < 1e-12


def test_system_ece_empty():
    out = system_ece([])
    assert out == {"ece": 0.0, "n": 0}
