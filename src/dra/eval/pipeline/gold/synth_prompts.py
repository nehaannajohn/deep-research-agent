"""DRA-Bench typed-prompt synthesizer (spec §10 D1, plan Phase G).

DRA-Bench is **5 query types x ~50 synthetic prompts** (~250). Each type carries
an `expected_behavior` derived from its type — that is what makes open-ended
prompts gradable (we score *whether the system did the right thing*, separating
plausible from correct):

  type1  deep NLP/AI                          -> answer_confident
  type2  pros-and-cons                        -> answer_confident (both sides)
  type3  contradictory / both-sides           -> flag_contested
  type4  no-answer / ambiguous (TruthfulQA-like) -> report_insufficient
                                                  (also acceptable: ask_clarification)
  type5  multi-format output (diagram/table)  -> answer_confident, wants_visual

The pure assembly (`build_prompt_item` + the type mappings) is what's unit-tested.
The live generation run — a **non-generator-family** model drafting `per_type`
distinct queries per type, then user review — is marked `# pragma: no cover`.
"""
from __future__ import annotations

from typing import List

from dra.eval.pipeline.contracts import EvalItem

__all__ = [
    "TYPE_SPECS",
    "expected_behavior_for",
    "also_acceptable",
    "build_prompt_item",
    "synthesize_prompts",
]


# Per-type specification. `constraints` are the per-type constraints stamped onto
# every prompt of that type; only type5 (multi-format output) carries one.
TYPE_SPECS: List[dict] = [
    {
        "key": "type1",
        "label": "deep NLP/AI",
        "description": (
            "Deep, technical NLP/AI research questions with a defensible answer "
            "in the literature (e.g. attention, tokenization, RLHF)."
        ),
        "expected_behavior": "answer_confident",
        "constraints": {},
    },
    {
        "key": "type2",
        "label": "pros-and-cons",
        "description": (
            "Questions asking for a balanced pros-and-cons assessment of an "
            "approach or design choice, where both sides should be covered."
        ),
        "expected_behavior": "answer_confident",
        "constraints": {},
    },
    {
        "key": "type3",
        "label": "contradictory / both-sides",
        "description": (
            "Questions where credible sources genuinely disagree — the evidence "
            "is contradictory and the system should surface the conflict."
        ),
        "expected_behavior": "flag_contested",
        "constraints": {},
    },
    {
        "key": "type4",
        "label": "no-answer / ambiguous",
        "description": (
            "Ill-posed, ambiguous, or unanswerable prompts (TruthfulQA-like) "
            "where the honest behavior is to report insufficiency or ask to "
            "clarify rather than fabricate an answer."
        ),
        "expected_behavior": "report_insufficient",
        "constraints": {},
    },
    {
        "key": "type5",
        "label": "multi-format output",
        "description": (
            "Questions whose answer is best conveyed with a diagram or table "
            "(mirrors the brief's multimodal/landscape prompt) — output is "
            "scored by the formatting checklist; the pipeline stays text-in."
        ),
        "expected_behavior": "answer_confident",
        "constraints": {"wants_visual": True},
    },
]

_SPEC_BY_KEY = {spec["key"]: spec for spec in TYPE_SPECS}

# type4 may legitimately ask the user to clarify instead of reporting a gap.
_ALSO_ACCEPTABLE = {"type4": ["ask_clarification"]}


def expected_behavior_for(type_key: str) -> str:
    """The `expected_behavior` derived from the prompt's type."""
    return _SPEC_BY_KEY[type_key]["expected_behavior"]


def also_acceptable(type_key: str) -> List[str]:
    """Alternative behaviors that also count as correct for this type."""
    return list(_ALSO_ACCEPTABLE.get(type_key, []))


def build_prompt_item(type_key: str, query: str, idx: int) -> EvalItem:
    """Assemble one DRA-Bench `EvalItem` from a type + drafted query (pure).

    The id is `dra-<type>-<idx:03d>`, the tier is always `dra_bench`, the
    per-type constraints are stamped on, and `meta` records the type plus the
    also-acceptable behaviors so the scorer can credit them.
    """
    spec = _SPEC_BY_KEY[type_key]
    return EvalItem(
        id=f"dra-{type_key}-{idx:03d}",
        tier="dra_bench",
        query=query,
        constraints=dict(spec["constraints"]),
        expected_behavior=expected_behavior_for(type_key),
        meta={"type": type_key, "also_acceptable": also_acceptable(type_key)},
    )


def synthesize_prompts(llm, *, per_type: int = 50) -> List[EvalItem]:  # pragma: no cover
    """Draft `per_type` distinct queries per type via the injected `llm`.

    Live step: `llm` is a **non-generator-family** model. For each type it is
    prompted with the type spec to draft distinct candidate queries; each is then
    assembled by the pure `build_prompt_item`. The drafted prompts are reviewed
    by the user before use (the review is a marked manual step).
    """
    items: List[EvalItem] = []
    for spec in TYPE_SPECS:
        type_key = spec["key"]
        prompt = (
            f"Draft {per_type} distinct, self-contained research questions that are "
            f"'{spec['label']}' prompts. {spec['description']}\n"
            f"Return one question per line, no numbering."
        )
        raw = llm.complete(prompt) or ""
        queries = [line.strip() for line in raw.splitlines() if line.strip()]
        for idx, query in enumerate(queries[:per_type]):
            items.append(build_prompt_item(type_key, query, idx))
    return items
