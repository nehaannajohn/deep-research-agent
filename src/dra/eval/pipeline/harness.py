"""Layer-2 live orchestrator (spec §4, plan Phase 4).

Runs our pipeline over a benchmark tier and scores every Layer-2 axis on the
resulting report. The orchestrator is pure composition + injected dependencies:
`run_query` (the live pipeline), the independent grounding judge, the blind
panel, and the answer extractor are all passed in via `PipelineDeps` — so the
end-to-end flow is fake-testable with **no network**.

Per item the flow is:

    report = deps.run_query(item.query)         # ResearchReport (live pipeline)
    g      = to_gradable(report, constraints)   # system-agnostic view
    grounding  = score_grounding(g, deps.grounding_judge, reference_claims=...)
    relevance  = score_relevance(g, item.query, deps.panel, seed=seed)
    quality    = score_quality(g, item.query, deps.panel, seed=seed)
    formatting = score_formatting(g, item.constraints)
    task_acc   = score_task_accuracy(extract_answer(...), item.gold_answer)  # gold only
    ece_inputs = system_ece(report.claims)      # surfaced confidence (no gold here)

`run_eval` maps `evaluate_item` over the items (a `ThreadPoolExecutor`, mirroring
`dra.eval.runner`), aggregates per-tier + overall, writes
``out_dir/{per_item.json, summary.json}``, and returns the summary. An item whose
scoring raises is logged and skipped — never fatal. The live `main()` wiring real
Bedrock deps is ``# pragma: no cover``.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

from dra.schemas import ResearchReport

from dra.eval.pipeline.adapters.dra import to_gradable
from dra.eval.pipeline.contracts import EvalItem, GradableReport
from dra.eval.pipeline.scoring.answer_extraction import extract_answer
from dra.eval.pipeline.scoring.calibration import system_ece
from dra.eval.pipeline.scoring.formatting import score_formatting
from dra.eval.pipeline.scoring.grounding import score_grounding
from dra.eval.pipeline.scoring.quality import score_quality
from dra.eval.pipeline.scoring.relevance import score_relevance
from dra.eval.pipeline.scoring.task_accuracy import score_task_accuracy

logger = logging.getLogger(__name__)

__all__ = ["PipelineDeps", "evaluate_item", "run_eval"]


@dataclass
class PipelineDeps:
    """Injected dependencies for the orchestrator (fakes in tests).

    - ``run_query`` — the live pipeline: ``query -> ResearchReport``.
    - ``grounding_judge`` — the INDEPENDENT grounding judge (panel family, not
      the in-loop verifier); exposes ``verdict(claim_text, passages) -> label``.
    - ``panel`` — the blind judge panel; exposes ``score(prompt, *, seed) -> dict``.
    - ``extractor`` — panel-family answer extractor; exposes ``complete(prompt)``.
    - ``reference_lookup`` — optional ``id -> GradableReport`` for the DRA-Bench
      Fable reference (similarity / citation-recall); unused in the agentic tier.
    """

    run_query: Callable[[str], ResearchReport]
    grounding_judge: object
    panel: object
    extractor: object
    reference_lookup: Optional[Callable[[str], GradableReport]] = None


def _expected_behavior_match(item: EvalItem, g: GradableReport, task_accuracy: Optional[dict]) -> Optional[bool]:
    """Best-effort `expected_behavior` check for DRA-Bench items.

    Heuristic + auditable (the deep semantic check is the panel's job): we map an
    item's `expected_behavior` to an observable property of the report —
    ``report_insufficient`` ⇒ the system abstained or carries an insufficiency
    disclaimer; ``flag_contested`` ⇒ at least one claim is ``contested``;
    ``answer_confident`` ⇒ the system committed to an answer (did not abstain).
    Returns ``None`` when the item declares no expected behavior.
    """
    expected = item.expected_behavior
    if not expected:
        return None

    contested = any(c.verdict == "contested" for c in g.claims)
    abstained = bool(task_accuracy and task_accuracy.get("abstained"))
    has_insufficient = any(c.verdict == "insufficient" for c in g.claims)

    if expected == "flag_contested":
        return contested
    if expected == "report_insufficient":
        return abstained or has_insufficient
    if expected == "answer_confident":
        return not abstained
    # ask_clarification and any future behavior: not decidable here.
    return None


def evaluate_item(item: EvalItem, deps: PipelineDeps, *, seed: int = 13) -> dict:
    """Run the pipeline on one item and score every axis. Returns a result dict.

    Result schema (per item)::

        {
          "id", "tier",
          "grounding":   <score_grounding dict>,
          "relevance":   <panel aggregate dict>,
          "quality":     <panel aggregate dict>,
          "formatting":  <score_formatting dict>,
          "task_accuracy": <score_task_accuracy dict | None>,   # gold only
          "extracted_answer": <str | None>,                     # gold only
          "ece": <system_ece dict>,
          "expected_behavior": <str | None>,
          "expected_behavior_match": <bool | None>,
        }
    """
    report = deps.run_query(item.query)
    g = to_gradable(report, constraints=item.constraints)

    reference_claims = item.reference_claims or None
    grounding = score_grounding(g, deps.grounding_judge, reference_claims=reference_claims)
    relevance = score_relevance(g, item.query, deps.panel, seed=seed)
    quality = score_quality(g, item.query, deps.panel, seed=seed)
    formatting = score_formatting(g, item.constraints)
    ece = system_ece(report.claims)

    extracted_answer: Optional[str] = None
    task_accuracy: Optional[dict] = None
    if item.gold_answer is not None:
        extracted_answer = extract_answer(
            g,
            item.query,
            aliases=tuple(item.gold_answer_aliases),
            extractor=deps.extractor,
        )
        task_accuracy = score_task_accuracy(
            extracted_answer,
            item.gold_answer,
            aliases=tuple(item.gold_answer_aliases),
        )

    return {
        "id": item.id,
        "tier": item.tier,
        "grounding": grounding,
        "relevance": relevance,
        "quality": quality,
        "formatting": formatting,
        "task_accuracy": task_accuracy,
        "extracted_answer": extracted_answer,
        "ece": ece,
        "expected_behavior": item.expected_behavior,
        "expected_behavior_match": _expected_behavior_match(item, g, task_accuracy),
    }


def _mean(values) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _aggregate(results: list[dict]) -> dict:
    """Aggregate a list of per-item results into mean axis scores + rates."""
    n = len(results)

    relevance_mean = _mean(r["relevance"].get("aggregate") for r in results)
    quality_mean = _mean(r["quality"].get("aggregate") for r in results)
    grounding_rate = _mean(r["grounding"].get("grounding_rate") for r in results)
    hallucination_rate = _mean(r["grounding"].get("hallucination_rate") for r in results)
    formatting_pass_rate = _mean(r["formatting"].get("pass_rate") for r in results)

    # task accuracy + abstention over items that carry a gold answer.
    graded = [r["task_accuracy"] for r in results if r["task_accuracy"] is not None]
    n_graded = len(graded)
    correct = sum(1 for t in graded if t.get("correct") is True)
    abstained = sum(1 for t in graded if t.get("abstained") is True)
    task_accuracy = (correct / n_graded) if n_graded else None
    abstention_rate = (abstained / n_graded) if n_graded else None

    # expected_behavior match rate over items that declare one.
    eb = [r["expected_behavior_match"] for r in results if r["expected_behavior_match"] is not None]
    expected_behavior_rate = (sum(1 for v in eb if v) / len(eb)) if eb else None

    return {
        "n": n,
        "n_graded": n_graded,
        "relevance_mean": relevance_mean,
        "quality_mean": quality_mean,
        "grounding_rate": grounding_rate,
        "hallucination_rate": hallucination_rate,
        "formatting_pass_rate": formatting_pass_rate,
        "task_accuracy": task_accuracy,
        "abstention_rate": abstention_rate,
        "expected_behavior_match_rate": expected_behavior_rate,
    }


def run_eval(items, deps: PipelineDeps, *, out_dir: str, seed: int = 13, max_workers: int = 1) -> dict:
    """Evaluate every item, aggregate per-tier + overall, write JSON, return summary.

    Mirrors `dra.eval.runner`: a `ThreadPoolExecutor` fans the (I/O-bound, model-
    heavy) per-item work out while preserving input order. An item whose
    `evaluate_item` raises is logged and skipped (never fatal). Writes
    ``out_dir/per_item.json`` and ``out_dir/summary.json``.
    """
    def _eval(indexed):
        idx, item = indexed
        try:
            return idx, evaluate_item(item, deps, seed=seed)
        except Exception:  # noqa: BLE001 - skip a pathological item, don't abort
            logger.warning("evaluate_item raised for %s; skipping", getattr(item, "id", "?"))
            return idx, None

    indexed = list(enumerate(items))
    if max_workers and max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            scored = list(pool.map(_eval, indexed))
    else:
        scored = [_eval(it) for it in indexed]

    results = [r for _idx, r in scored if r is not None]

    by_tier: dict[str, list[dict]] = {}
    for r in results:
        by_tier.setdefault(r["tier"], []).append(r)

    summary = {
        "seed": seed,
        "overall": _aggregate(results),
        "per_tier": {tier: _aggregate(rows) for tier, rows in by_tier.items()},
    }

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "per_item.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


def main():  # pragma: no cover - live Bedrock/Exa wiring
    """Live entrypoint: wire real Bedrock deps + a loader and run a tier.

    Builds the live pipeline (`dra.loop.run_query` over `build_deps(cfg)`), the
    panel-family grounding judge + blind panel + extractor, loads a tier
    (FRAMES / DRA-Bench), and writes results under ``eval/results/<run_id>/``.
    Exercised only in live runs; the pure orchestration above is unit-tested.
    """
    raise NotImplementedError(
        "Wire BedrockChat panel/grounding-judge/extractor + a live loader + "
        "dra.loop.run_query here for the live Layer-2 run."
    )
