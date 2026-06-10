"""Variant A: prompted LLM-judge entailment verifier (a different model family
from the generator, per model-independence)."""
from __future__ import annotations

from dra.verify.base import Verdict, Verifier

_PROMPT = """Does the EVIDENCE support the CLAIM?
- 'supported': the evidence entails the claim
- 'refuted': the evidence contradicts the claim
- 'insufficient': the evidence neither entails nor contradicts it
Answer ONLY JSON: {{"label": "supported|refuted|insufficient", "confidence": 0.0-1.0}}

CLAIM: {claim}
EVIDENCE: {evidence}"""


class LLMJudgeVerifier(Verifier):
    def __init__(self, llm):
        self.llm = llm

    def verify(self, claim: str, evidence: str) -> Verdict:
        d = self.llm.complete_json(_PROMPT.format(claim=claim, evidence=evidence))
        label = d.get("label")
        if label not in ("supported", "refuted", "insufficient"):
            label = "insufficient"
        try:
            conf = max(0.0, min(1.0, float(d.get("confidence", 0.0))))
        except (TypeError, ValueError):
            conf = 0.0
        return Verdict(label=label, confidence=conf)
