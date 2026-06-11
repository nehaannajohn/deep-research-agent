"""DRA-Bench prompt-synthesis driver (spec §10 D1, plan Phase G — live run).

Generates the 250 typed input prompts (5 types x ~50) for DRA-Bench using a
**non-generator-family** drafter (our generator is Llama, so we use Opus 4.8).
Opus only drafts *input* prompts here — not gold — so panel overlap is irrelevant.

Outputs (gitignored `eval/dra_bench/`):
  - prompts.jsonl       one EvalItem per line (machine-readable)
  - prompts_review.md   human-readable, grouped by type, for user review

Top-up: if a type returns materially fewer than `--per-type`, a second
`complete` call is made for that type and the results are deduped/merged.

Live Bedrock run — requires AWS creds (profile `Arenal-science`, us-east-1).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Load .env so AWS_PROFILE / AWS_REGION / model ids are picked up.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional
    pass

from dra.eval.pipeline.gold.synth_prompts import (
    TYPE_SPECS,
    build_prompt_item,
    parse_query_lines,
)
from dra.llm.bedrock import BedrockChat

DRAFTER_MODEL = "global.anthropic.claude-opus-4-8"
OUT_DIR = "eval/dra_bench"


def _draft_prompt(spec: dict, n: int, avoid: list[str]) -> str:
    """Build the instruction asking the drafter for `n` distinct queries of a type."""
    base = (
        f"Draft {n} distinct, self-contained research questions that are "
        f"'{spec['label']}' prompts. {spec['description']}\n"
        f"Each must be a single standalone question a user could ask a deep "
        f"research agent. Return one question per line, no numbering, no preamble, "
        f"no commentary."
    )
    if avoid:
        sample = "\n".join(f"- {q}" for q in avoid[:40])
        base += (
            "\n\nDo NOT repeat or paraphrase any of these already-collected "
            f"questions; produce different ones:\n{sample}"
        )
    return base


def synthesize_with_topup(llm, *, per_type: int) -> dict[str, list[str]]:
    """Draft `per_type` queries per type, with one top-up call if a type falls short.

    Returns {type_key: [query, ...]} (deduped, <= per_type each).
    """
    by_type: dict[str, list[str]] = {}
    for spec in TYPE_SPECS:
        key = spec["key"]
        raw = llm.complete(_draft_prompt(spec, per_type, avoid=[])) or ""
        queries = parse_query_lines(raw, limit=per_type)
        print(f"  {key} ({spec['label']}): {len(queries)} from first call")

        # Top up if materially short (give the model headroom; we trim to per_type).
        if len(queries) < per_type:
            need = per_type - len(queries)
            raw2 = llm.complete(_draft_prompt(spec, need + 10, avoid=queries)) or ""
            seen = {q.lower() for q in queries}
            for q in parse_query_lines(raw2, limit=per_type * 2):
                if q.lower() not in seen:
                    seen.add(q.lower())
                    queries.append(q)
                    if len(queries) >= per_type:
                        break
            print(f"  {key}: {len(queries)} after top-up")

        by_type[key] = queries[:per_type]
    return by_type


def write_outputs(by_type: dict[str, list[str]], out_dir: str) -> tuple[str, str, int]:
    """Write prompts.jsonl and prompts_review.md; return (jsonl, md, total_items)."""
    os.makedirs(out_dir, exist_ok=True)
    jsonl_path = os.path.join(out_dir, "prompts.jsonl")
    md_path = os.path.join(out_dir, "prompts_review.md")

    spec_by_key = {s["key"]: s for s in TYPE_SPECS}
    total = 0

    with open(jsonl_path, "w") as jf, open(md_path, "w") as mf:
        mf.write("# DRA-Bench — synthesized prompts for review\n\n")
        mf.write(
            f"Drafter: `{DRAFTER_MODEL}` (non-generator family). "
            "Each prompt is an EvalItem; `expected_behavior` is derived from its "
            "type and is what makes the open-ended prompt gradable.\n\n"
        )
        counts = {k: len(v) for k, v in by_type.items()}
        mf.write(f"Per-type counts: {counts} (total {sum(counts.values())}).\n\n")

        for spec in TYPE_SPECS:
            key = spec["key"]
            queries = by_type.get(key, [])
            mf.write(
                f"## {key} — {spec['label']} "
                f"(expected_behavior: `{spec['expected_behavior']}`)\n\n"
            )
            mf.write(f"_{spec['description']}_\n\n")
            for idx, query in enumerate(queries):
                item = build_prompt_item(key, query, idx)
                jf.write(json.dumps(item.model_dump()) + "\n")
                total += 1
                mf.write(f"{idx + 1}. {query}\n")
            mf.write("\n")

    return jsonl_path, md_path, total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-type", type=int, default=50,
                    help="queries per type (default 50 -> ~250 total)")
    args = ap.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-1")
    print(f"Drafter: {DRAFTER_MODEL} @ {region} | per_type={args.per_type}")
    llm = BedrockChat(DRAFTER_MODEL, region=region, timeout=300)

    by_type = synthesize_with_topup(llm, per_type=args.per_type)
    jsonl_path, md_path, total = write_outputs(by_type, OUT_DIR)

    print("\n=== DONE ===")
    print(f"total items: {total}")
    for spec in TYPE_SPECS:
        k = spec["key"]
        print(f"  {k} ({spec['label']}): {len(by_type.get(k, []))}/{args.per_type}")
    print(f"jsonl:  {os.path.abspath(jsonl_path)}")
    print(f"review: {os.path.abspath(md_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
