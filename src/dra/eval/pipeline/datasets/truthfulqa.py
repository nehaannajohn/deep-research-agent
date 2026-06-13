"""TruthfulQA loader — broad adversarial QA that probes common misconceptions.

TruthfulQA (HF ``truthful_qa``, ``generation`` config) is a broad, non-technical
benchmark whose questions are chosen because humans *often answer them falsely*
(myths, misconceptions, superstitions). Each row carries a question, a
``best_answer`` (the truthful answer), and lists of ``correct_answers`` /
``incorrect_answers``. We route the question through ``run_query`` and grade the
extracted answer against the truthful gold + its correct-answer aliases.

Why this complements FRAMES: FRAMES stresses *multi-hop factual retrieval*;
TruthfulQA stresses whether the pipeline resists the popular-but-wrong answer and
either reports the truthful fact or abstains — i.e. it exercises the
grounding/abstention behavior on diverse, non-technical topics that DRA-Bench's
technical skew under-tests.

`truthfulqa_row_to_item` is the **pure** mapper (fixture-tested), tolerant of the
documented column names and common variants. `load_truthfulqa` is the **live**
loader (``# pragma: no cover``) — it streams the HF dataset, samples ``n`` rows
under ``seed``, and maps each via the pure mapper.
"""
from __future__ import annotations

from typing import List

from dra.eval.pipeline.contracts import EvalItem

__all__ = ["truthfulqa_row_to_item", "load_truthfulqa"]

_QUESTION_KEYS = ("question", "Question", "prompt", "Prompt")
_BEST_KEYS = ("best_answer", "Best Answer", "best", "gold_answer")
_CORRECT_KEYS = ("correct_answers", "Correct Answers", "correct", "answers")
_CATEGORY_KEYS = ("category", "Category", "type")


def _first(row: dict, keys):
    """Return the first present, non-empty value among `keys` (else None)."""
    for k in keys:
        if k in row and row[k] not in (None, "", []):
            return row[k]
    return None


def _as_list(value) -> list[str]:
    """Normalize a correct-answers field to a clean list of strings.

    HF exposes it as a list, but defensively accept a ``;``-separated string too.
    """
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(";")
    else:
        parts = list(value)
    return [str(p).strip() for p in parts if str(p).strip()]


def truthfulqa_row_to_item(row: dict, *, idx: int) -> EvalItem:
    """Map one TruthfulQA row to a stress-tier `EvalItem` (pure).

    ``idx`` makes the id stable/unique (``truthfulqa-<idx:03d>``). The truthful
    ``best_answer`` is the gold; the ``correct_answers`` list becomes aliases so
    the answer-matcher accepts any truthful phrasing. ``expected_behavior`` is
    left unset — TruthfulQA answers range from a confident truthful fact to "there
    is no evidence", so we let task-accuracy vs the truthful gold drive scoring
    rather than imposing one behavior label.
    """
    question = _first(row, _QUESTION_KEYS) or ""
    best = _first(row, _BEST_KEYS)
    aliases = _as_list(_first(row, _CORRECT_KEYS))
    category = _first(row, _CATEGORY_KEYS)

    return EvalItem(
        id=f"truthfulqa-{idx:03d}",
        tier="stress",
        query=str(question),
        gold_answer=None if best is None else str(best),
        gold_answer_aliases=aliases,
        meta={"source": "truthfulqa", "category": category},
    )


def load_truthfulqa(n: int | None = None, *, seed: int = 13) -> List[EvalItem]:  # pragma: no cover - live HF download
    """Load + sample TruthfulQA (generation config) from HuggingFace (live).

    Resilient: an unavailable HF id/split/shape raises a clear error rather than
    corrupting the harness — the pure `truthfulqa_row_to_item` is unit-tested.
    """
    from datasets import load_dataset  # imported lazily; not a unit-test dep

    ds = load_dataset("truthful_qa", "generation", split="validation")
    if n is not None:
        ds = ds.shuffle(seed=seed).select(range(min(n, len(ds))))
    return [truthfulqa_row_to_item(dict(row), idx=i) for i, row in enumerate(ds)]
