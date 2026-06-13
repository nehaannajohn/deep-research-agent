"""Verifier B inference: a trained cross-encoder behind the `Verifier` ABC.

`score_fn(claim, passage_text) -> {"supported":p,"refuted":p,"nei":p}` is injected
(the torch model wrapper lives in experiments/verifier_b/evaluate.py and binds a
real score_fn; tests inject a fake). Aggregation:
  - per-passage 3-way probs; claim verdict by MAX-aggregation:
      supported if max p_supported >= margin and no p_refuted >= margin
      refuted   symmetric
      contested if BOTH a supporting and a refuting passage exceed margin
      else insufficient (nei)
  - confidence = max p_supported across passages, Platt-calibrated if a calibrator
    is provided.
"""
from __future__ import annotations

from typing import Callable, Optional

from dra.schemas import Passage
from dra.verify.base import Recommendation, Verifier, VerifierResult

ScoreFn = Callable[[str, str], dict]

_REC: dict[str, Recommendation] = {
    "supported": "accept", "refuted": "revise",
    "insufficient": "gather_more", "contested": "flag_contested",
}


class CrossEncoderVerifier(Verifier):
    def __init__(self, *, score_fn: ScoreFn, calibrator=None, margin: float = 0.5):
        self.score_fn = score_fn
        self.calibrator = calibrator
        self.margin = margin

    def verify(self, claim: str, passages: list[Passage]) -> VerifierResult:
        texts = [p.text for p in passages if (p.text or "").strip()]
        if not texts:
            return VerifierResult(label="insufficient", confidence=0.0,
                                  recommendation="gather_more")

        max_sup = max_ref = 0.0
        for t in texts:
            s = self.score_fn(claim, t)
            max_sup = max(max_sup, s.get("supported", 0.0))
            max_ref = max(max_ref, s.get("refuted", 0.0))

        sup_hit = max_sup >= self.margin
        ref_hit = max_ref >= self.margin
        if sup_hit and ref_hit:
            label = "contested"
        elif sup_hit:
            label = "supported"
        elif ref_hit:
            label = "refuted"
        else:
            label = "insufficient"

        conf = self.calibrator.apply(max_sup) if self.calibrator else max_sup
        return VerifierResult(label=label, confidence=float(conf),
                              recommendation=_REC[label],
                              votes={"max_supported": int(round(max_sup * 100)),
                                     "max_refuted": int(round(max_ref * 100))})
