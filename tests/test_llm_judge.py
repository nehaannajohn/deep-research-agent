"""Holistic self-consistent LLM-judge verifier — fake LLM, no live calls."""
from dra.schemas import Passage
from dra.verify.llm_judge import LLMJudgeVerifier


class SeqLLM:
    """Returns queued payloads in order, one per complete_json call."""
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def complete_json(self, prompt, **kw):
        self.calls += 1
        return self.payloads.pop(0)


P = [Passage(source_id="s1", text="evidence one", url="u1")]


def test_self_consistency_modal_label_and_confidence():
    llm = SeqLLM([
        {"label": "supported", "reasoning": "r", "recommendation": "accept"},
        {"label": "supported", "reasoning": "r", "recommendation": "accept"},
        {"label": "insufficient", "reasoning": "r", "recommendation": "gather_more"},
        {"label": "supported", "reasoning": "r", "recommendation": "accept"},
        {"label": "supported", "reasoning": "r", "recommendation": "accept"},
    ])
    r = LLMJudgeVerifier(llm, n_samples=5).verify("claim", P)
    assert r.label == "supported"
    assert r.confidence == 0.8
    assert r.recommendation == "accept"
    assert r.votes == {"supported": 4, "insufficient": 1}
    assert llm.calls == 5


def test_contested_is_a_valid_label():
    llm = SeqLLM([{"label": "contested", "reasoning": "split", "recommendation": "flag_contested"}])
    r = LLMJudgeVerifier(llm, n_samples=1).verify("claim", P)
    assert r.label == "contested"
    assert r.recommendation == "flag_contested"


def test_bad_label_and_recommendation_coerced():
    llm = SeqLLM([{"label": "weird", "reasoning": "r", "recommendation": "nonsense"}])
    r = LLMJudgeVerifier(llm, n_samples=1).verify("claim", P)
    assert r.label == "insufficient"
    assert r.recommendation == "gather_more"


def test_empty_passages_short_circuits_without_calling_llm():
    llm = SeqLLM([])  # would IndexError if called
    r = LLMJudgeVerifier(llm, n_samples=5).verify("claim", [])
    assert r.label == "insufficient"
    assert llm.calls == 0


def test_tie_breaks_on_first_seen_sample_order():
    # 1-1 split: modal = the label seen first; confidence = 0.5
    llm = SeqLLM([
        {"label": "refuted", "reasoning": "r", "recommendation": "revise"},
        {"label": "supported", "reasoning": "r", "recommendation": "accept"},
    ])
    r = LLMJudgeVerifier(llm, n_samples=2).verify("claim", P)
    assert r.label == "refuted"
    assert r.confidence == 0.5
    assert r.votes == {"refuted": 1, "supported": 1}
