"""Collect baseline reports (Perplexity Sonar + OpenAI) on a seeded 50-item
DRA-Bench subset, for later scoring with the Layer-2 harness.

This is the COLLECTION side: it calls the live baseline APIs via the injectable
clients in ``dra.eval.pipeline.baselines`` and writes raw responses to
``eval/dra_bench/baselines/<provider>/<id>.json``. Those raw files are what the
SCORING-side adapters (``PerplexityAdapter`` / ``OpenAIAdapter``) consume.

Design notes:
  - The 50-item subset is a **seeded** (default seed=0), **stratified** draw of
    10 prompts per ``meta.type`` from ``eval/dra_bench/prompts.jsonl`` — stable
    across runs so collection is reproducible/resumable.
  - **Resumable:** existing per-id output files are skipped.
  - **Skip-on-exception:** a failure on one prompt/provider is logged and the
    run continues. Perplexity is the committed baseline; OpenAI is the stretch
    target — if its model/endpoint isn't available with this key, we catch, log,
    and continue.
  - ``--limit N`` runs only the first N subset items (smoke test).

Usage:
    .venv/bin/python -m experiments.collect_dra_baselines --limit 3
    .venv/bin/python -m experiments.collect_dra_baselines              # full 50
    .venv/bin/python -m experiments.collect_dra_baselines --provider perplexity
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

# Make ``src`` importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dra.config import load_config  # noqa: E402
from dra.eval.pipeline.baselines.openai_client import OpenAIClient  # noqa: E402
from dra.eval.pipeline.baselines.perplexity_client import PerplexityClient  # noqa: E402

PROMPTS_PATH = REPO_ROOT / "eval" / "dra_bench" / "prompts.jsonl"
BASELINES_DIR = REPO_ROOT / "eval" / "dra_bench" / "baselines"

SUBSET_SEED = 0
PER_TYPE = 10  # 5 types x 10 = 50


def load_prompts() -> list[dict]:
    rows: list[dict] = []
    with open(PROMPTS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def stratified_subset(rows: list[dict], per_type: int, seed: int) -> list[dict]:
    """Seeded, stratified draw of ``per_type`` prompts per ``meta.type``.

    Deterministic: sort within each type by id, then sample with a per-type-
    independent RNG seeded from ``seed``, finally order the result by id.
    """
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_type[r.get("meta", {}).get("type", "unknown")].append(r)

    picked: list[dict] = []
    for t in sorted(by_type):
        items = sorted(by_type[t], key=lambda r: r["id"])
        rng = random.Random(f"{seed}:{t}")
        n = min(per_type, len(items))
        picked.extend(rng.sample(items, n))
    return sorted(picked, key=lambda r: r["id"])


def out_path(provider: str, prompt_id: str) -> Path:
    return BASELINES_DIR / provider / f"{prompt_id}.json"


def write_record(provider: str, prompt_id: str, query: str, result: dict) -> Path:
    p = out_path(provider, prompt_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "id": prompt_id,
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
    p.write_text(json.dumps(record, indent=2))
    return p


def collect_for_provider(name: str, client, subset: list[dict]) -> dict:
    """Run one provider across the subset. Returns a small stats dict."""
    written, skipped, failed = 0, 0, 0
    for row in subset:
        pid, query = row["id"], row["query"]
        if out_path(name, pid).exists():
            skipped += 1
            continue
        try:
            t0 = time.time()
            result = client.query(query)
            write_record(name, pid, query, result)
            written += 1
            chars = len(result.get("text", "") or "")
            nsrc = len(result.get("urls", []) or [])
            print(
                f"[{name}] {pid}: ok ({chars} chars, {nsrc} sources, "
                f"{time.time() - t0:.1f}s)"
            )
        except Exception as e:  # skip-on-exception
            failed += 1
            print(f"[{name}] {pid}: FAILED: {type(e).__name__}: {e}", file=sys.stderr)
    return {"written": written, "skipped": skipped, "failed": failed}


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=["perplexity", "openai", "both"],
        default="both",
    )
    parser.add_argument("--limit", type=int, default=None, help="smoke: first N items")
    parser.add_argument("--seed", type=int, default=SUBSET_SEED)
    parser.add_argument("--per-type", type=int, default=PER_TYPE)
    args = parser.parse_args(argv)

    load_dotenv()
    cfg = load_config()

    rows = load_prompts()
    subset = stratified_subset(rows, args.per_type, args.seed)
    if args.limit is not None:
        subset = subset[: args.limit]
    print(
        f"Subset: {len(subset)} prompts "
        f"(seed={args.seed}, per_type={args.per_type}); "
        f"output -> {BASELINES_DIR}"
    )

    results: dict[str, dict] = {}

    if args.provider in ("perplexity", "both"):
        ppx_key = cfg.perplexity_key or os.environ.get("PERPLEXITY_API_KEY", "")
        if not ppx_key:
            print("[perplexity] no API key found; skipping", file=sys.stderr)
        else:
            client = PerplexityClient(api_key=ppx_key, model="sonar-pro")
            print("[perplexity] starting (model=sonar-pro)")
            results["perplexity"] = collect_for_provider("perplexity", client, subset)

    if args.provider in ("openai", "both"):
        oai_key = os.environ.get("OPENAI_API_KEY", "")
        if not oai_key:
            print("[openai] no API key found; skipping (stretch)", file=sys.stderr)
        else:
            # OpenAI is the stretch target: if the model/endpoint is unavailable
            # with this key, every call will fail-and-skip; we still continue.
            client = OpenAIClient(api_key=oai_key, model="gpt-4o-search-preview")
            print("[openai] starting (model=gpt-4o-search-preview)")
            try:
                results["openai"] = collect_for_provider("openai", client, subset)
            except Exception as e:
                print(f"[openai] aborted: {type(e).__name__}: {e}", file=sys.stderr)
                results["openai"] = {"written": 0, "skipped": 0, "failed": len(subset)}

    print("\n=== SUMMARY ===")
    for name, stats in results.items():
        print(
            f"{name}: written={stats['written']} "
            f"skipped(existing)={stats['skipped']} failed={stats['failed']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
