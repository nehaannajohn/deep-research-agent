"""The INDEPENDENT grounding judge (spec §4).

`LLMGroundingJudge(llm)` implements the `GroundingJudge` Protocol from
`scoring/grounding.py`: `verdict(claim_text, passages) -> VerdictLabel`. It
prompts an *injected*, panel-family `llm` for a single holistic verdict over a
claim's cited passages and parses the response resiliently.

Independence: this judge takes a plain `llm` (a panel-family model live) and
does NOT import or invoke the pipeline's in-loop verifier ensemble (`dra.verify`)
— re-using that ensemble to score grounding would only measure its
self-consistency (spec §4). It is structurally a single independent verifier,
reusing `llm_judge.py`'s prompt-then-parse shape and per-call try/except so one
malformed/truncated response never crashes scoring.
"""
from __future__ import annotations

from dra.llm.bedrock import _extract_json
from dra.schemas import Passage

# Same label vocabulary as the in-loop verifier, but an independent instrument.
_LABELS = ("supported", "refuted", "insufficient", "contested")

_PROMPT = """You judge whether a CLAIM is supported by its cited PASSAGES, considered together.

Labels:
- "supported": the passages (collectively) entail the claim
- "refuted": the passages contradict the claim
- "insufficient": the passages neither entail nor contradict it
- "contested": the passages are split — at least one supports AND at least one refutes the claim

Answer ONLY JSON: {{"label": "...", "reasoning": "<one short sentence>"}}

CLAIM: {claim}

PASSAGES:
{passages}"""


def _coerce_label(value) -> str:
    """Map any judge output to a known label; default to the safe `insufficient`."""
    return value if value in _LABELS else "insufficient"


class LLMGroundingJudge:
    """An injected panel-family `llm` exposing ``complete(prompt) -> str``.

    We call ``complete`` (the panel-family interface) and parse JSON ourselves
    with bedrock's resilient `_extract_json`, so a malformed/truncated sample is
    handled here rather than relying on the model wrapper's `complete_json`.
    """

    def __init__(self, llm):
        self.llm = llm

    def verdict(self, claim_text: str, passages: list[Passage]) -> str:
        # No cited passages -> nothing to ground against; mirrors llm_judge.py.
        if not passages:
            return "insufficient"

        rendered = "\n".join(f"[{p.source_id}] {p.text}" for p in passages)
        prompt = _PROMPT.format(claim=claim_text, passages=rendered)

        # Resilient parse: a raised / truncated / unparseable response -> a safe
        # `insufficient` vote rather than a crash (reuses llm_judge.py's pattern).
        try:
            data = _extract_json(self.llm.complete(prompt))
        except Exception:
            return "insufficient"

        if not isinstance(data, dict):
            return "insufficient"
        return _coerce_label(data.get("label"))
