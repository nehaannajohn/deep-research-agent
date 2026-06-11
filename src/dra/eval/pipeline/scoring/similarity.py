"""Similarity-to-reference — claim-entailment overlap (spec §4, D1, D5).

The retained entailment-match fn used for the Fable reference comparison:
what fraction of the *reference* report's claims are entailed by some claim in
our report. The entailment predicate is injected (a fake in tests; an NLI /
judge model live), keeping this pure and offline.
"""
from __future__ import annotations

from typing import Callable

from dra.eval.pipeline.contracts import GradableReport

# entail_fn(hypothesis_claim_text, premise_claim_texts) -> bool
EntailFn = Callable[[str, list[str]], bool]


def score_similarity(
    report: GradableReport,
    reference_report: GradableReport,
    entail_fn: EntailFn,
) -> dict:
    """Fraction of reference claims entailed by some claim in ``report``.

    Returns ``{covered, total_reference, similarity, missing}`` where
    ``missing`` lists the reference claim texts no report claim entailed.
    """
    premise_texts = [c.text for c in report.claims]
    reference_texts = [c.text for c in reference_report.claims]

    covered = 0
    missing: list[str] = []
    for ref_text in reference_texts:
        if entail_fn(ref_text, premise_texts):
            covered += 1
        else:
            missing.append(ref_text)

    total = len(reference_texts)
    similarity = covered / total if total else None
    return {
        "covered": covered,
        "total_reference": total,
        "similarity": similarity,
        "missing": missing,
    }
