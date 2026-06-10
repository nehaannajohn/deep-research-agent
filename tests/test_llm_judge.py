from dra.verify.llm_judge import LLMJudgeVerifier


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, prompt):
        return self.payload


def test_supported_verdict():
    v = LLMJudgeVerifier(FakeLLM({"label": "supported", "confidence": 0.9})).verify("c", "e")
    assert v.label == "supported" and v.confidence == 0.9


def test_bad_label_and_confidence_are_sanitized():
    v = LLMJudgeVerifier(FakeLLM({"label": "weird", "confidence": 2})).verify("c", "e")
    assert v.label == "insufficient"  # unknown label -> insufficient
    assert v.confidence == 1.0  # clamped to [0,1]
