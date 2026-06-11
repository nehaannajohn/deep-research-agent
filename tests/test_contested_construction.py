"""Contested-set construction tests (fakes only, no network).

Covers the §3 construction contract: synthesize a refuting E' for a held-out
supported (C, E) pair, gate it through an injected verifier, and bundle both
evidences into a SINGLE holistic contested EvalExample.
"""
from dra.eval.base import EvalExample
from dra.eval.loaders.contested import (
    build_contested_example,
    build_contested_set,
    is_valid_contested,
    load_prior_contested_cases,
    synthesize_refuting_evidence,
)
from dra.schemas import Passage
from dra.verify.base import VerifierResult


# ----- fakes -------------------------------------------------------------

class FakeLLM:
    """complete(prompt) -> canned refuting text."""

    REFUTE_TEXT = "Studies show the opposite: the claim does not hold."

    def __init__(self):
        self.calls = []

    def complete(self, prompt, **kw):
        self.calls.append(prompt)
        return self.REFUTE_TEXT


class FakeVerifier:
    """Returns supported unless a passage contains the canned refuting text,
    in which case it returns refuted (mirrors a real construction gate)."""

    def verify(self, claim, passages):
        text = " ".join(p.text for p in passages)
        label = "refuted" if FakeLLM.REFUTE_TEXT in text else "supported"
        return VerifierResult(label=label, confidence=0.9)


class AlwaysSupportedVerifier:
    def verify(self, claim, passages):
        return VerifierResult(label="supported", confidence=0.9)


def _support(i=0):
    return Passage(source_id=f"E{i}", text="Evidence supporting the claim.", title="Doc")


# ----- build_contested_example -------------------------------------------

def test_build_contested_example_order_and_meta():
    support = Passage(source_id="E", text="supports", title="T")
    refute = Passage(source_id="E::refute", text="refutes", title="T")
    ex = build_contested_example("C", support, refute, example_id="contested:1")
    assert isinstance(ex, EvalExample)
    assert ex.passages == [support, refute]  # order [support, refute]
    assert ex.gold_label == "contested"
    assert ex.split == "test"
    assert ex.meta["dataset"] == "contested"
    assert ex.meta["construction"] == "synthetic"
    assert ex.meta["support_id"] == "E"
    assert ex.meta["refute_id"] == "E::refute"


# ----- is_valid_contested ------------------------------------------------

def test_is_valid_contested_true_when_split():
    support = _support()
    refute = Passage(source_id="E::refute", text=FakeLLM.REFUTE_TEXT, title="Doc")
    assert is_valid_contested("C", support, refute, FakeVerifier()) is True


def test_is_valid_contested_false_when_both_supported():
    support = _support()
    refute = Passage(source_id="E::refute", text=FakeLLM.REFUTE_TEXT, title="Doc")
    # AlwaysSupportedVerifier never returns refuted -> gate must reject.
    assert is_valid_contested("C", support, refute, AlwaysSupportedVerifier()) is False


# ----- synthesize_refuting_evidence --------------------------------------

def test_synthesize_refuting_evidence_wraps_passage():
    support = _support(7)
    llm = FakeLLM()
    refute = synthesize_refuting_evidence("C", support, llm)
    assert isinstance(refute, Passage)
    assert refute.text == FakeLLM.REFUTE_TEXT
    assert refute.source_id == "E7::refute"
    assert refute.title == support.title
    assert llm.calls  # the llm was prompted


# ----- build_contested_set -----------------------------------------------

def _supported_example(i):
    return EvalExample(
        example_id=f"sup:{i}",
        claim=f"Claim {i}",
        passages=[_support(i)],
        gold_label="supported",
    )


def test_build_contested_set_emits_only_gated_passes():
    supported = [_supported_example(i) for i in range(3)]
    out = build_contested_set(supported, FakeLLM(), FakeVerifier())
    # FakeVerifier gives supported for [E] and refuted for [E'] -> all pass.
    assert len(out) == 3
    assert all(ex.gold_label == "contested" for ex in out)
    assert all(ex.passages[1].text == FakeLLM.REFUTE_TEXT for ex in out)
    assert all(ex.meta["construction"] == "synthetic" for ex in out)


def test_build_contested_set_rejects_failing_gate():
    supported = [_supported_example(i) for i in range(2)]
    # AlwaysSupportedVerifier never returns refuted -> nothing passes the gate.
    out = build_contested_set(supported, FakeLLM(), AlwaysSupportedVerifier())
    assert out == []


def test_build_contested_set_respects_n_cap():
    supported = [_supported_example(i) for i in range(5)]
    out = build_contested_set(supported, FakeLLM(), FakeVerifier(), n=2)
    assert len(out) == 2


# ----- load_prior_contested_cases ----------------------------------------

def test_load_prior_contested_cases_parses_bench_shape(tmp_path):
    import json

    bench = [
        {"case": "tc1", "intended": "contested", "panel_labels": ["contested"],
         "claim": "A contested claim."},
        {"case": "tc2", "intended": "supported", "panel_labels": ["supported"],
         "claim": "Not contested."},
        {"case": "tc3", "intended": "contested", "panel_labels": ["contested"],
         "claim": "Another contested claim."},
    ]
    p = tmp_path / "bench.json"
    p.write_text(json.dumps(bench))
    out = load_prior_contested_cases(str(p))
    assert len(out) == 2  # only intended==contested
    assert all(ex.gold_label == "contested" for ex in out)
    assert all(ex.meta["construction"] == "panel_validated" for ex in out)
    assert all(ex.meta["dataset"] == "contested" for ex in out)
    assert {ex.claim for ex in out} == {"A contested claim.", "Another contested claim."}
