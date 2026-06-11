"""Significance testing for Layer-2 comparisons (spec §7).

- ``paired_t`` — paired t-test for continuous metrics (rubric means, per-prompt
  grounding rate). Wraps ``scipy.stats.ttest_rel``.
- ``mcnemar`` — paired-binary outcomes (per-item correct/incorrect: task
  accuracy, expected-behavior match, formatting pass). Reduces to the discordant
  counts ``b`` (A right, B wrong) and ``c`` (A wrong, B right): **exact** binomial
  when ``b+c < 25``, else chi-square with continuity correction.
- ``holm`` — pure step-down Holm–Bonferroni across the family of comparisons.
- ``unit_of_analysis`` — documents the claim-level vs prompt-level split (spec §7:
  grounding is claim-level, N in the thousands; rubric axes are prompt-level).

Statistical tests use ``scipy.stats``; Holm is dependency-free and exact.
"""
from __future__ import annotations

from scipy.stats import binomtest, chi2, ttest_rel

__all__ = ["paired_t", "mcnemar", "holm", "unit_of_analysis", "MCNEMAR_EXACT_CUTOFF"]

# b+c strictly below this uses the exact binomial; at/above uses chi-square.
MCNEMAR_EXACT_CUTOFF = 25


def paired_t(a, b) -> dict:
    """Paired t-test on two equal-length continuous samples (``a`` vs ``b``).

    Returns ``{statistic, p_value, n, mean_diff}`` where ``mean_diff`` is the
    mean of ``a_i - b_i`` (positive => ``a`` higher). Unit of analysis is
    prompt-level for rubric means, claim-level when fed per-claim continuous
    metrics — the caller decides what each pair represents.
    """
    n = len(a)
    if n != len(b):
        raise ValueError("paired_t requires equal-length samples")
    if n < 2:
        raise ValueError("paired_t requires at least 2 pairs")
    res = ttest_rel(a, b)
    mean_diff = sum(x - y for x, y in zip(a, b)) / n
    return {
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": n,
        "mean_diff": mean_diff,
    }


def mcnemar(a_correct, b_correct) -> dict:
    """McNemar test on paired binary outcomes (1=correct, 0=incorrect).

    ``b`` = #(A right, B wrong), ``c`` = #(A wrong, B right) are the discordant
    cells. For ``b+c < MCNEMAR_EXACT_CUTOFF`` (25) we use the exact two-sided
    binomial ``binomtest(min(b,c), b+c, 0.5)``; otherwise the chi-square
    statistic ``((|b-c|-1)^2)/(b+c)`` with 1 df. Returns
    ``{b, c, statistic, p_value, method}`` where ``method`` records the path.
    """
    if len(a_correct) != len(b_correct):
        raise ValueError("mcnemar requires equal-length outcome arrays")
    b = sum(1 for x, y in zip(a_correct, b_correct) if x and not y)
    c = sum(1 for x, y in zip(a_correct, b_correct) if not x and y)
    n_disc = b + c

    if n_disc == 0:
        # No discordant pairs -> no evidence of difference.
        return {"b": b, "c": c, "statistic": 0.0, "p_value": 1.0, "method": "exact"}

    if n_disc < MCNEMAR_EXACT_CUTOFF:
        p = binomtest(min(b, c), n_disc, 0.5).pvalue
        # statistic reported as the smaller discordant count (the exact test
        # operates directly on it; no chi-square statistic in this path).
        return {
            "b": b,
            "c": c,
            "statistic": float(min(b, c)),
            "p_value": float(p),
            "method": "exact",
        }

    statistic = ((abs(b - c) - 1) ** 2) / n_disc
    p = float(chi2.sf(statistic, 1))
    return {
        "b": b,
        "c": c,
        "statistic": float(statistic),
        "p_value": p,
        "method": "chi2",
    }


def holm(pvals: dict, alpha: float = 0.05) -> dict:
    """Pure step-down Holm–Bonferroni correction over a family of p-values.

    Sorts ascending; tests the i-th smallest (0-indexed) against ``alpha/(m-i)``;
    once a hypothesis fails to clear its threshold, it and all larger p-values are
    not rejected (step-down stop). Adjusted p-values are ``p * (m-i)`` clamped to
    1.0 and made monotonically non-decreasing in p order. Returns
    ``{name: {p, p_adj, reject}}``.
    """
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out: dict = {}

    stopped = False
    prev_adj = 0.0
    for i, (name, p) in enumerate(items):
        threshold = alpha / (m - i)
        if not stopped and p <= threshold:
            reject = True
        else:
            reject = False
            stopped = True  # step-down: everything after this is not rejected
        p_adj = min(1.0, p * (m - i))
        # enforce monotonic non-decreasing adjusted p-values
        p_adj = max(p_adj, prev_adj)
        prev_adj = p_adj
        out[name] = {"p": p, "p_adj": p_adj, "reject": reject}
    return out


# Spec §7: deliberate unit-of-analysis split. Grounding is scored per atomic
# claim (N in the thousands); rubric axes are scored per prompt (~100 items).
_CLAIM_LEVEL = {"grounding", "citation_precision", "citation_recall", "hallucination"}


def unit_of_analysis(axis: str) -> str:
    """Return ``"claim-level"`` or ``"prompt-level"`` for a scoring axis (spec §7)."""
    return "claim-level" if axis in _CLAIM_LEVEL else "prompt-level"
