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
from dataclasses import dataclass, replace
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
    reference_lookup: Optional[Callable[[str], object]] = None
    # Report caching: when set, a generated report is persisted under
    # ``<report_cache_dir>/<arm>/<item_id>.json`` and reused on later passes so
    # the expensive pipeline never re-runs just to re-score. ``arm`` namespaces
    # the cache per ablation arm (e.g. with_verifier vs without_verifier).
    # ``refresh`` forces regeneration even when a cached report exists.
    report_cache_dir: Optional[str] = None
    arm: str = "default"
    refresh: bool = False


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


def _resolve_reference_claims(reference_lookup, item_id: str) -> Optional[list]:
    """Call ``reference_lookup(item_id)`` and normalize to ``list[str] | None``.

    Accepts a list of claim texts, a `GradableReport`-like object (``.claims`` of
    objects with ``.text``), or ``None`` when no reference exists for the item.
    A raised lookup is non-fatal (similarity is simply skipped for that item).
    """
    try:
        ref = reference_lookup(item_id)
    except Exception:  # noqa: BLE001 - a missing/failed reference -> skip recall
        return None
    if ref is None:
        return None
    claims = getattr(ref, "claims", ref)
    texts = [getattr(c, "text", c) for c in claims]
    texts = [t for t in texts if isinstance(t, str) and t.strip()]
    return texts or None


def _cache_path(cache_dir: str, arm: str, item_id: str) -> str:
    """Cache key scheme: ``<cache_dir>/<arm>/<item_id>.json`` (one report/file).

    The ``arm`` segment isolates ablation arms (with_verifier vs without_verifier)
    so the same item id caches independently per arm.
    """
    return os.path.join(cache_dir, arm, f"{item_id}.json")


def _load_cached_report(path: str) -> Optional[ResearchReport]:
    """Deserialize a cached `ResearchReport` from JSON; None if absent/corrupt."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return ResearchReport.model_validate_json(f.read())
    except Exception:  # noqa: BLE001 - a corrupt cache file -> regenerate
        logger.warning("corrupt report cache at %s; regenerating", path)
        return None


def _save_cached_report(path: str, report: ResearchReport) -> None:
    """Persist a `ResearchReport` to JSON (pydantic dump) at `path`."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    os.replace(tmp, path)  # atomic: a partial write never poisons the cache


def _obtain_report(item: EvalItem, deps: PipelineDeps) -> ResearchReport:
    """Return the item's `ResearchReport`, from cache when present else generate.

    Decouples the expensive pipeline pass from the (re-runnable) scoring: a fresh
    item calls ``deps.run_query`` and caches the report; a cached item is loaded
    and ``run_query`` is never called (unless ``deps.refresh``).
    """
    if not deps.report_cache_dir:
        return deps.run_query(item.query)

    path = _cache_path(deps.report_cache_dir, deps.arm, item.id)
    if not deps.refresh:
        cached = _load_cached_report(path)
        if cached is not None:
            return cached

    report = deps.run_query(item.query)
    _save_cached_report(path, report)
    return report


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
    report = _obtain_report(item, deps)
    g = to_gradable(report, constraints=item.constraints)

    # Reference claims for citation-recall: prefer the item's own, else consult
    # the injected reference_lookup (e.g. a Fable reference loaded from disk).
    # The lookup may yield a list of claim texts or a GradableReport; both are
    # normalized to ``list[str]``. A missing reference -> None (recall skipped).
    reference_claims = item.reference_claims or None
    if reference_claims is None and deps.reference_lookup is not None:
        reference_claims = _resolve_reference_claims(deps.reference_lookup, item.id)
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


def run_eval(items, deps: PipelineDeps, *, out_dir: str, seed: int = 13, max_workers: int = 1,
             report_cache_dir: Optional[str] = None, arm: Optional[str] = None,
             refresh: Optional[bool] = None) -> dict:
    """Evaluate every item, aggregate per-tier + overall, write JSON, return summary.

    Mirrors `dra.eval.runner`: a `ThreadPoolExecutor` fans the (I/O-bound, model-
    heavy) per-item work out while preserving input order. An item whose
    `evaluate_item` raises is logged and skipped (never fatal). Writes
    ``out_dir/per_item.json`` and ``out_dir/summary.json``.

    ``report_cache_dir`` / ``arm`` / ``refresh`` override the matching
    `PipelineDeps` fields for this run (so the same deps can drive several arms /
    cache locations). When omitted, the deps' own values are used. Report
    caching makes the run resumable: a second invocation reuses cached reports
    and never re-calls the expensive pipeline.
    """
    overrides = {}
    if report_cache_dir is not None:
        overrides["report_cache_dir"] = report_cache_dir
    if arm is not None:
        overrides["arm"] = arm
    if refresh is not None:
        overrides["refresh"] = refresh
    if overrides:
        deps = replace(deps, **overrides)

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
