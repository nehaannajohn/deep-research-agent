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


def test_multicite_supported_not_overflipped_to_contested():
    # 4 strongly-supporting passages + 1 where refuted>=margin but supported is
    # STILL its argmax. Old max-aggregation flipped this to contested; argmax
    # voting keeps it supported (the stray passage casts no refuted vote).
    scores = {f"sup{i}": {"supported": 0.95, "refuted": 0.02, "nei": 0.03} for i in range(4)}
    scores["stray"] = {"supported": 0.55, "refuted": 0.52, "nei": 0.0}  # argmax=supported
    v = _verifier(scores)
    passages = [Passage(source_id=str(i), text=t) for i, t in enumerate(scores)]
    r = v.verify("c", passages)
    assert r.label == "supported"
    assert r.votes["ref_votes"] == 0


def test_genuine_two_sided_disagreement_still_contested():
    # one passage truly argmaxes supported, another truly argmaxes refuted
    v = _verifier({
        "a": {"supported": 0.92, "refuted": 0.03, "nei": 0.05},
        "b": {"supported": 0.05, "refuted": 0.90, "nei": 0.05},
    })
    r = v.verify("c", [Passage(source_id="0", text="a"), Passage(source_id="1", text="b")])
    assert r.label == "contested"


def test_passage_below_margin_casts_no_vote():
    # nothing clears the margin on its argmax -> insufficient
    v = _verifier({"x": {"supported": 0.45, "refuted": 0.40, "nei": 0.15}})
    r = v.verify("c", [Passage(source_id="0", text="x")])
    assert r.label == "insufficient"


def test_multicite_refuted_not_overflipped_to_contested():
    # symmetric to the supported over-flip: many refuting passages + one stray
    # supported>=margin where refuted is still argmax -> stays refuted.
    scores = {f"ref{i}": {"supported": 0.02, "refuted": 0.95, "nei": 0.03} for i in range(4)}
    scores["stray"] = {"supported": 0.52, "refuted": 0.55, "nei": 0.0}  # argmax=refuted
    v = _verifier(scores)
    passages = [Passage(source_id=str(i), text=t) for i, t in enumerate(scores)]
    r = v.verify("c", passages)
    assert r.label == "refuted"
    assert r.votes["sup_votes"] == 0


def test_all_nei_is_insufficient():
    v = _verifier({
        "a": {"supported": 0.2, "refuted": 0.1, "nei": 0.7},
        "b": {"supported": 0.3, "refuted": 0.2, "nei": 0.5},
    })
    r = v.verify("c", [Passage(source_id="0", text="a"), Passage(source_id="1", text="b")])
    assert r.label == "insufficient"


def test_confidence_pinned_to_support_prob_even_when_refuted():
    # contract: confidence is max p_supported across passages, regardless of label
    v = _verifier({"x": {"supported": 0.18, "refuted": 0.80, "nei": 0.02}})
    r = v.verify("c", [Passage(source_id="0", text="x")])
    assert r.label == "refuted"
    assert abs(r.confidence - 0.18) < 1e-9
