"""Build every Verifier B data slice to eval/verifier_b_data/*.jsonl (live).

Slices: fever_pairs, scifact_pairs, curriculum, synthetic, transfer (+ anchor.csv).
Run on EC2 (Bedrock for synthetic-negative generation + filtering; HF for FEVER/SciFact).

Usage:
    .venv-train/bin/python -m experiments.code.build_data --slice all
    .venv-train/bin/python -m experiments.code.build_data --slice synthetic --n-synth 3000
"""
from __future__ import annotations

import argparse
import glob
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from dra.eval.loaders.fever import load_fever          # noqa: E402
from dra.eval.loaders.scifact import load_scifact      # noqa: E402
from dra.schemas import Passage                         # noqa: E402
from dra.verify.train.curriculum import ablation_ladder  # noqa: E402
from dra.verify.train.pairs import TrainPair, example_to_pairs  # noqa: E402
from dra.verify.train.synthetic import (                # noqa: E402
    PERTURBATIONS, PERTURBATION_LABEL, build_perturbation_prompt,
    is_genuine_negative, parse_synthetic_claim,
)
from dra.verify.train.transfer import build_transfer_examples, stratified_anchor  # noqa: E402

OUT = REPO / "eval" / "verifier_b_data"
PIPE = REPO / "eval" / "results" / "pipeline"          # DRA-Bench cache — used ONLY for the transfer set (eval of B)
TRAINPOOL = REPO / "eval" / "trainpool" / "passages.jsonl"  # held-out, no-leak source for synthetic negatives
SYNTH_MODEL = "openai.gpt-oss-120b-1:0"   # panel-family, independent of the generator


def _dump(rows, name):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r.model_dump() if hasattr(r, "model_dump") else r, ensure_ascii=False) + "\n")
    print(f"[{name}] wrote {len(rows)} -> {path}")


def _distractor_pool(pairs, k=2000, seed=13):
    texts = list({p.passage for p in pairs if p.passage.strip()})
    random.Random(seed).shuffle(texts)
    return texts[:k]


def build_fever_scifact():
    fever = []
    for ex in load_fever(split="train", n=120_000):
        fever += example_to_pairs(ex)
    _dump(fever, "fever_pairs")
    sci = []
    for ex in load_scifact(split="train", n=2_000):
        sci += example_to_pairs(ex)
    _dump(sci, "scifact_pairs")
    return fever + sci


def build_curriculum(pool_pairs):
    pool = _distractor_pool(pool_pairs)
    rng = random.Random(13)
    rows = []
    for ex in load_scifact(split="train", n=2_000):
        rows += ablation_ladder(ex, distractor_pool=pool, rng=rng)
    for ex in load_fever(split="train", n=20_000):  # subsample fever for the ladder
        rows += ablation_ladder(ex, distractor_pool=pool, rng=rng)
    _dump(rows, "curriculum")


def _trainpool_passages(limit=8000):
    """Real Exa passages from the HELD-OUT training-query pool (Task 5b) — NOT from
    any eval benchmark's cache. Enforces the no-leak rule."""
    if not TRAINPOOL.exists():
        raise SystemExit(f"missing {TRAINPOOL}; run harvest_trainpool first (Task 5b)")
    out = []
    for line in open(TRAINPOOL, encoding="utf-8"):
        s = json.loads(line)
        t = (s.get("text") or "").strip()
        if len(t) > 200:
            out.append(Passage(source_id=s["source_id"], text=t,
                               url=s.get("url", ""), title=s.get("title", "")))
        if len(out) >= limit:
            break
    return out


def build_synthetic(n_synth=3000):
    from dra.config import load_config
    from dra.eval.pipeline.judges.grounding_judge import LLMGroundingJudge
    from dra.llm.bedrock import BedrockChat

    cfg = load_config()
    llm = BedrockChat(SYNTH_MODEL, region=cfg.region, timeout=120)
    judge = LLMGroundingJudge(BedrockChat(SYNTH_MODEL, region=cfg.region, timeout=120))

    passages = _trainpool_passages()   # held-out, no-leak (Task 5b) — never DRA-Bench
    rng = random.Random(13)
    rng.shuffle(passages)

    # Candidate (passage, perturbation) tasks — all 4 types per passage so a small
    # passage pool still yields enough negatives. Capped at ~2x target to bound the
    # filter rejects. PARALLEL over Bedrock (sequential here would be hours, like the
    # similarity job was) — each task does 1 generation + 1 judge-filter call.
    tasks = [(psg, pt) for psg in passages for pt in PERTURBATIONS]
    rng.shuffle(tasks)
    tasks = tasks[: max(n_synth * 2, n_synth)]

    def _one(task):
        psg, pt = task
        try:
            claim = parse_synthetic_claim(llm.complete(build_perturbation_prompt(psg.text, pt)))
        except Exception:
            return None
        if not claim or not is_genuine_negative(claim, [psg], judge):
            return None  # gen failed or perturbation didn't break entailment
        return TrainPair(claim=claim, passage=psg.text,
                         label=PERTURBATION_LABEL[pt], source="synthetic")

    from concurrent.futures import ThreadPoolExecutor
    rows = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for r in pool.map(_one, tasks):
            if r is not None:
                rows.append(r)
                if len(rows) % 200 == 0:
                    print(f"[synthetic] kept {len(rows)}/{n_synth}")
            if len(rows) >= n_synth:
                break
    _dump(rows, "synthetic")


def build_transfer():
    reports = {}
    for f in glob.glob(str(PIPE / "report_cache" / "with_verifier" / "*.json")):
        rid = Path(f).stem
        try:
            reports[rid] = json.load(open(f))
        except Exception:
            pass
    pi = json.load(open(PIPE / "with_verifier" / "per_item.json"))
    per_items = {r["id"]: r for r in pi}
    exs = build_transfer_examples(reports, per_items)
    _dump(exs, "transfer")
    anchor = stratified_anchor(exs, n=100, seed=13)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "anchor.csv", "w", encoding="utf-8") as f:
        f.write("example_id\tclaim\tsilver_label\thuman_label\n")
        for e in anchor:
            f.write(f"{e.example_id}\t{e.claim}\t{e.label}\t\n")
    print(f"[anchor] wrote {len(anchor)} rows -> {OUT/'anchor.csv'}")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--slice", choices=["all", "fever_scifact", "curriculum", "synthetic", "transfer"], default="all")
    p.add_argument("--n-synth", type=int, default=3000)
    a = p.parse_args(argv)

    base = None
    if a.slice in ("all", "fever_scifact", "curriculum"):
        base = build_fever_scifact() if a.slice != "curriculum" else \
            [TrainPair(**json.loads(l)) for l in open(OUT / "fever_pairs.jsonl")] + \
            [TrainPair(**json.loads(l)) for l in open(OUT / "scifact_pairs.jsonl")]
    if a.slice in ("all", "curriculum"):
        build_curriculum(base)
    if a.slice in ("all", "synthetic"):
        build_synthetic(a.n_synth)
    if a.slice in ("all", "transfer"):
        build_transfer()


if __name__ == "__main__":
    main()
