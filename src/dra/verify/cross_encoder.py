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
  - confidence = the calibrated probability OF THE PREDICTED LABEL (not always
    p_supported): supported->max p_supported, refuted->max p_refuted,
    insufficient->max p_nei, contested->min(max p_supported, max p_refuted) (high
    only when BOTH sides are strongly evidenced). Each label is calibrated by its
    own one-vs-rest calibrator (`calibrators[label]`); raw if none is provided.
    This makes "low confidence" mean "the verifier is unsure of the label it
    predicted" — the trigger the adaptive loop gates on.
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
    def __init__(self, *, score_fn: ScoreFn, calibrator=None, calibrators=None,
                 margin: float = 0.5):
        self.score_fn = score_fn
        # Per-label calibrators keyed by predicted label. Legacy single
        # `calibrator` is a supported-vs-rest detector, so it maps to {"supported": .}.
        self.calibrators = dict(calibrators) if calibrators else (
            {"supported": calibrator} if calibrator is not None else {})
        self.margin = margin

    def aggregate(self, claim: str, texts: list[str]):
        """Per-passage ARGMAX voting -> claim label + the per-class max probs.

        A passage votes `supported`/`refuted` only when that class is its *argmax*
        AND clears the margin. This stops the multi-cite over-flip: on a well-
        supported claim with many citations, a stray passage that scores
        refuted>=margin while supported is still its argmax does NOT count as a
        refuting vote, so the claim stays `supported` rather than flipping to
        `contested`. Genuine two-sided disagreement (a passage that truly argmaxes
        refuted) still yields `contested`. Shared by verify() and calibrator fitting
        so both see one source of truth for the label and the per-class maxes.
        """
        sup_votes = ref_votes = 0
        max_sup = max_ref = max_nei = 0.0
        for t in texts:
            s = self.score_fn(claim, t)
            ps, pr, pn = s.get("supported", 0.0), s.get("refuted", 0.0), s.get("nei", 0.0)
            max_sup, max_ref, max_nei = max(max_sup, ps), max(max_ref, pr), max(max_nei, pn)
            # argmax; exact ties resolve by dict order (supported > refuted > nei).
            # A support-leaning (even ~50/50) passage deliberately casts NO refuted
            # vote — that is precisely what prevents the multi-cite over-flip.
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
        return label, sup_votes, ref_votes, max_sup, max_ref, max_nei

    def raw_label_confidence(self, label, max_sup, max_ref, max_nei) -> float:
        """The pre-calibration confidence OF the predicted label."""
        return {
            "supported": max_sup,
            "refuted": max_ref,
            "insufficient": max_nei,
            "contested": min(max_sup, max_ref),
        }[label]

    def verify(self, claim: str, passages: list[Passage]) -> VerifierResult:
        texts = [p.text for p in passages if (p.text or "").strip()]
        if not texts:
            return VerifierResult(label="insufficient", confidence=0.0,
                                  recommendation="gather_more")

        label, sup_votes, ref_votes, max_sup, max_ref, max_nei = self.aggregate(claim, texts)
        raw = self.raw_label_confidence(label, max_sup, max_ref, max_nei)
        cal = self.calibrators.get(label)
        conf = cal.apply(raw) if cal is not None else raw
        return VerifierResult(label=label, confidence=float(conf),
                              recommendation=_REC[label],
                              votes={"max_supported": int(round(max_sup * 100)),
                                     "max_refuted": int(round(max_ref * 100)),
                                     "max_nei": int(round(max_nei * 100)),
                                     "sup_votes": sup_votes, "ref_votes": ref_votes})
