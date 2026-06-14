"""Verifier B inference: a trained cross-encoder behind the `Verifier` ABC.

`score_fn(claim, passage_text) -> {"supported":p,"refuted":p,"nei":p}` is injected
(the torch model wrapper lives in experiments/verifier_b/evaluate.py and binds a
real score_fn; tests inject a fake). Aggregation:
  - per-passage 3-way probs; claim verdict by per-passage ARGMAX VOTING:
      each passage votes its argmax class iff that class clears `margin`;
      supported if ≥1 supported-vote and no refuted-vote
      refuted   symmetric
      contested if BOTH a supported-vote and a refuted-vote exist
      else insufficient (nei)
    (argmax voting, not independent max-aggregation, so a stray refuted>=margin
     passage on a well-supported multi-cite claim no longer over-flips contested)
  - confidence = max p_supported across passages, Platt-calibrated if a calibrator
    is provided.
"""
from __future__ import annotations

from typing import Callable

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

        # Per-passage ARGMAX voting (not independent max-aggregation). A passage
        # votes `supported`/`refuted` only when that class is its *argmax* AND
        # clears the margin. This stops the multi-cite over-flip: on a well-
        # supported claim with many citations, a stray passage that scores
        # refuted>=margin while supported is still its argmax does NOT count as a
        # refuting vote, so the claim stays `supported` rather than flipping to
        # `contested`. Genuine two-sided disagreement (a passage that truly
        # argmaxes refuted) still yields `contested`.
        sup_votes = ref_votes = 0
        max_sup = max_ref = 0.0
        for t in texts:
            s = self.score_fn(claim, t)
            ps, pr = s.get("supported", 0.0), s.get("refuted", 0.0)
            max_sup, max_ref = max(max_sup, ps), max(max_ref, pr)
            top = max(s, key=s.get)
            if top == "supported" and ps >= self.margin:
                sup_votes += 1
            elif top == "refuted" and pr >= self.margin:
                ref_votes += 1

        if sup_votes and ref_votes:
            label = "contested"
        elif sup_votes:
            label = "supported"
        elif ref_votes:
            label = "refuted"
        else:
            label = "insufficient"

        conf = self.calibrator.apply(max_sup) if self.calibrator else max_sup
        return VerifierResult(label=label, confidence=float(conf),
                              recommendation=_REC[label],
                              votes={"max_supported": int(round(max_sup * 100)),
                                     "max_refuted": int(round(max_ref * 100)),
                                     "sup_votes": sup_votes, "ref_votes": ref_votes})
