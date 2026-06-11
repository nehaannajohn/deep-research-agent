"""Judge reliability — Cohen's κ + human-validation subset accounting (spec §7).

`cohen_kappa` reuses Layer-1's chance-corrected implementation from
`dra.eval.calibrate` (the shapes align: two equal-length label sequences) so the
two layers report the same κ. `human_validation_summary` reports the human↔panel
agreement rate and the validated `n` for the human-validation subset.
"""
from __future__ import annotations

# Reuse Layer-1's chance-corrected κ rather than reimplementing it.
from dra.eval.calibrate import cohen_kappa

__all__ = ["cohen_kappa", "human_validation_summary"]


def human_validation_summary(panel_labels, human_labels) -> dict:
    """Agreement between panel labels and human labels on the validated subset.

    Returns ``{"n": <validated count>, "agreement": <fraction matching>,
    "n_agree": <count matching>}``. ``agreement`` is the simple match rate (the
    κ between the two is available via :func:`cohen_kappa` when chance-correction
    is wanted; here we report the raw agreement the subset audit calls for).
    """
    n = len(panel_labels)
    if n != len(human_labels):
        raise ValueError("panel_labels and human_labels must be equal length")
    if n == 0:
        return {"n": 0, "agreement": 0.0, "n_agree": 0}
    n_agree = sum(1 for p, h in zip(panel_labels, human_labels) if p == h)
    return {"n": n, "agreement": n_agree / n, "n_agree": n_agree}
