"""Holistic LLM-judge verifier: one claim vs ALL its cited passages.

Confidence is measured by self-consistency — sample the judge n_samples times
(temperature>0); confidence = fraction agreeing on the modal label. The judge
sees every passage at once, so it can label `contested` when support is split.
A different model family from the generator (model independence)."""
from __future__ import annotations

from collections import Counter

from dra.schemas import Passage
from dra.verify.base import Recommendation, Verifier, VerifierResult

_LABELS = ("supported", "refuted", "insufficient", "contested")
_RECS = ("accept", "gather_more", "reformulate", "revise", "flag_contested")

_PROMPT = """You judge whether a CLAIM is supported by its cited PASSAGES, considered together.

Labels:
- "supported": the passages (collectively) entail the claim
- "refuted": the passages contradict the claim
- "insufficient": the passages neither entail nor contradict it
- "contested": the passages are split — at least one supports AND at least one refutes the claim

Also give a short reasoning and a recommendation:
- "accept" (supported), "gather_more"/"reformulate" (insufficient), "revise" (refuted), "flag_contested" (contested)

Answer ONLY JSON: {{"label": "...", "reasoning": "...", "recommendation": "..."}}

CLAIM: {claim}

PASSAGES:
{passages}"""


def _coerce_label(v) -> str:
    return v if v in _LABELS else "insufficient"


def _coerce_rec(v) -> Recommendation:
    return v if v in _RECS else "gather_more"


class LLMJudgeVerifier(Verifier):
    def __init__(self, llm, n_samples: int = 5, temperature: float = 0.7):
        self.llm = llm
        self.n_samples = n_samples
        self.temperature = temperature

    def verify(self, claim: str, passages: list[Passage]) -> VerifierResult:
        if not passages:
            return VerifierResult(label="insufficient", confidence=1.0,
                                  reasoning="no cited passages", recommendation="gather_more")
        rendered = "\n".join(f"[{p.source_id}] {p.text}" for p in passages)
        prompt = _PROMPT.format(claim=claim, passages=rendered)
        raw = [self.llm.complete_json(prompt, temperature=self.temperature)
               for _ in range(self.n_samples)]
        samples = [s if isinstance(s, dict) else {} for s in raw]
        labels = [_coerce_label(s.get("label")) for s in samples]
        tally = Counter(labels)
        # ties break on first-seen sample order (Counter.most_common is a stable count sort);
        # confidence still reflects the split (e.g. 0.5), which the loop can act on.
        modal, count = tally.most_common(1)[0]
        rep = next(s for s, lab in zip(samples, labels) if lab == modal)
        return VerifierResult(
            label=modal,
            confidence=count / len(labels),
            reasoning=str(rep.get("reasoning", "")),
            recommendation=_coerce_rec(rep.get("recommendation")),
            votes=dict(tally),
        )
