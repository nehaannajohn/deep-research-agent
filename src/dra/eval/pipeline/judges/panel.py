"""The blind judge panel + adjudication (spec §4, §6).

`JudgePanel(judges)` runs each injected judge over a rubric prompt, collects a
1–5 score + justification, and aggregates via mean + majority. When the panel
diverges beyond a threshold it records that *adjudication* triggered (a real run
would issue a tie-break / summarizing call; here we flag it and keep the
deterministic aggregate so reliability-per-cost can be computed after the fact).

Blinding:
- The rubric prompt carries no system identity (the rubric builders enforce
  this) — the panel does not inject one.
- When multiple candidate reports are compared, their presentation order is
  shuffled under `seed` (deterministic), to control position bias.

Each judge exposes ``complete_json(prompt) -> {"score": int, "justification": str}``
and is injected (a fake in tests; a panel-family Bedrock model live).
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Optional

# Adjudication fires when the per-judge score spread (max - min) exceeds this.
# A spread of 2 on a 1..5 scale (e.g. 3 vs 5) is tolerated; 3+ (e.g. 1 vs 4)
# signals genuine disagreement that warrants a tie-break.
ADJUDICATION_SPREAD_THRESHOLD = 2


def _coerce_score(d) -> Optional[int]:
    """Pull an integer 1..5 score from a judge response; None if unusable."""
    if not isinstance(d, dict):
        return None
    raw = d.get("score")
    try:
        s = int(raw)
    except (TypeError, ValueError):
        return None
    return s if 1 <= s <= 5 else None


class JudgePanel:
    def __init__(self, judges: list, threshold: int = ADJUDICATION_SPREAD_THRESHOLD):
        if not judges:
            raise ValueError("JudgePanel requires at least one judge")
        self.judges = judges
        self.threshold = threshold

    def _present(self, rubric_prompt: str, candidates: Optional[list[str]], seed: int) -> str:
        """Blind, seed-shuffled presentation of candidate reports (if comparing)."""
        if not candidates:
            return rubric_prompt
        order = list(candidates)
        random.Random(seed).shuffle(order)
        labels = [chr(ord("A") + i) for i in range(len(order))]
        block = "\n\n".join(f"CANDIDATE {lab}:\n{c}" for lab, c in zip(labels, order))
        return f"{rubric_prompt}\n\n{block}"

    def _ask(self, judge, prompt: str) -> Optional[int]:
        """One judge call. A raised / unparseable response -> None (dropped vote),
        so a single bad judge never crashes the panel (mirrors llm_judge.py)."""
        try:
            d = judge.complete_json(prompt)
        except Exception:
            return None
        return _coerce_score(d)

    def score(self, rubric_prompt: str, *, seed: int,
              candidates: Optional[list[str]] = None) -> dict:
        prompt = self._present(rubric_prompt, candidates, seed)
        scores = [s for s in (self._ask(j, prompt) for j in self.judges) if s is not None]

        if not scores:
            return {"aggregate": None, "mean": None, "majority": None,
                    "per_judge": [], "adjudicated": False}

        mean = sum(scores) / len(scores)
        # majority = most common score; ties break on the lower (more conservative).
        counts = Counter(scores)
        top = max(counts.values())
        majority = min(s for s, c in counts.items() if c == top)
        spread = max(scores) - min(scores)
        adjudicated = spread > self.threshold

        return {
            "aggregate": majority,
            "mean": mean,
            "majority": majority,
            "per_judge": scores,
            "spread": spread,
            "adjudicated": adjudicated,
        }
