"""Generate a HELD-OUT training-query pool (disjoint from all eval benchmarks)
and harvest real Exa passages for Verifier B's synthetic hard negatives.

DRA-Bench / FRAMES / TruthfulQA are EVAL-ONLY; this pool exists so v1 trains on
real-pipeline-style passages without contaminating the pipeline eval. Queries are
generated fresh and ASSERTED disjoint from DRA-Bench before any harvesting.

Usage (live, EC2): .venv-train/bin/python -m experiments.verifier_b.harvest_trainpool --n 80
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from dra.config import load_config                 # noqa: E402
from dra.llm.bedrock import BedrockChat, _extract_json  # noqa: E402
from dra.planner import plan                       # noqa: E402
from dra.search import default_search_tool         # noqa: E402

OUT = REPO / "eval" / "trainpool"
DRA = REPO / "eval" / "dra_bench" / "prompts.jsonl"

_GEN_PROMPT = (
    "Generate {k} diverse, specific research questions a person might ask a "
    "deep-research assistant. Span factual, comparative, contested, "
    "ambiguous/unanswerable, and report-style asks, across many domains "
    "(science, tech, economics, health, history, policy). Avoid generic or "
    "duplicate questions.\n"
    'Answer ONLY JSON: {{"queries": ["...", "..."]}}'
)


def _norm(q: str) -> str:
    return " ".join((q or "").lower().split())


def _dra_queries() -> set[str]:
    if not DRA.exists():
        return set()
    return {_norm(json.loads(l).get("query", "")) for l in open(DRA, encoding="utf-8")}


def generate_queries(llm, n: int, banned: set[str]) -> list[str]:
    out: list[str] = []
    seen = set(banned)
    guard = 0
    while len(out) < n and guard < 20:
        guard += 1
        try:
            data = _extract_json(llm.complete(_GEN_PROMPT.format(k=min(40, n * 2))))
        except Exception:
            continue
        for q in (data.get("queries") if isinstance(data, dict) else []) or []:
            nq = _norm(q)
            if nq and nq not in seen:
                seen.add(nq)
                out.append(q.strip())
            if len(out) >= n:
                break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--k", type=int, default=5, help="passages per sub-question")
    a = ap.parse_args(argv)

    cfg = load_config()
    gen = BedrockChat(cfg.roles["generator"], region=cfg.region)
    search = default_search_tool(cfg)

    banned = _dra_queries()
    queries = generate_queries(gen, a.n, banned)
    # HARD disjointness guarantee before we harvest anything.
    overlap = {_norm(q) for q in queries} & banned
    assert not overlap, f"trainpool overlaps DRA-Bench: {len(overlap)} queries"

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "queries.jsonl", "w", encoding="utf-8") as f:
        for i, q in enumerate(queries):
            f.write(json.dumps({"id": f"trainq-{i:03d}", "query": q}) + "\n")

    seen, passages = set(), []
    for q in queries:
        try:
            p = plan(q, gen)
        except Exception:
            continue
        for subq in p.subquestions:
            try:
                res = search.search(subq, k=a.k)
            except Exception:
                continue
            for psg in res.passages:
                if psg.source_id in seen or not (psg.text or "").strip():
                    continue
                seen.add(psg.source_id)
                passages.append({"source_id": psg.source_id, "text": psg.text,
                                 "url": psg.url, "title": psg.title})
    with open(OUT / "passages.jsonl", "w", encoding="utf-8") as f:
        for psg in passages:
            f.write(json.dumps(psg, ensure_ascii=False) + "\n")
    print(f"trainpool: {len(queries)} queries, {len(passages)} passages -> {OUT}")


if __name__ == "__main__":
    main()
