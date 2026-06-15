"""Score the collected agentic-baseline responses (FRAMES + TruthfulQA) through
the Layer-2 instrument.

The COLLECTION is done by ``collect_agentic_baselines.py`` (it wrote
``eval/<dataset>_baselines/<provider>/<id>.json``). This driver is the SCORING
side, analogous to ``score_baselines.py`` but for the gold-bearing agentic/stress
sets rather than DRA-Bench. It reuses ``score_baselines``'s pure helpers verbatim
(``load_record`` / ``normalize_sources`` / ``keyword_matcher`` / ``score_record``
/ ``aggregate`` / ``baseline_grounding`` + the live Bedrock deps/decomposer) and
only swaps:

  - **item loading** — the EvalItems come from the dataset loaders
    (``load_frames`` / ``load_truthfulqa``, same ``n=100, seed=13`` as collection)
    so each saved response is scored against ITS gold answer; and
  - **directories** — reads ``eval/<dataset>_baselines/<provider>/`` and writes
    ``eval/results/<dataset>_baselines/<provider>/summary.json``.

Because these items carry a ``gold_answer``, ``score_gradable`` computes
**task_accuracy** (extract answer -> EM/alias/judge vs gold) in addition to the
panel's **relevance** / **quality**. Grounding is N/A for these black-box
baselines (no usable source text / no expected_behavior) and is left to the
shared ``baseline_grounding`` (which reports ``applicable: False`` when no source
carries evidence text).

Resumable per item (skip if already scored) + skip-on-exception, ≤6 workers
(another Bedrock job may run concurrently).

Usage:
    .venv/bin/python -m experiments.score_agentic_baselines --dataset frames --limit 3
    .venv/bin/python -m experiments.score_agentic_baselines --dataset frames
    .venv/bin/python -m experiments.score_agentic_baselines --dataset truthfulqa --provider perplexity
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

# Make ``src`` importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dra.eval.pipeline.contracts import EvalItem  # noqa: E402
from dra.eval.pipeline.harness import PipelineDeps  # noqa: E402

# Reuse the existing baseline scorer's pure helpers + live wiring verbatim so the
# two drivers stay in lock-step (same instrument, same record shape).
from experiments.code.score_baselines import (  # noqa: E402
    ADAPTERS,
    aggregate,
    keyword_matcher,
    load_record,
    score_record,
)

logger = logging.getLogger(__name__)

EVAL_DIR = REPO_ROOT / "eval"
SEED = 13
DATASET_N = 100

DATASETS = ("frames", "truthfulqa")


def baselines_dir(dataset: str) -> Path:
    return EVAL_DIR / f"{dataset}_baselines"


def default_out_dir(dataset: str) -> str:
    return f"eval/results/{dataset}_baselines"


def load_items(dataset: str, n: int, seed: int) -> dict[str, EvalItem]:  # pragma: no cover - live HF download
    """Index the dataset's seeded EvalItems by id (carries gold_answer + aliases).

    Uses the SAME n/seed as collection so ids line up with the saved responses.
    """
    if dataset == "frames":
        from dra.eval.pipeline.datasets.agentic import load_frames

        items = load_frames(n, seed=seed)
    elif dataset == "truthfulqa":
        from dra.eval.pipeline.datasets.truthfulqa import load_truthfulqa

        items = load_truthfulqa(n, seed=seed)
    else:
        raise ValueError(f"unknown dataset: {dataset!r}")
    return {it.id: it for it in items}


def _saved_ids(dataset: str, provider: str) -> list[str]:
    """Sorted ids of saved responses for a provider/dataset."""
    pdir = baselines_dir(dataset) / provider
    if not pdir.is_dir():
        return []
    return sorted(p.stem for p in pdir.glob("*.json"))


def _already_scored(out_dir: str, provider: str) -> dict[str, dict]:
    """Resumability: load any per_item.json already written for this provider."""
    path = Path(out_dir) / provider / "per_item.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return {r["id"]: r for r in rows if "id" in r}
    except Exception:  # noqa: BLE001 - corrupt partial file -> rescore all
        return {}


def score_provider(dataset: str, provider: str, deps_factory: Callable[[], PipelineDeps], *,
                   adapter, items: dict[str, EvalItem], out_dir: str,
                   limit: Optional[int] = None, workers: int = 6,
                   seed: int = SEED) -> dict:  # pragma: no cover - live orchestration
    """Score every saved response for ``dataset``/``provider``; write per_item +
    summary. Resumable + never fatal. Returns the summary dict."""
    ids = _saved_ids(dataset, provider)
    if limit is not None:
        ids = ids[:limit]

    done = _already_scored(out_dir, provider)
    todo = [i for i in ids if i not in done]
    deps = deps_factory()

    def _score(item_id: str):
        try:
            record = load_record(str(baselines_dir(dataset) / provider / f"{item_id}.json"))
            item = items.get(item_id)
            if item is None:
                logger.warning("[%s/%s] %s: no matching EvalItem; skipping",
                               dataset, provider, item_id)
                return None
            return score_record(record, item, adapter, deps, seed=seed)
        except Exception:  # noqa: BLE001 - skip a pathological item, don't abort
            logger.warning("[%s/%s] %s scoring raised; skipping\n%s",
                           dataset, provider, item_id, traceback.format_exc())
            return None

    if workers and workers > 1 and todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fresh = list(pool.map(_score, todo))
    else:
        fresh = [_score(i) for i in todo]

    results = list(done.values()) + [r for r in fresh if r is not None]
    results.sort(key=lambda r: r["id"])

    summary = {
        "dataset": dataset,
        "provider": provider,
        "seed": seed,
        "overall": aggregate(results),
    }

    pdir = Path(out_dir) / provider
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "per_item.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (pdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv=None):  # pragma: no cover - live Bedrock wiring
    import argparse

    from dotenv import load_dotenv

    from dra.config import load_config

    # Reuse the live deps/decomposer builders from score_baselines so the Bedrock
    # wiring (grounding judge + panel + extractor + decomposer) is identical.
    from experiments.code.score_baselines import _bedrock_decomposer, _build_live_deps

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=list(DATASETS), required=True)
    parser.add_argument("--provider", choices=["perplexity", "openai", "both"],
                        default="both")
    parser.add_argument("--limit", type=int, default=None, help="first N saved items")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--n", type=int, default=DATASET_N)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv()
    cfg = load_config()

    out_dir = args.out_dir or default_out_dir(args.dataset)
    items = load_items(args.dataset, args.n, args.seed)
    decomposer = _bedrock_decomposer(cfg)
    providers = ["perplexity", "openai"] if args.provider == "both" else [args.provider]

    for provider in providers:
        adapter = ADAPTERS[provider](decomposer=decomposer, matcher=keyword_matcher)
        summary = score_provider(
            args.dataset,
            provider,
            deps_factory=lambda: _build_live_deps(cfg),
            adapter=adapter,
            items=items,
            out_dir=out_dir,
            limit=args.limit,
            workers=args.workers,
            seed=args.seed,
        )
        overall = summary["overall"]
        print(f"[{args.dataset}/{provider}] n={overall['n']} "
              f"task_accuracy={overall['task_accuracy']} "
              f"relevance_mean={overall['relevance_mean']} "
              f"quality_mean={overall['quality_mean']} -> {out_dir}/{provider}/")


if __name__ == "__main__":  # pragma: no cover
    main()
