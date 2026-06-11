"""Task accuracy (facet 2a) — extracted answer vs gold (spec §5, D2).

Normalized exact-match against the gold answer + aliases, then an optional
injected equivalence judge for synonym / format near-misses. Abstention
(``INSUFFICIENT`` / ``None``) is scored as a *feature*, not a wrong answer:
``correct`` is ``None`` and ``abstained`` is ``True``, so honest abstention is
reported separately rather than penalised.
"""
from __future__ import annotations

import re
import string
from typing import Optional, Protocol

_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


class EquivalenceJudge(Protocol):
    """Injected near-miss judge: are two answers the same?"""

    def equivalent(self, a: str, b: str) -> bool:
        ...


def _normalize(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = s.lower().strip()
    s = _PUNCT_RE.sub(" ", s)
    return " ".join(s.split())


def score_task_accuracy(
    extracted_answer: Optional[str],
    gold_answer: str,
    *,
    aliases: tuple[str, ...] = (),
    equivalence_judge: Optional[EquivalenceJudge] = None,
) -> dict:
    """Score an extracted answer against gold + aliases.

    Returns ``{correct, abstained, method}``:
    - abstention (``extracted_answer`` is ``None`` or ``"INSUFFICIENT"``) →
      ``{correct: None, abstained: True, method: "abstain"}``.
    - normalized EM against gold → ``method="em"``.
    - normalized match against an alias → ``method="alias"``.
    - otherwise, if an ``equivalence_judge`` is given, its verdict →
      ``method="judge"``.
    - else a plain miss → ``{correct: False, ...}`` with the last attempted
      method.
    """
    if extracted_answer is None or extracted_answer.strip().upper() == "INSUFFICIENT":
        return {"correct": None, "abstained": True, "method": "abstain"}

    norm = _normalize(extracted_answer)

    if norm == _normalize(gold_answer):
        return {"correct": True, "abstained": False, "method": "em"}

    for alias in aliases:
        if norm == _normalize(alias):
            return {"correct": True, "abstained": False, "method": "alias"}

    if equivalence_judge is not None:
        is_eq = equivalence_judge.equivalent(extracted_answer, gold_answer)
        return {"correct": bool(is_eq), "abstained": False, "method": "judge"}

    return {"correct": False, "abstained": False, "method": "em"}
