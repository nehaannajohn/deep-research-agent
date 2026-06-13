"""Similarity-to-gold re-score: cached pipeline reports vs the Sonnet gold.

The ±verifier ablation cached every generated `ResearchReport` under
``<report_cache>/<arm>/<id>.json`` (arm ∈ {with_verifier, without_verifier}).
The Sonnet gold reference reports live under
``eval/dra_bench/reference_reports/<id>.md``. They were not both available at
ablation time, so the dedicated **similarity-to-gold** axis
(`scoring/similarity.py::score_similarity`) was never computed. This driver is
that re-score — it touches no live pipeline, only the cached artifacts.

Similarity is **claim-entailment coverage of the gold** (spec §4, D1/D5), a
*recall-style* measure:

    decompose the gold report -> atomic gold claims (same Bedrock decomposer the
        baseline scorer uses)
    our cached report already carries atomic claims (adapter `to_gradable`)
    for each gold claim: is it ENTAILED by some claim in our report? (judge)
    similarity = (gold claims entailed) / (total gold claims)

So a higher number means our report *covered more of what the reference said*.
It is directional (coverage of gold, not symmetric), semantic (entailment, not
string overlap), and yields one number per arm — with_verifier vs
without_verifier — directly comparable to the ±verifier ablation.

The judge/entailer and decomposer are injected (fakes in tests; Bedrock live),
keeping the pure helpers (`decompose_gold`, `gold_gradable`, `score_pair`,
`type_of`, `aggregate`) offline-testable. The live Bedrock wiring is
``# pragma: no cover``.

Usage:
    .venv/bin/python -m experiments.score_similarity_vs_gold --limit 3
    .venv/bin/python -m experiments.score_similarity_vs_gold            # both arms
    .venv/bin/python -m experiments.score_similarity_vs_gold --arm with_verifier
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

# Make ``src`` importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dra.eval.pipeline.adapters.dra import to_gradable  # noqa: E402
from dra.eval.pipeline.contracts import (  # noqa: E402
    EvalItem,
    GradableClaim,
    GradableReport,
)
from dra.eval.pipeline.scoring.similarity import score_similarity  # noqa: E402

logger = logging.getLogger(__name__)

REFERENCE_DIR = REPO_ROOT / "eval" / "dra_bench" / "reference_reports"
DEFAULT_CACHE_DIR = REPO_ROOT / "eval" / "results" / "pipeline" / "report_cache"
DEFAULT_OUT_DIR = "eval/results/similarity"
ARMS = ["with_verifier", "without_verifier"]
SEED = 13

# Entailment judge: panel-family model, independent of BOTH the Llama generator
# (our reports) and the Sonnet gold author — so neither side grades its own prose.
DEFAULT_ENTAIL_MODEL = "openai.gpt-oss-120b-1:0"


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested with fakes)
# --------------------------------------------------------------------------- #
def type_of(item_id: str) -> str:
    """DRA-Bench query type from an id (``dra-type3-033`` -> ``type3``)."""
    parts = item_id.split("-")
    return parts[1] if len(parts) >= 2 else "unknown"


def decompose_gold(markdown: str, decomposer: Callable[[str], list[str]]) -> list[str]:
    """Reduce a gold reference report to atomic claim texts via the decomposer.

    The decomposer is the same free-prose -> atomic-claims instrument the baseline
    scorer uses, so the gold is atomized by a mechanism comparable to how our own
    claims are produced. Empty/whitespace input -> no claims.
    """
    if not (markdown or "").strip():
        return []
    return [c for c in decomposer(markdown) if (c or "").strip()]


def gold_gradable(query: str, claim_texts: list[str]) -> GradableReport:
    """Wrap gold claim texts as a `GradableReport` (the reference for similarity).

    Only ``claims`` matter to `score_similarity` (it compares claim sets); sources
    and narrative are irrelevant to the reference side and left empty.
    """
    claims = [GradableClaim(id=f"g{i}", text=t) for i, t in enumerate(claim_texts)]
    return GradableReport(query=query, claims=claims)


def score_pair(
    our_report: GradableReport,
    gold: GradableReport,
    entail_fn: Callable[[str, list[str]], bool],
) -> dict:
    """Similarity of one (our report, gold) pair — delegates to `score_similarity`."""
    return score_similarity(our_report, gold, entail_fn)


def aggregate(results: list[dict]) -> dict:
    """Mean similarity overall + per query type, with coverage totals.

    ``similarity`` may be ``None`` for an item whose gold decomposed to zero
    claims; such items are excluded from the means (counted under ``n_no_gold``).
    """
    scored = [r for r in results if r.get("similarity") is not None]
    n = len(results)
    n_scored = len(scored)

    def _mean(rows: list[dict]) -> Optional[float]:
        vals = [r["similarity"] for r in rows]
        return sum(vals) / len(vals) if vals else None

    by_type: dict[str, list[dict]] = {}
    for r in scored:
        by_type.setdefault(r.get("type", "unknown"), []).append(r)

    return {
        "n": n,
        "n_scored": n_scored,
        "n_no_gold": n - n_scored,
        "similarity_mean": _mean(scored),
        "covered_total": sum(r.get("covered", 0) for r in scored),
        "reference_total": sum(r.get("total_reference", 0) for r in scored),
        "per_type": {
            t: {"n": len(rows), "similarity_mean": _mean(rows)}
            for t, rows in sorted(by_type.items())
        },
    }


# --------------------------------------------------------------------------- #
# Per-arm driver (resumable + skip-on-exception) — live orchestration
# --------------------------------------------------------------------------- #
def _gold_ids(reference_dir: Path) -> list[str]:
    """Sorted ids that have a gold reference report."""
    if not reference_dir.is_dir():
        return []
    return sorted(p.stem for p in reference_dir.glob("*.md"))


def _load_cached_report(path: Path):  # pragma: no cover - disk read
    """Deserialize a cached `ResearchReport`; None if absent/corrupt."""
    from dra.schemas import ResearchReport

    if not path.exists():
        return None
    try:
        return ResearchReport.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - corrupt cache -> skip
        logger.warning("corrupt report cache at %s; skipping", path)
        return None


def _already_scored(out_dir: str, arm: str) -> dict[str, dict]:
    """Resumability: load any per_item.json already written for this arm."""
    path = Path(out_dir) / arm / "per_item.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return {r["id"]: r for r in rows if "id" in r}
    except Exception:  # noqa: BLE001 - corrupt partial -> rescore all
        return {}


def score_arm(  # pragma: no cover - live orchestration
    arm: str,
    *,
    cache_dir: Path,
    reference_dir: Path,
    items: dict[str, EvalItem],
    decomposer: Callable[[str], list[str]],
    entail_fn: Callable[[str, list[str]], bool],
    out_dir: str,
    limit: Optional[int] = None,
    workers: int = 6,
) -> dict:
    """Score similarity-to-gold for every cached report under ``arm``.

    An item is scored only when BOTH a gold reference and a cached report exist.
    Resumable (skips ids already in per_item.json) and never fatal (an item whose
    scoring raises is logged + skipped). Writes per_item + summary, returns summary.
    """
    ids = _gold_ids(reference_dir)
    if limit is not None:
        ids = ids[:limit]

    done = _already_scored(out_dir, arm)
    todo = [i for i in ids if i not in done]

    def _score(item_id: str) -> Optional[dict]:
        try:
            report = _load_cached_report(cache_dir / arm / f"{item_id}.json")
            if report is None:
                return None  # no cached report for this arm -> nothing to score
            gold_md = (reference_dir / f"{item_id}.md").read_text(encoding="utf-8")
            item = items.get(item_id)
            query = item.query if item is not None else report.query
            gold = gold_gradable(query, decompose_gold(gold_md, decomposer))
            res = score_pair(to_gradable(report), gold, entail_fn)
            res["id"] = item_id
            res["type"] = type_of(item_id)
            return res
        except Exception:  # noqa: BLE001 - skip a pathological item, don't abort
            logger.warning("[%s] %s similarity raised; skipping\n%s",
                           arm, item_id, traceback.format_exc())
            return None

    if workers and workers > 1 and todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fresh = list(pool.map(_score, todo))
    else:
        fresh = [_score(i) for i in todo]

    results = list(done.values()) + [r for r in fresh if r is not None]
    results.sort(key=lambda r: r["id"])

    summary = {"arm": arm, "overall": aggregate(results)}

    adir = Path(out_dir) / arm
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "per_item.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (adir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


# --------------------------------------------------------------------------- #
# Live Bedrock wiring
# --------------------------------------------------------------------------- #
def _bedrock_entailer(model: str, region: str):  # pragma: no cover - live Bedrock
    """entail_fn(gold_claim, our_claim_texts) -> bool via a panel-family judge.

    YES iff the gold claim is supported/entailed by ANY of our report's claims.
    Conservative parse: only an explicit leading YES counts as entailed.
    """
    from dra.llm.bedrock import BedrockChat

    llm = BedrockChat(model, region=region, timeout=120)
    tmpl = (
        "You judge textual entailment. Does ANY single statement in the LIST "
        "support or entail the TARGET statement (same meaning, or the target "
        "follows from it)? Answer with one word: YES or NO.\n\n"
        "TARGET:\n{target}\n\nLIST:\n{lst}\n\nANSWER:"
    )

    def _entail(target: str, premises: list[str]) -> bool:
        if not (target or "").strip() or not premises:
            return False
        lst = "\n".join(f"- {p}" for p in premises)
        out = (llm.complete(tmpl.format(target=target, lst=lst)) or "").strip().upper()
        return out.startswith("YES")

    return _entail


def main(argv=None):  # pragma: no cover - live Bedrock wiring
    import argparse

    from dotenv import load_dotenv

    from dra.config import load_config

    from experiments.score_baselines import _bedrock_decomposer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=ARMS + ["both"], default="both")
    parser.add_argument("--limit", type=int, default=None, help="first N gold ids")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--reference-dir", default=str(REFERENCE_DIR))
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--entail-model", default=DEFAULT_ENTAIL_MODEL)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv()
    cfg = load_config()

    from dra.eval.pipeline.datasets.dra_bench import load_dra_bench

    items = {it.id: it for it in load_dra_bench()}
    decomposer = _bedrock_decomposer(cfg)
    entail_fn = _bedrock_entailer(args.entail_model, cfg.region)
    arms = ARMS if args.arm == "both" else [args.arm]

    for arm in arms:
        summary = score_arm(
            arm,
            cache_dir=Path(args.cache_dir),
            reference_dir=Path(args.reference_dir),
            items=items,
            decomposer=decomposer,
            entail_fn=entail_fn,
            out_dir=args.out_dir,
            limit=args.limit,
            workers=args.workers,
        )
        o = summary["overall"]
        print(f"[{arm}] n_scored={o['n_scored']} similarity_mean={o['similarity_mean']} "
              f"(covered {o['covered_total']}/{o['reference_total']}) -> {args.out_dir}/{arm}/")


if __name__ == "__main__":  # pragma: no cover
    main()
