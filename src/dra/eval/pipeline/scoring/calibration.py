"""System-level ECE on surfaced confidence (spec §4 cross-cutting metric).

Reuses the Layer-1 `dra.eval.calibrate.ece` verbatim — Layer 2 only *reports*
ECE on the already-recalibrated, surfaced confidence; it does not fit a
calibrator (that's owned by Layer-1 calibration).

Binary-collapse rule (auditable): each claim's surfaced ``confidence`` is read
as p(correct); the outcome is 1 iff ``verdict == gold_verdict`` and 0
otherwise. We then hand ``(probs, outcomes)`` to the reused `ece`.
"""
from __future__ import annotations

from dra.eval.calibrate import ece


def system_ece(claims, *, bins: int = 15) -> dict:
    """Compute system-level ECE from claims carrying (verdict, confidence, gold_verdict).

    Claims missing a ``confidence`` or a ``gold_verdict`` are skipped (an
    unverified / black-box claim has nothing to calibrate). Returns
    ``{ece, n}`` where ``n`` is the number of scored claims.
    """
    probs: list[float] = []
    outcomes: list[int] = []
    for c in claims:
        confidence = getattr(c, "confidence", None)
        gold = getattr(c, "gold_verdict", None)
        if confidence is None or gold is None:
            continue
        probs.append(confidence)
        # documented binary collapse: outcome 1 iff the surfaced verdict matches gold
        outcomes.append(1 if c.verdict == gold else 0)

    return {"ece": ece(probs, outcomes, bins=bins), "n": len(probs)}
