"""Grounding scorer — driven by an INDEPENDENT grounding judge, not the in-loop verifier.

Spec §4 ("Grounding detail"): the in-loop verifier already decided grounding
*online* (it drove adaptive retrieval and set the surfaced confidence), so
re-scoring grounding with that same model would measure the verifier's
self-consistency rather than whether the claims are actually grounded. We
therefore take an *injected* independent judge (panel family in live runs; a
fake in tests) and run it over each claim's cited passages.

The judge is the only model dependency and it is passed in, keeping this
function pure and offline-testable.
"""
from __future__ import annotations

from typing import Optional, Protocol

from dra.schemas import Passage

from dra.eval.pipeline.contracts import GradableReport


class GroundingJudge(Protocol):
    """The injected independent grounding judge (panel family, not the verifier)."""

    def verdict(self, claim_text: str, passages: list[Passage]) -> str:
        """Return a VerdictLabel for the claim against its cited passages."""
        ...


def _cited_passages(claim, sources: list[Passage]) -> list[Passage]:
    """Resolve a claim's citations to the report's passages by source_id."""
    by_id = {p.source_id: p for p in sources}
    seen: list[Passage] = []
    for cit in claim.citations:
        p = by_id.get(cit.source_id)
        if p is not None and p not in seen:
            seen.append(p)
    return seen


def _keyword_overlap(reference: str, claim_texts: list[str]) -> bool:
    """True if some report claim shares a meaningful keyword with the reference claim.

    Lightweight string/keyword overlap — a deeper entailment match lives in
    `similarity.py` (Phase G). Stopwords are dropped so trivial words don't
    spuriously match.
    """
    stop = {"the", "a", "an", "is", "are", "of", "in", "to", "and", "on",
            "for", "with", "as", "by", "at", "it", "its", "that", "this"}

    def kw(text: str) -> set[str]:
        return {t.strip(".,;:!?()").lower() for t in text.split()} - stop - {""}

    ref_kw = kw(reference)
    if not ref_kw:
        return False
    for ct in claim_texts:
        overlap = ref_kw & kw(ct)
        # require a majority of the reference keywords to be present
        if overlap and len(overlap) >= max(1, (len(ref_kw) + 1) // 2):
            return True
    return False


def score_grounding(
    report: GradableReport,
    judge: GroundingJudge,
    *,
    reference_claims: Optional[list[str]] = None,
) -> dict:
    """Score grounding / hallucination / citation precision-recall via `judge`.

    Returns a dict with ``grounding_rate``, ``hallucination_rate``,
    ``citation_precision``, ``citation_recall`` (``None`` when no
    ``reference_claims`` given), ``n_claims`` and ``per_claim`` detail.

    - ``grounding_rate`` = supported / n_claims.
    - ``hallucination_rate`` = (insufficient + uncited) / n_claims, where an
      uncited claim (no citations) is always a hallucination regardless of the
      holistic verdict.
    - ``citation_precision`` = fraction of all cited (claim, source) pairs the
      judge confirms support the claim. We reuse the holistic per-claim verdict
      (a claim judged ``supported`` confirms each of its cited sources) — kept
      simple and documented; a per-(claim, single-passage) judge call is a
      future refinement.
    - ``citation_recall`` = fraction of ``reference_claims`` covered by the
      report's claims via keyword overlap.
    """
    claims = report.claims
    n = len(claims)
    per_claim: list[dict] = []

    supported = 0
    hallucinated = 0
    cited_pairs = 0
    confirmed_pairs = 0

    for claim in claims:
        cited = _cited_passages(claim, report.sources)
        uncited = len(claim.citations) == 0
        verdict = judge.verdict(claim.text, cited)
        is_supported = verdict == "supported"
        # uncited always counts as hallucination; otherwise insufficient does
        is_hallucination = uncited or verdict == "insufficient"

        if is_supported:
            supported += 1
        if is_hallucination:
            hallucinated += 1

        # citation precision: each cited source counts; confirmed when the
        # holistic verdict is supported.
        n_cited = len(claim.citations)
        cited_pairs += n_cited
        if is_supported:
            confirmed_pairs += n_cited

        per_claim.append({
            "id": claim.id,
            "verdict": verdict,
            "uncited": uncited,
            "supported": is_supported,
            "hallucinated": is_hallucination,
            "n_citations": n_cited,
        })

    grounding_rate = supported / n if n else 0.0
    hallucination_rate = hallucinated / n if n else 0.0
    citation_precision = confirmed_pairs / cited_pairs if cited_pairs else None

    citation_recall: Optional[float]
    if reference_claims is None:
        citation_recall = None
    elif not reference_claims:
        citation_recall = None
    else:
        claim_texts = [c.text for c in claims]
        covered = sum(1 for r in reference_claims if _keyword_overlap(r, claim_texts))
        citation_recall = covered / len(reference_claims)

    return {
        "grounding_rate": grounding_rate,
        "hallucination_rate": hallucination_rate,
        "citation_precision": citation_precision,
        "citation_recall": citation_recall,
        "n_claims": n,
        "per_claim": per_claim,
    }
