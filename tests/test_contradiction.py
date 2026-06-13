from dra.schemas import Claim
from dra.contradiction import (candidate_pairs, PairContradictionJudge,
                               ContradictionRecord, detect_and_resolve)


def _c(cid, text, section="s"):
    return Claim(id=cid, text=text, section=section)


def test_candidate_pairs_same_section_paired_unrelated_excluded():
    claims = [
        _c("c0", "Latency improved by thirty percent overall", "perf"),
        _c("c1", "Latency was essentially unchanged overall", "perf"),   # same section -> paired
        _c("c2", "The capital of France is Paris", "geo"),               # unrelated section+words
    ]
    pairs = candidate_pairs(claims)
    ids = {(a.id, b.id) for a, b in pairs}
    assert ("c0", "c1") in ids
    assert ("c0", "c2") not in ids and ("c1", "c2") not in ids


class SeqLLM:
    def __init__(self, payloads):
        self.payloads = list(payloads)
    def complete_json(self, prompt, **kw):
        return self.payloads.pop(0)


def test_judge_self_consistency_modal_and_confidence():
    llm = SeqLLM([{"relation": "contradict"}, {"relation": "contradict"}, {"relation": "agree"}])
    rel, conf = PairContradictionJudge(llm, n_samples=3).judge("a", "b")
    assert rel == "contradict"
    assert conf == 2 / 3


def test_judge_bad_output_coerced_to_independent():
    llm = SeqLLM([{"relation": "weird"}])
    rel, conf = PairContradictionJudge(llm, n_samples=1).judge("a", "b")
    assert rel == "independent"


def test_flag_policy_marks_both_claims_contested():
    claims = [_c("c0", "Latency improved thirty percent overall", "perf"),
              _c("c1", "Latency was unchanged overall always", "perf")]

    class Judge:
        def judge(self, a, b):
            return "contradict", 0.9

    out, records = detect_and_resolve(claims, Judge(), policy="flag")
    assert {c.verdict for c in out} == {"contested"}      # both flagged, neither dropped
    assert len(out) == 2 and len(records) == 1
    assert records[0].action == "flagged"


def test_detect_noop_when_judge_none():
    claims = [_c("c0", "x"), _c("c1", "y")]
    out_claims, records = detect_and_resolve(claims, None)
    assert out_claims == claims and records == []


def test_agree_relation_is_not_flagged():
    """Paraphrases / consistent claims judged 'agree' must NOT be marked contested
    (the over-flagging fix)."""
    claims = [_c("c0", "Transfer learning reuses a model trained on one task", "s"),
              _c("c1", "Transfer learning leverages previously learned knowledge", "s")]

    class AgreeJudge:
        def judge(self, a, b):
            return "agree", 1.0

    out, records = detect_and_resolve(claims, AgreeJudge(), policy="flag")
    assert records == []
    assert all(c.verdict != "contested" for c in out)


def test_default_threshold_rejects_low_confidence_contradiction():
    """The raised default threshold (0.67) must reject a weak 0.6-confidence contradict."""
    claims = [_c("c0", "Latency improved thirty percent", "perf"),
              _c("c1", "Latency was unchanged overall", "perf")]

    class WeakJudge:
        def judge(self, a, b):
            return "contradict", 0.6

    out, records = detect_and_resolve(claims, WeakJudge(), policy="flag")
    assert records == []
    assert all(c.verdict != "contested" for c in out)
