"""Re-measure Expected-Behavior-Match (EBM) for the black-box baselines using a
TEXT-LEVEL judge.

WHY: the harness computes EBM by checking per-claim ``verdict == "contested" /
"insufficient"``, but the black-box baseline adapter never assigns those
verdicts (a black box exposes no internal verdicts), so it structurally can't
pass — the reported baseline EBM (~0.60) is a broken measurement.

EBM is conceptually about whether the report TEXT exhibits the query's
``expected_behavior`` (``flag_contested`` -> surfaces sources disagree;
``report_insufficient`` -> says the answer is unknown/insufficient;
``answer_confident`` -> commits to a direct answer). That IS judgeable from the
report text + the query (no access to the baseline's passages needed — unlike
grounding). This driver re-measures it with a single panel-family LLM judge over
the saved report text (`dra.eval.pipeline.judges.behavior_judge`).

Per provider:
  - load the saved baseline responses ``eval/dra_bench/baselines/<provider>/<id>.json``
    (report text under ``narrative``),
  - match each to ``load_dra_bench()`` by id to get ``item.expected_behavior``,
  - call ``behavior_match(query, narrative, expected_behavior, BedrockChat(panel))``,
  - aggregate the per-provider TEXT-EBM rate over items that DECLARE a
    text-judgeable expected_behavior,
  - write ``eval/results/baselines_ebm/<provider>.json`` (rate + per-item + n).

Resumable (skips ids already in the output) + skip-on-exception; modest workers
(<=6) since another Bedrock job may run concurrently. The live Bedrock wiring is
``# pragma: no cover``; the pure judge helper is unit-tested in
``tests/test_behavior_judge.py``.

Usage:
    .venv/bin/python -m experiments.score_baselines_ebm                 # both
    .venv/bin/python -m experiments.score_baselines_ebm --provider openai
    .venv/bin/python -m experiments.score_baselines_ebm --limit 3
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

from dra.eval.pipeline.contracts import EvalItem  # noqa: E402
from dra.eval.pipeline.judges.behavior_judge import (  # noqa: E402
    TEXT_JUDGEABLE_BEHAVIORS,
    behavior_match,
)

logger = logging.getLogger(__name__)

BASELINES_DIR = REPO_ROOT / "eval" / "dra_bench" / "baselines"
DEFAULT_OUT_DIR = "eval/results/baselines_ebm"

# Judge: a panel-family model independent of the generator (spec §4). The first
# instance ``BEDROCK_PANEL_MODELS`` entry (``openai.gpt-oss-120b-1:0``) is a
# safe known-working default.
DEFAULT_JUDGE_MODEL = "openai.gpt-oss-120b-1:0"


# --------------------------------------------------------------------------- #
# Pure helpers (the judge itself is unit-tested in tests/test_behavior_judge.py)
# --------------------------------------------------------------------------- #
def load_record(path: str) -> dict:
    """Read one saved baseline response (collect shape: query/narrative/raw...)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _items_by_id() -> dict[str, EvalItem]:  # pragma: no cover - reads gitignored eval/
    from dra.eval.pipeline.datasets.dra_bench import load_dra_bench

    return {it.id: it for it in load_dra_bench()}


def _saved_ids(provider: str) -> list[str]:
    pdir = BASELINES_DIR / provider
    if not pdir.is_dir():
        return []
    return sorted(p.stem for p in pdir.glob("*.json"))


def _already_scored(out_dir: str, provider: str) -> dict[str, dict]:
    """Resumability: load any per-item rows already written for this provider."""
    path = Path(out_dir) / f"{provider}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {r["id"]: r for r in data.get("per_item", []) if "id" in r}
    except Exception:  # noqa: BLE001 - corrupt partial -> rescore all
        return {}


def aggregate(rows: list[dict]) -> dict:
    """Text-EBM rate over rows whose ``match`` is a concrete bool.

    Rows where ``match is None`` (behavior not text-judgeable, empty report, or
    an unparseable/failed judge call) are excluded from the denominator.
    """
    decided = [r for r in rows if isinstance(r.get("match"), bool)]
    n = len(decided)
    matched = sum(1 for r in decided if r["match"])
    return {
        "expected_behavior_match_rate": (matched / n) if n else None,
        "n": n,
        "n_matched": matched,
    }


# --------------------------------------------------------------------------- #
# Per-provider live driver (resumable + skip-on-exception)
# --------------------------------------------------------------------------- #
def score_provider(provider: str, *, items: dict[str, EvalItem], llm,
                   out_dir: str, limit: Optional[int] = None,
                   workers: int = 6) -> dict:  # pragma: no cover - live orchestration
    """Judge text-EBM for every saved response of ``provider``; write the result."""
    ids = _saved_ids(provider)
    if limit is not None:
        ids = ids[:limit]

    done = _already_scored(out_dir, provider)

    def _judge(item_id: str) -> Optional[dict]:
        if item_id in done:
            return done[item_id]
        try:
            item = items.get(item_id)
            if item is None:
                logger.warning("[%s] %s: no matching EvalItem; skipping", provider, item_id)
                return None
            behavior = item.expected_behavior
            # Only items that declare a TEXT-judgeable behavior contribute.
            if not behavior or behavior not in TEXT_JUDGEABLE_BEHAVIORS:
                return None
            record = load_record(str(BASELINES_DIR / provider / f"{item_id}.json"))
            report_text = record.get("narrative", "") or ""
            query = record.get("query", item.query)
            match = behavior_match(query, report_text, behavior, llm)
            logger.info("[%s] %s behavior=%s match=%s", provider, item_id, behavior, match)
            return {"id": item_id, "expected_behavior": behavior, "match": match}
        except Exception:  # noqa: BLE001 - skip a pathological item, don't abort
            logger.warning("[%s] %s judging raised; skipping\n%s",
                           provider, item_id, traceback.format_exc())
            return None

    if workers and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_judge, ids))
    else:
        rows = [_judge(i) for i in ids]

    rows = [r for r in rows if r is not None]
    rows.sort(key=lambda r: r["id"])

    summary = aggregate(rows)
    out = {"provider": provider, "judge_model": getattr(llm, "model_id", None),
           **summary, "per_item": rows}

    odir = Path(out_dir)
    odir.mkdir(parents=True, exist_ok=True)
    (odir / f"{provider}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv=None):  # pragma: no cover - live Bedrock wiring
    import argparse
    import os

    from dotenv import load_dotenv

    from dra.llm.bedrock import BedrockChat

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["perplexity", "openai", "both"],
                        default="both")
    parser.add_argument("--limit", type=int, default=None, help="first N saved items")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv()

    region = os.environ.get("AWS_REGION") or os.environ.get("BEDROCK_REGION") or "us-east-1"
    panel_models = [m.strip() for m in (os.environ.get("BEDROCK_PANEL_MODELS") or "").split(",") if m.strip()]
    judge_model = os.environ.get("BEDROCK_EBM_JUDGE_MODEL") or (panel_models[0] if panel_models else DEFAULT_JUDGE_MODEL)
    llm = BedrockChat(judge_model, region=region)

    items = _items_by_id()
    providers = ["perplexity", "openai"] if args.provider == "both" else [args.provider]

    for provider in providers:
        out = score_provider(provider, items=items, llm=llm, out_dir=args.out_dir,
                             limit=args.limit, workers=args.workers)
        print(f"[{provider}] text-EBM rate={out['expected_behavior_match_rate']} "
              f"(n={out['n']}, matched={out['n_matched']}) -> {args.out_dir}/{provider}.json")


if __name__ == "__main__":  # pragma: no cover
    main()
