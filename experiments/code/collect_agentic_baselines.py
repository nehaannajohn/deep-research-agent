"""Collect baseline responses (Perplexity Sonar + OpenAI search) on the agentic
benchmark sets (FRAMES + TruthfulQA), for later scoring with the Layer-2 harness.

This is the COLLECTION side, analogous to ``collect_dra_baselines.py`` but for the
gold-bearing agentic/stress benchmarks rather than DRA-Bench. It loads the SAME
seeded item set the pipeline was evaluated on (``n=100, seed=13``) via the live HF
loaders, calls the live baseline APIs via the injectable clients in
``dra.eval.pipeline.baselines``, and writes raw responses to
``eval/<dataset>_baselines/<provider>/<id>.json``. Those raw files are what the
SCORING-side adapters (``PerplexityAdapter`` / ``OpenAIAdapter``) consume.

Design notes:
  - The item set is the loader's seeded sample (``load_frames`` /
    ``load_truthfulqa`` with ``n``, ``seed``) — identical to the pipeline run so
    the per-item comparison is apples-to-apples. Each `EvalItem` carries a stable
    id (``frames-NNN`` / ``truthfulqa-NNN``) used as the per-record filename.
  - **Resumable:** existing per-id output files are skipped.
  - **Skip-on-exception:** a failure on one item/provider is logged and the run
    continues.
  - ``--limit N`` runs only the first N items (smoke test).

SECURITY: API keys are read from the local ``.env`` via ``load_dotenv()`` /
``os.environ``; never printed or logged. Run this LOCALLY only.

Usage:
    .venv/bin/python -m experiments.collect_agentic_baselines --dataset frames --limit 3
    .venv/bin/python -m experiments.collect_agentic_baselines --dataset frames
    .venv/bin/python -m experiments.collect_agentic_baselines --dataset truthfulqa
    .venv/bin/python -m experiments.collect_agentic_baselines --dataset frames --provider perplexity
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Make ``src`` importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dra.config import load_config  # noqa: E402
from dra.eval.pipeline.baselines.openai_client import OpenAIClient  # noqa: E402
from dra.eval.pipeline.baselines.perplexity_client import PerplexityClient  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"

DATASET_N = 100
DATASET_SEED = 13


def baselines_dir(dataset: str) -> Path:
    return EVAL_DIR / f"{dataset}_baselines"


def load_items(dataset: str, n: int, seed: int):  # pragma: no cover - live HF download
    """Load the seeded EvalItem set for the dataset (same set as the pipeline run)."""
    if dataset == "frames":
        from dra.eval.pipeline.datasets.agentic import load_frames

        return load_frames(n, seed=seed)
    if dataset == "truthfulqa":
        from dra.eval.pipeline.datasets.truthfulqa import load_truthfulqa

        return load_truthfulqa(n, seed=seed)
    raise ValueError(f"unknown dataset: {dataset!r}")


def out_path(dataset: str, provider: str, item_id: str) -> Path:
    return baselines_dir(dataset) / provider / f"{item_id}.json"


def build_record(provider: str, item_id: str, query: str, result: dict) -> dict:
    """Build the saved-record shape expected by the scorer (matches write_record
    in collect_dra_baselines.py)."""
    import json  # local import keeps build_record a pure dict builder

    record = {
        "id": item_id,
        "provider": provider,
        "query": query,
        # Adapter-facing normalized shape:
        "narrative": result.get("text", ""),
        "sources": result.get("urls", []),
        # Collection-side extras:
        "citations": result.get("citations", []),
        "raw": result.get("raw", {}),
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    # Validate it's JSON-serializable up front (catches odd raw payloads early).
    json.dumps(record)
    return record


def write_record(dataset: str, provider: str, item_id: str, query: str, result: dict) -> Path:
    import json

    p = out_path(dataset, provider, item_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    record = build_record(provider, item_id, query, result)
    p.write_text(json.dumps(record, indent=2))
    return p


def collect_for_provider(dataset: str, name: str, client, items) -> dict:  # pragma: no cover - live API
    """Run one provider across the items. Returns a small stats dict."""
    written, skipped, failed = 0, 0, 0
    for item in items:
        pid, query = item.id, item.query
        if out_path(dataset, name, pid).exists():
            skipped += 1
            continue
        try:
            t0 = time.time()
            result = client.query(query)
            write_record(dataset, name, pid, query, result)
            written += 1
            chars = len(result.get("text", "") or "")
            nsrc = len(result.get("urls", []) or [])
            print(
                f"[{dataset}/{name}] {pid}: ok ({chars} chars, {nsrc} sources, "
                f"{time.time() - t0:.1f}s)"
            )
        except Exception as e:  # skip-on-exception
            failed += 1
            print(
                f"[{dataset}/{name}] {pid}: FAILED: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
    return {"written": written, "skipped": skipped, "failed": failed}


def main(argv: "list[str] | None" = None) -> int:  # pragma: no cover - live orchestration
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["frames", "truthfulqa"], required=True)
    parser.add_argument(
        "--provider",
        choices=["perplexity", "openai", "both"],
        default="both",
    )
    parser.add_argument("--limit", type=int, default=None, help="smoke: first N items")
    parser.add_argument("--n", type=int, default=DATASET_N)
    parser.add_argument("--seed", type=int, default=DATASET_SEED)
    args = parser.parse_args(argv)

    load_dotenv()
    cfg = load_config()

    items = load_items(args.dataset, args.n, args.seed)
    if args.limit is not None:
        items = items[: args.limit]
    print(
        f"Dataset {args.dataset}: {len(items)} items "
        f"(n={args.n}, seed={args.seed}); output -> {baselines_dir(args.dataset)}"
    )

    results: dict[str, dict] = {}

    if args.provider in ("perplexity", "both"):
        ppx_key = cfg.perplexity_key or os.environ.get("PERPLEXITY_API_KEY", "")
        if not ppx_key:
            print("[perplexity] no API key found; skipping", file=sys.stderr)
        else:
            client = PerplexityClient(api_key=ppx_key, model="sonar-pro")
            print("[perplexity] starting (model=sonar-pro)")
            results["perplexity"] = collect_for_provider(
                args.dataset, "perplexity", client, items
            )

    if args.provider in ("openai", "both"):
        oai_key = os.environ.get("OPENAI_API_KEY", "")
        if not oai_key:
            print("[openai] no API key found; skipping", file=sys.stderr)
        else:
            client = OpenAIClient(api_key=oai_key, model="gpt-4o-search-preview")
            print("[openai] starting (model=gpt-4o-search-preview)")
            try:
                results["openai"] = collect_for_provider(
                    args.dataset, "openai", client, items
                )
            except Exception as e:
                print(f"[openai] aborted: {type(e).__name__}: {e}", file=sys.stderr)
                results["openai"] = {"written": 0, "skipped": 0, "failed": len(items)}

    print("\n=== SUMMARY ===")
    for name, stats in results.items():
        print(
            f"{args.dataset}/{name}: written={stats['written']} "
            f"skipped(existing)={stats['skipped']} failed={stats['failed']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
