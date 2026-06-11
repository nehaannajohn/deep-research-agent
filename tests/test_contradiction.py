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
