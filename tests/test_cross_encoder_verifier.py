from __future__ import annotations

from dra.schemas import Passage
from dra.verify.cross_encoder import CrossEncoderVerifier


def _verifier(scores_by_text, calibrator=None, margin=0.5):
    def score_fn(claim, passage):
        return scores_by_text[passage]
    return CrossEncoderVerifier(score_fn=score_fn, calibrator=calibrator, margin=margin)


def test_max_aggregation_supported_when_one_strong_passage():
    v = _verifier({
        "weak": {"supported": 0.2, "refuted": 0.1, "nei": 0.7},
        "strong": {"supported": 0.9, "refuted": 0.05, "nei": 0.05},
    })
    r = v.verify("c", [Passage(source_id="s0", text="weak"), Passage(source_id="s1", text="strong")])
    assert r.label == "supported"
    assert r.confidence >= 0.9


def test_candidate_contested_when_support_and_refute_both_present():
    v = _verifier({
        "a": {"supported": 0.8, "refuted": 0.1, "nei": 0.1},
        "b": {"supported": 0.1, "refuted": 0.85, "nei": 0.05},
    })
    r = v.verify("c", [Passage(source_id="s0", text="a"), Passage(source_id="s1", text="b")])
    assert r.label == "contested"
    assert r.recommendation == "flag_contested"


def test_no_passages_is_insufficient():
    v = _verifier({})
    r = v.verify("c", [])
    assert r.label == "insufficient" and r.confidence == 0.0


def test_calibrator_is_applied_to_confidence():
    class _Cal:
        def apply(self, p): return 0.5
    v = _verifier({"p": {"supported": 0.9, "refuted": 0.05, "nei": 0.05}}, calibrator=_Cal())
    r = v.verify("c", [Passage(source_id="s", text="p")])
    assert r.confidence == 0.5
