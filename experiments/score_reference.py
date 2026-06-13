"""Score the Sonnet gold reference reports through the Layer-2 instrument.

The Sonnet gold reports (``eval/dra_bench/reference_reports/<id>.md``) are our
*reference*, but until now they were never themselves run through the judge
panel. This driver scores them on the axes that ARE fairly assessable for a
narrative-only artifact — the same axes we report for the black-box baselines:

  - **relevance** (blind panel rubric over the narrative + query)
  - **quality**   (blind panel rubric over the narrative + query)
  - **formatting** (deterministic checklist over the markdown + constraints)

This gives the **reference ceiling** on these axes and lets us place the gold on
the same leaderboard as Perplexity / OpenAI / our pipeline (±verifier).

Axes deliberately NOT computed for the gold (same reasons as the black-box
baselines, see `score_baselines.py`):
  - **grounding / hallucination** — the gold carries no retrieved passages with
    verbatim text, so there is nothing to check claims against (N/A).
  - **expected_behavior_match** — degenerate without our claim-level verdicts
    (contested / insufficient), which a reference narrative does not expose.
  - **similarity-to-gold** — the gold is the reference; similarity to itself is
    trivially 1.0.

The panel is injected (a fake in tests; the live blind panel via Bedrock). The
pure helpers (`build_gradable`, `score_reference_item`, `type_of`, `aggregate`)
are offline-testable; the live Bedrock wiring is ``# pragma: no cover``.

Usage:
    .venv/bin/python -m experiments.score_reference --limit 3
    .venv/bin/python -m experiments.score_reference            # all gold reports
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

# Make ``src`` importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dra.eval.pipeline.contracts import EvalItem, GradableReport  # noqa: E402
from dra.eval.pipeline.scoring.formatting import score_formatting  # noqa: E402
from dra.eval.pipeline.scoring.quality import score_quality  # noqa: E402
from dra.eval.pipeline.scoring.relevance import score_relevance  # noqa: E402

logger = logging.getLogger(__name__)

REFERENCE_DIR = REPO_ROOT / "eval" / "dra_bench" / "reference_reports"
DEFAULT_OUT_DIR = "eval/results/reference_sonnet"
SEED = 13


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested with fakes)
# --------------------------------------------------------------------------- #
def type_of(item_id: str) -> str:
    """DRA-Bench query type from an id (``dra-type3-033`` -> ``type3``)."""
    parts = item_id.split("-")
    return parts[1] if len(parts) >= 2 else "unknown"


def build_gradable(query: str, markdown: str, constraints: dict) -> GradableReport:
    """Wrap a reference report's markdown as a `GradableReport`.

    Only the narrative + constraints matter to the relevance/quality rubrics and
    the formatting checklist; claims/sources are irrelevant to those axes and are
    left empty (grounding is N/A for the gold).
    """
    return GradableReport(
        query=query,
        narrative_markdown=markdown or "",
        constraints=constraints or {},
    )


def score_reference_item(query: str, markdown: str, constraints: dict, panel, *,
                         seed: int = SEED) -> dict:
    """Score one reference report on relevance + quality + formatting."""
    g = build_gradable(query, markdown, constraints)
    return {
        "relevance": score_relevance(g, query, panel, seed=seed),
        "quality": score_quality(g, query, panel, seed=seed),
        "formatting": score_formatting(g, constraints),
    }


def aggregate(results: list[dict]) -> dict:
    """Mean relevance / quality / formatting-pass overall + per query type."""
    def _mean(rows: list[dict], axis: str, key: str) -> Optional[float]:
        vals = [r[axis].get(key) for r in rows if r.get(axis)]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    def _block(rows: list[dict]) -> dict:
        return {
            "n": len(rows),
            "relevance_mean": _mean(rows, "relevance", "aggregate"),
            "quality_mean": _mean(rows, "quality", "aggregate"),
            "formatting_pass_rate": _mean(rows, "formatting", "pass_rate"),
        }

    by_type: dict[str, list[dict]] = {}
    for r in results:
        by_type.setdefault(r.get("type", "unknown"), []).append(r)

    out = _block(results)
    out["per_type"] = {t: _block(rows) for t, rows in sorted(by_type.items())}
    return out


# --------------------------------------------------------------------------- #
# Driver (resumable + skip-on-exception) — live orchestration
# --------------------------------------------------------------------------- #
def _gold_ids(reference_dir: Path) -> list[str]:
    if not reference_dir.is_dir():
        return []
    return sorted(p.stem for p in reference_dir.glob("*.md"))


def _already_scored(out_dir: str) -> dict[str, dict]:
    path = Path(out_dir) / "per_item.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return {r["id"]: r for r in rows if "id" in r}
    except Exception:  # noqa: BLE001 - corrupt partial -> rescore all
        return {}


def score_all(  # pragma: no cover - live orchestration
    *, reference_dir: Path, items: dict[str, EvalItem], panel, out_dir: str,
    limit: Optional[int] = None, workers: int = 6, seed: int = SEED,
) -> dict:
    """Score every gold reference; write per_item + summary; return summary.

    Resumable (skips ids already in per_item.json) and never fatal.
    """
    ids = _gold_ids(reference_dir)
    if limit is not None:
        ids = ids[:limit]

    done = _already_scored(out_dir)
    todo = [i for i in ids if i not in done]

    def _score(item_id: str) -> Optional[dict]:
        try:
            md = (reference_dir / f"{item_id}.md").read_text(encoding="utf-8")
            item = items.get(item_id)
            query = item.query if item is not None else ""
            constraints = item.constraints if item is not None else {}
            res = score_reference_item(query, md, constraints, panel, seed=seed)
            res["id"] = item_id
            res["type"] = type_of(item_id)
            return res
        except Exception:  # noqa: BLE001 - skip a pathological item, don't abort
            logger.warning("%s reference scoring raised; skipping\n%s",
                           item_id, traceback.format_exc())
            return None

    if workers and workers > 1 and todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fresh = list(pool.map(_score, todo))
    else:
        fresh = [_score(i) for i in todo]

    results = list(done.values()) + [r for r in fresh if r is not None]
    results.sort(key=lambda r: r["id"])

    summary = {"system": "sonnet_reference", "seed": seed, "overall": aggregate(results)}

    odir = Path(out_dir)
    odir.mkdir(parents=True, exist_ok=True)
    (odir / "per_item.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (odir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv=None):  # pragma: no cover - live Bedrock wiring
    import argparse

    from dotenv import load_dotenv

    from dra.config import load_config
    from dra.eval.pipeline.datasets.dra_bench import load_dra_bench
    from dra.eval.pipeline.judges.panel import JudgePanel
    from dra.llm.bedrock import BedrockChat

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="first N gold ids")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--reference-dir", default=str(REFERENCE_DIR))
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv()
    cfg = load_config()

    items = {it.id: it for it in load_dra_bench()}
    panel = JudgePanel([BedrockChat(m, region=cfg.region) for m in cfg.panel_models])

    summary = score_all(
        reference_dir=Path(args.reference_dir),
        items=items,
        panel=panel,
        out_dir=args.out_dir,
        limit=args.limit,
        workers=args.workers,
    )
    o = summary["overall"]
    print(f"[sonnet_reference] n={o['n']} relevance_mean={o['relevance_mean']} "
          f"quality_mean={o['quality_mean']} formatting_pass={o['formatting_pass_rate']} "
          f"-> {args.out_dir}/")


if __name__ == "__main__":  # pragma: no cover
    main()
