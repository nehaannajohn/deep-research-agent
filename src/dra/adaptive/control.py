"""Pure gate + termination logic for the adaptive-retrieval loop (claim-level).

No I/O, no models — just the decisions: which claims are weak enough to repair,
whether a repair beat the incumbent, and when to stop iterating a claim. The gate
is the claim's calibrated predicted-label confidence vs τ (design §2): low
confidence == the verifier is unsure of the label it assigned == worth
re-retrieving. A trigger probe set τ=0.7 (≈22% of DRA-Bench claims).
"""
from __future__ import annotations

DEFAULT_TAU = 0.7
DEFAULT_EPS = 0.05
DEFAULT_MAX_ITERS = 3


def needs_repair(confidence, tau: float = DEFAULT_TAU) -> bool:
    """A claim triggers repair when its calibrated label confidence is below τ.
    A missing confidence (None) is treated as weak — repair it."""
    return confidence is None or confidence < tau


def select_weak_claims(claims, tau: float = DEFAULT_TAU) -> list:
    """The below-τ claims (duck-typed on `.confidence`) — the repair set."""
    return [c for c in claims if needs_repair(getattr(c, "confidence", None), tau)]


def made_progress(old_conf, new_conf, eps: float = DEFAULT_EPS) -> bool:
    """A repair counts as progress only if it beats the incumbent by ≥ eps.
    A None new-confidence is no progress; improving from None is progress."""
    if new_conf is None:
        return False
    if old_conf is None:
        return True
    return (new_conf - old_conf) >= eps


def should_stop(iteration: int, confidence, tau: float = DEFAULT_TAU,
                progressed: bool = True, max_iters: int = DEFAULT_MAX_ITERS) -> bool:
    """Stop iterating a claim when it clears τ, makes no progress, or hits the cap.
    `iteration` is the 1-based count of the iteration just completed."""
    if confidence is not None and confidence >= tau:
        return True
    if iteration >= max_iters:
        return True
    return not progressed
