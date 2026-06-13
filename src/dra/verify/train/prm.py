"""PRM fitness gates (design §1.6), pure scoring given precomputed p_supported.

monotonicity_ladder: for each claim, p_supported across rungs
{none, distractor, partial, full} should be non-decreasing. Pass = >=90% of
claims monotonic AND mean per-rung delta > 0.
insensitivity_check: padding/duplicating/reordering irrelevant evidence must not
raise p_supported. Pass = mean |p_padded - p_clean| < eps.
"""
from __future__ import annotations


def monotonicity_ladder(rows: list[list[float]], min_frac: float = 0.90) -> dict:
    """rows[i] = ascending-rung p_supported for claim i (len>=2)."""
    if not rows:
        return {"frac_monotonic": 0.0, "mean_delta": 0.0, "pass": False, "n": 0}
    mono = 0
    deltas = []
    for r in rows:
        if all(r[j + 1] >= r[j] - 1e-9 for j in range(len(r) - 1)):
            mono += 1
        deltas.append((r[-1] - r[0]) / max(1, len(r) - 1))
    frac = mono / len(rows)
    mean_delta = sum(deltas) / len(deltas)
    return {"frac_monotonic": frac, "mean_delta": mean_delta,
            "pass": frac >= min_frac and mean_delta > 0, "n": len(rows)}


def insensitivity_check(pairs: list[tuple], eps: float = 0.05) -> dict:
    """pairs[i] = (p_clean, p_padded). Pass = mean |delta| < eps."""
    if not pairs:
        return {"mean_abs_delta": 0.0, "pass": True, "n": 0}
    deltas = [abs(pp - pc) for pc, pp in pairs]
    mad = sum(deltas) / len(deltas)
    return {"mean_abs_delta": mad, "pass": mad < eps, "n": len(pairs)}
