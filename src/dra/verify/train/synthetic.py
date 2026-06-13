"""Synthetic hard-negative *helpers* (pure). Generation (live Bedrock) is in
experiments/verifier_b/build_data.py and calls these.

We take a REAL passage (from our pipeline's cached reports) and ask a
panel-family LLM (independent of the generator) to write a near-miss false claim
of a given perturbation TYPE — plausible given the passage but not entailed by
it. Each candidate is then filtered by the independent grounding judge: it is
kept only if the judge does NOT label it `supported` (i.e. the perturbation
actually broke entailment).
"""
from __future__ import annotations

from dra.llm.bedrock import _extract_json
from dra.schemas import Passage

PERTURBATIONS = ("number", "entity_swap", "scope_overreach", "unsupported_causality")
# number/entity edits contradict the passage -> refuted; scope/causality overreach
# is not entailed but not directly contradicted -> nei.
PERTURBATION_LABEL = {
    "number": "refuted",
    "entity_swap": "refuted",
    "scope_overreach": "nei",
    "unsupported_causality": "nei",
}

_INSTRUCTIONS = {
    "number": "Change a quantity/number/percentage/date so the claim contradicts the passage.",
    "entity_swap": "Swap a key entity (person, place, organization, drug) for a different one.",
    "scope_overreach": "Overstate scope: turn a hedged/partial finding into a universal claim the passage does not support.",
    "unsupported_causality": "Assert a causal relationship the passage only describes as correlation or does not state.",
}

_PROMPT = """You write a single FALSE-but-plausible claim derived from a PASSAGE, for training a fact-checker.

Perturbation type: {ptype} — {instruction}

Rules:
- The claim must be a single declarative sentence.
- It must be plausible on its face but NOT supported by the passage.
- Keep the topic and surface style of the passage.

Answer ONLY JSON: {{"claim": "<one sentence>"}}

PASSAGE:
{passage}"""


def build_perturbation_prompt(passage_text: str, perturbation: str) -> str:
    """Render the generation prompt for one (passage, perturbation type)."""
    return _PROMPT.format(
        ptype=perturbation,
        instruction=_INSTRUCTIONS[perturbation],
        passage=passage_text,
    )


def parse_synthetic_claim(llm_output: str) -> "str | None":
    """Extract the claim string from a JSON or plain-text model response."""
    text = (llm_output or "").strip()
    if not text:
        return None
    try:
        data = _extract_json(text)
        if isinstance(data, dict) and isinstance(data.get("claim"), str):
            c = data["claim"].strip()
            return c or None
    except Exception:  # noqa: BLE001 - fall through to plain text
        pass
    return text or None


def is_genuine_negative(claim: str, passages: list[Passage], grounding_judge) -> bool:
    """Keep the synthetic claim only if the independent judge does NOT support it."""
    return grounding_judge.verdict(claim, passages) != "supported"
