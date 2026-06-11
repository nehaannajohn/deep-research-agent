"""EnsembleVerifier — majority vote across member verifiers, agreement = confidence."""
import pytest

from dra.schemas import Passage
from dra.verify.base import Verifier, VerifierResult
from dra.verify.ensemble import EnsembleVerifier

P = [Passage(source_id="s1", text="e", url="u")]


class Const(Verifier):
    """A member that always returns a fixed result."""
    def __init__(self, label, rec="accept"):
        self.label, self.rec = label, rec

    def verify(self, claim, passages):
        return VerifierResult(label=self.label, confidence=1.0,
                              reasoning=f"{self.label} says so", recommendation=self.rec)


def test_majority_vote_and_agreement_confidence():
    e = EnsembleVerifier([Const("supported"), Const("supported"), Const("refuted")])
    r = e.verify("c", P)
    assert r.label == "supported"
    assert r.confidence == 2 / 3
    assert r.votes == {"supported": 2, "refuted": 1}
    assert r.reasoning == "supported says so"  # from a majority-side member


def test_unanimous_is_full_confidence():
    e = EnsembleVerifier([Const("contested", "flag_contested")] * 3)
    r = e.verify("c", P)
    assert r.label == "contested"
    assert r.confidence == 1.0
    assert r.recommendation == "flag_contested"


def test_no_majority_falls_back_to_insufficient():
    e = EnsembleVerifier([Const("supported"), Const("refuted"), Const("contested")])
    r = e.verify("c", P)
    assert r.label == "insufficient"
    assert r.confidence == 1 / 3
    assert r.recommendation == "gather_more"
    assert r.votes == {"supported": 1, "refuted": 1, "contested": 1}


def test_empty_members_raises():
    with pytest.raises(ValueError):
        EnsembleVerifier([])


def test_single_member_is_unanimous_not_no_consensus():
    # a 1-member ensemble must return that member's verdict, not fall into no-consensus
    e = EnsembleVerifier([Const("supported")])
    r = e.verify("c", P)
    assert r.label == "supported"
    assert r.confidence == 1.0
