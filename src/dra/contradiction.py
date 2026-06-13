"""Contradiction-detection layer (Feature 2): detect claim<->claim contradictions
over a FILTERED set of claim pairs (not O(n^2) LLM calls), independent of the grounding
verifier, on verified OR unverified claims. B1 = detection only; the policy that acts on
detections is Phase B2. See docs/superpowers/specs/2026-06-11-report-composition-followups-design.md.
"""
from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from dra.schemas import Claim

_RELATIONS = ("contradict", "agree", "independent")
_STOP = {"the", "and", "for", "that", "with", "this", "from", "are", "was", "were",
         "has", "have", "had", "can", "may", "not", "but", "its", "their", "than",
         "into", "more", "less", "such", "which", "when", "what", "does"}


def _keywords(text: str) -> set[str]:
    return {w for w in (t.strip(".,;:()[]\"'").lower() for t in text.split())
            if len(w) >= 4 and w not in _STOP}


def candidate_pairs(claims: list[Claim]) -> list[tuple[Claim, Claim]]:
    """Pairs worth judging: same section OR sharing >=2 significant keywords. Deduped by the
    upper-triangular iteration. Limits expensive LLM judging to plausibly-related pairs."""
    kw = {c.id: _keywords(c.text) for c in claims}
    pairs = []
    for i, a in enumerate(claims):
        for b in claims[i + 1:]:
            if (a.section == b.section) or (len(kw[a.id] & kw[b.id]) >= 2):
                pairs.append((a, b))
    return pairs


_PAIR_PROMPT = """Decide the logical relation between two CLAIMS. Be conservative: only call a genuine, direct factual conflict a contradiction.

- "contradict": the claims make logically INCOMPATIBLE assertions about the same thing — they cannot both be true at the same time.
- "agree": they are consistent — equivalent, paraphrases/restatements of the same point, definitions of the same concept, or one entails the other.
- "independent": about different things, different aspects, or different scope / time / population / conditions; no logical conflict.

IMPORTANT — these are NOT contradictions (label "agree" or "independent"):
- differences in wording, emphasis, or level of detail
- two definitions or descriptions of the same concept
- claims about different sub-aspects, conditions, time periods, or populations

Examples:
- A: "Transfer learning reuses a model trained on one task for a related task." B: "Transfer learning leverages previously-learned knowledge for a new task." -> agree (paraphrase of the same definition)
- A: "Rent control increases availability for low-income households." B: "Rent control reduces total rental supply in the long run." -> contradict (incompatible effects on supply)
- A: "The model has 7B parameters." B: "The model was trained on 2T tokens." -> independent (different aspects)

Answer ONLY JSON: {{"relation": "contradict|agree|independent", "reasoning": "<one short sentence>"}}

CLAIM A: {a}
CLAIM B: {b}"""


def _coerce_relation(v) -> str:
    return v if v in _RELATIONS else "independent"


class PairContradictionJudge:
    """Claim-vs-claim entailment judge with self-consistency (modal relation, agreement
    fraction as confidence). A truncated/unparseable sample counts as 'independent'."""
    def __init__(self, llm, n_samples: int = 1, temperature: float = 0.0):
        self.llm = llm
        self.n_samples = n_samples
        self.temperature = temperature

    def _sample(self, prompt) -> dict:
        try:
            d = self.llm.complete_json(prompt, temperature=self.temperature)
        except Exception:
            return {}
        return d if isinstance(d, dict) else {}

    def judge(self, a: str, b: str) -> tuple[str, float]:
        prompt = _PAIR_PROMPT.format(a=a, b=b)
        labels = [_coerce_relation(self._sample(prompt).get("relation"))
                  for _ in range(self.n_samples)]
        tally = Counter(labels)
        modal, count = tally.most_common(1)[0]
        return modal, count / len(labels)


class ContradictionRecord(BaseModel):
    claim_a: str            # claim id
    claim_b: str            # claim id
    relation: str = "contradict"
    confidence: float = 0.0
    action: str = "detected"   # B1: detection only; B2 sets "flagged"


def detect_and_resolve(claims, judge, *, policy: str = "flag", threshold: float = 0.67):
    """Filter -> judge candidate pairs -> records for 'contradict' (conf >= threshold).
    policy='flag' (the decided MVP): set BOTH claims in each contradicting pair to
    verdict='contested' (kept, never dropped); record action='flagged'. No-op (claims, [])
    when judge is None or < 2 claims."""
    if judge is None or len(claims) < 2:
        return claims, []
    records = []
    for a, b in candidate_pairs(claims):
        rel, conf = judge.judge(a.text, b.text)
        if rel == "contradict" and conf >= threshold:
            records.append(ContradictionRecord(claim_a=a.id, claim_b=b.id, confidence=conf,
                                                action=("flagged" if policy == "flag" else "detected")))
    if policy == "flag":
        flagged = {r.claim_a for r in records} | {r.claim_b for r in records}
        by_id = {c.id: c for c in claims}
        for cid in flagged:
            by_id[cid].verdict = "contested"
    return claims, records
