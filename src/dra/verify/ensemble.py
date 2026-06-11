"""Ensemble verifier: run N member verifiers, majority-vote the label, and use
inter-member agreement as the (raw) confidence. No majority (all members differ)
-> insufficient, since verifier disagreement is not source `contested`."""
from __future__ import annotations

from collections import Counter

from dra.schemas import Passage
from dra.verify.base import Verifier, VerifierResult


class EnsembleVerifier(Verifier):
    def __init__(self, members: list[Verifier]):
        if not members:
            raise ValueError("EnsembleVerifier needs at least one member")
        self.members = members

    def verify(self, claim: str, passages: list[Passage]) -> VerifierResult:
        results = [m.verify(claim, passages) for m in self.members]
        labels = [r.label for r in results]
        tally = Counter(labels)
        modal, count = tally.most_common(1)[0]
        n = len(self.members)
        # No consensus = the modal label appears once AND there are >1 members (every member
        # differed). A single-member ensemble is unanimous, not no-consensus. (2-2 even ties
        # don't reach this branch — out of scope for the 3-member design.)
        if count == 1 and n > 1:
            return VerifierResult(
                label="insufficient",
                confidence=1 / n,
                reasoning="verifiers disagreed: " + ", ".join(labels),
                recommendation="gather_more",
                votes=dict(tally),
            )
        rep = next(r for r in results if r.label == modal)
        return VerifierResult(
            label=modal,
            confidence=count / n,
            reasoning=rep.reasoning,
            recommendation=rep.recommendation,
            votes=dict(tally),
        )
