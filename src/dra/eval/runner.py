"""Offline runner + prediction caching for the Layer-1 verifier-eval harness.

Iterates a `Verifier` over an `EvalExample` stream, recording one prediction row
per example, and caches the rows as JSONL keyed by the run identity
``(verifier_id, dataset, split, dataset_revision, sample_seed)``. The ensemble
verifier costs several model calls per claim, so re-running scoring/recalibration
must reuse cached predictions rather than re-query (CLAUDE.md design invariant).

Pure, fake-friendly: `verify()` is the only external surface and is injected in
tests. Nothing here imports Bedrock; the live convenience entrypoint at the
bottom is marked ``# pragma: no cover``.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Documented row schema (all values JSON-serializable):
ROW_KEYS = (
    "example_id", "gold", "pred", "confidence",
    "recommendation", "votes", "latency_ms", "model_calls",
)


def _cache_filename(verifier_id, dataset, split, dataset_revision, sample_seed) -> str:
    """Filesystem-safe JSONL filename from the cache-key parts.

    Scheme: ``{verifier_id}__{dataset}__{split}__{dataset_revision}__seed{sample_seed}.jsonl``
    Each part is sanitized (non-alphanumeric -> ``-``) so arbitrary dataset
    revisions/ids never produce an invalid path.
    """
    def sane(x) -> str:
        return "".join(c if (c.isalnum() or c in "-.") else "-" for c in str(x))

    return (
        f"{sane(verifier_id)}__{sane(dataset)}__{sane(split)}__"
        f"{sane(dataset_revision)}__seed{sane(sample_seed)}.jsonl"
    )


def _read_cache(path: str) -> "list[dict] | None":
    """Return cached rows, or None on any miss (missing file / bad line)."""
    try:
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return None


def _write_cache(path: str, rows: "list[dict]") -> None:
    """Atomically write rows as JSONL (unique temp path + os.replace)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)  # atomic on POSIX


def _model_calls(verifier, result) -> "int | None":
    """Read the model-call count defensively; None when unavailable.

    No verifier class is modified — we read whatever the object/result happens to
    expose. Prefers a per-result count if present, else falls back to the
    verifier attribute.
    """
    rc = getattr(result, "model_calls", None)
    if rc is not None:
        return rc
    return getattr(verifier, "model_calls", None)


def run_predictions(
    verifier,
    examples,
    *,
    verifier_id: str,
    dataset: str,
    split: str,
    dataset_revision: str,
    sample_seed,
    cache_dir: str,
    refresh: bool = False,
    max_workers: int = 1,
) -> "list[dict]":
    """Run `verifier` over `examples`, returning/caching prediction rows.

    Cache hit (file exists for this key and not ``refresh``) returns the cached
    rows without invoking the verifier. Otherwise each example is scored, the
    rows are written atomically as JSONL, and returned. An example whose
    ``verify()`` raises is logged and skipped (the row is omitted) — never fatal,
    mirroring the existing experiment's ``except: continue``.
    """
    path = os.path.join(
        cache_dir,
        _cache_filename(verifier_id, dataset, split, dataset_revision, sample_seed),
    )

    if not refresh:
        cached = _read_cache(path)
        if cached is not None:
            return cached

    def _score(indexed):
        idx, ex = indexed
        start = time.perf_counter()
        try:
            result = verifier.verify(ex.claim, ex.passages)
        except Exception:  # noqa: BLE001 - skip a pathological example, don't abort
            logger.warning("verify() raised for example %s; skipping", ex.example_id)
            return idx, None
        latency_ms = (time.perf_counter() - start) * 1000.0
        return idx, {
            "example_id": ex.example_id,
            "gold": ex.gold_label,
            "pred": result.label,
            "confidence": result.confidence,
            "recommendation": result.recommendation,
            "votes": dict(result.votes),
            "latency_ms": latency_ms,
            "model_calls": _model_calls(verifier, result),
        }

    # Score concurrently when max_workers > 1 (the ensemble fans out to several
    # Bedrock calls per claim, so the run is I/O-bound — parallelism is a large
    # speedup). map() preserves input order, so cached rows stay deterministic.
    indexed = list(enumerate(examples))
    if max_workers and max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            scored = list(pool.map(_score, indexed))
    else:
        scored = [_score(it) for it in indexed]

    rows = [row for _idx, row in scored if row is not None]
    _write_cache(path, rows)
    return rows


def cost_summary(rows, price_table: "dict[str, float]", *, verifier_id: str) -> dict:
    """Aggregate per-claim cost and latency over prediction `rows`.

    ``price_table`` maps a verifier id (or model id) to a price-per-model-call,
    e.g. ``{"A": 0.0012}``. Per-claim cost = ``model_calls * price``; rows whose
    ``model_calls`` is None contribute 0 cost / 0 calls but still count as a
    claim (so means divide by the full row count). Pure and unit-testable.

    Returns: ``{n, total_model_calls, total_cost, mean_cost,
    total_latency_ms, mean_latency_ms}``.
    """
    price = price_table.get(verifier_id, 0.0)
    n = len(rows)
    total_calls = sum((r.get("model_calls") or 0) for r in rows)
    total_cost = total_calls * price
    total_latency = sum((r.get("latency_ms") or 0.0) for r in rows)
    return {
        "n": n,
        "total_model_calls": total_calls,
        "total_cost": total_cost,
        "mean_cost": (total_cost / n) if n else 0.0,
        "total_latency_ms": total_latency,
        "mean_latency_ms": (total_latency / n) if n else 0.0,
    }


def run_cached(verifier_id, dataset, split, *, cache_dir, **kwargs):  # pragma: no cover - live wiring
    """Convenience entrypoint that builds the real (Bedrock-wired) verifier +
    loader and delegates to `run_predictions`. Exercised only in live runs; the
    pure core above is what the unit tests cover."""
    raise NotImplementedError(
        "Wire the real verifier registry + dataset loader here for live runs."
    )
