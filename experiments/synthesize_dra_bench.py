"""DRA-Bench prompt-synthesis driver (spec §10 D1, plan Phase G — live run).

Generates / refines the 250 typed input prompts (5 types x ~50) for DRA-Bench
using a **non-generator-family** drafter (our generator is Llama, so we use
Opus 4.8). Opus only drafts/classifies *input* prompts here — not gold — so
panel overlap is irrelevant.

Outputs (gitignored `eval/dra_bench/`):
  - prompts.jsonl       one EvalItem per line (machine-readable)
  - prompts_review.md   human-readable, grouped by type, for user review

Modes
-----
Default (no mode flags): full regeneration of all five types (legacy behavior).

`--only type1` : regenerate ONLY type1 with an explicit *specificity spread*
  (~17 foundational/broad, ~17 intermediate, ~16 deep/specific); type2/3/4/5 are
  preserved verbatim from the existing prompts.jsonl.

`--relabel-type5` : keep the existing type5 queries verbatim, but reclassify each
  item's constraints into table (`{"format": "table"}`) vs diagram
  (`{"wants_visual": True}`). Classification is rule-based by default, or via one
  batched Opus call with `--classify-with-llm`. type1/2/3/4 preserved verbatim.

The two refinement modes compose: `--only type1 --relabel-type5` rebuilds type1
fresh and relabels type5, while keeping type2/3/4 byte-identical.

Top-up: if a type returns materially fewer than `--per-type`, a second
`complete` call is made for that type and the results are deduped/merged.

Live Bedrock run — requires AWS creds (profile `Arenal-science`,
us-west-2 / us-east-1).
"""
from __future__ import annotations

import argparse
import json
import os
import re
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

# type5 constraint variants (exactly one is stamped per item).
TABLE_CONSTRAINTS = {"format": "table"}
DIAGRAM_CONSTRAINTS = {"wants_visual": True}


# --------------------------------------------------------------------------
# type1 — specificity spread
# --------------------------------------------------------------------------

# (tier label, count, drafting instruction). Counts sum to per_type for n=50.
def _type1_tiers(per_type: int) -> list[tuple[str, int, str]]:
    """Three difficulty tiers for type1; counts scale to `per_type` (50 -> 17/17/16)."""
    foundational = round(per_type * 17 / 50)
    intermediate = round(per_type * 17 / 50)
    deep = per_type - foundational - intermediate
    return [
        (
            "foundational",
            foundational,
            "FOUNDATIONAL / BROAD questions on well-trodden, abundant-consensus "
            "NLP/AI topics that a strong model can answer confidently from "
            "widely-taught material. Examples of the desired flavor: 'Explain how "
            "self-attention works in transformers.', 'What are neural scaling "
            "laws?', 'What is RLHF and why is it used?', 'How does backpropagation "
            "train a neural network?'. Keep them broad and canonical.",
        ),
        (
            "intermediate",
            intermediate,
            "INTERMEDIATE-difficulty NLP/AI research questions: more specific than "
            "the canonical basics but still answerable with defensible literature "
            "consensus. Examples of the desired flavor: 'How does mixture-of-experts "
            "routing trade off compute and quality?', 'Why does layer normalization "
            "placement (pre-LN vs post-LN) affect training stability?', 'What are the "
            "main approaches to parameter-efficient fine-tuning and how do they "
            "differ?'.",
        ),
        (
            "deep",
            deep,
            "DEEP / SPECIFIC, technically demanding NLP/AI research questions on "
            "narrower phenomena where the answer exists in the literature but "
            "requires real depth. Examples of the desired flavor: 'How do rotary "
            "positional encodings extrapolate to context lengths beyond training, "
            "and what governs the failure mode?', 'What mechanisms drive reward "
            "overoptimization in RLHF and how is it mitigated?', 'How does the "
            "induction-head mechanism explain in-context learning?'.",
        ),
    ]


def _type1_draft_prompt(label: str, instruction: str, n: int, avoid: list[str]) -> str:
    base = (
        f"Draft {n} distinct, self-contained deep NLP/AI research questions.\n\n"
        f"These should be {instruction}\n\n"
        "Each must be a single standalone question a user could ask a deep "
        "research agent, with a defensible answer in the literature. Return one "
        "question per line, no numbering, no preamble, no commentary."
    )
    if avoid:
        sample = "\n".join(f"- {q}" for q in avoid[:60])
        base += (
            "\n\nDo NOT repeat or paraphrase any of these already-collected "
            f"questions; produce different ones:\n{sample}"
        )
    return base


def synthesize_type1_spread(llm, *, per_type: int) -> tuple[list[str], dict[str, int]]:
    """Draft `per_type` type1 queries with a foundational/intermediate/deep spread.

    Returns (queries, tier_counts) where tier_counts maps tier label -> #queries.
    Deduped across tiers; trimmed to per_type total preserving tier proportions.
    """
    all_queries: list[str] = []
    seen: set[str] = set()
    tier_counts: dict[str, int] = {}
    for label, want, instruction in _type1_tiers(per_type):
        collected: list[str] = []
        raw = llm.complete(_type1_draft_prompt(label, instruction, want, avoid=all_queries)) or ""
        for q in parse_query_lines(raw, limit=want * 2):
            if q.lower() in seen:
                continue
            seen.add(q.lower())
            collected.append(q)
            if len(collected) >= want:
                break
        # Top up this tier if short.
        if len(collected) < want:
            need = want - len(collected)
            raw2 = llm.complete(
                _type1_draft_prompt(label, instruction, need + 8, avoid=all_queries + collected)
            ) or ""
            for q in parse_query_lines(raw2, limit=need * 3):
                if q.lower() in seen:
                    continue
                seen.add(q.lower())
                collected.append(q)
                if len(collected) >= want:
                    break
        print(f"  type1[{label}]: {len(collected)}/{want}")
        tier_counts[label] = len(collected)
        all_queries.extend(collected)
    return all_queries[:per_type], tier_counts


# --------------------------------------------------------------------------
# type5 — table vs diagram classification
# --------------------------------------------------------------------------

# Rule-based cues. Order matters: table cues win when both appear because the
# brief says "compare … across" / "matrix" prompts are tabular even if phrased
# with "chart"/"map".
_TABLE_RE = re.compile(
    r"\b(table|tabulate|matrix|decision matrix|feature matrix|"
    r"comparison table|side-by-side|compare\b.*\bacross\b|across\b.*\bin a (?:table|matrix))\b",
    re.IGNORECASE,
)
_DIAGRAM_RE = re.compile(
    r"\b(diagram|flow|flowchart|timeline|map\b|maps?\b|architecture|graph|"
    r"pipeline|sequence diagram|illustrate|chart\b|hierarchy|cycle|funnel|layered)\b",
    re.IGNORECASE,
)


def classify_type5_rule_based(query: str) -> str:
    """Return 'table' or 'diagram' for a type5 query (default ambiguous -> diagram)."""
    if _TABLE_RE.search(query):
        return "table"
    if _DIAGRAM_RE.search(query):
        return "diagram"
    return "diagram"  # default ambiguous -> diagram


def classify_type5_with_llm(llm, queries: list[str]) -> list[str]:
    """One batched Opus call: classify each type5 query as 'table' or 'diagram'."""
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(queries))
    prompt = (
        "Each line below is a request whose answer is best conveyed visually. "
        "Classify each as either TABLE (the answer is fundamentally a structured "
        "comparison best shown as a Markdown table / matrix — e.g. 'compare X "
        "across A, B, C', 'feature matrix', 'tabulate values') or DIAGRAM (the "
        "answer is fundamentally a structural/temporal/flow visual best shown as "
        "a Mermaid diagram — e.g. flows, timelines, architectures, cycles, "
        "sequence/state diagrams, labeled anatomy). If ambiguous, choose DIAGRAM.\n\n"
        "Return ONLY a JSON array of strings, one per line in order, each either "
        '"table" or "diagram". No commentary.\n\n'
        f"{numbered}"
    )
    raw = llm.complete(prompt) or ""
    try:
        from dra.llm.bedrock import _extract_json  # type: ignore

        arr = _extract_json(raw)
    except Exception:
        arr = None
    out: list[str] = []
    if isinstance(arr, list) and len(arr) == len(queries):
        for v in arr:
            s = str(v).strip().lower()
            out.append("table" if s.startswith("table") else "diagram")
        return out
    # Fallback to rule-based if the LLM output is unusable.
    print("  (LLM classification unusable; falling back to rule-based)")
    return [classify_type5_rule_based(q) for q in queries]


def constraints_for_label(label: str) -> dict:
    return dict(TABLE_CONSTRAINTS) if label == "table" else dict(DIAGRAM_CONSTRAINTS)


# --------------------------------------------------------------------------
# existing-file helpers (preserve types verbatim)
# --------------------------------------------------------------------------

def load_existing_items(jsonl_path: str) -> dict[str, list[dict]]:
    """Load existing prompts.jsonl grouped by type, preserving order and exact dicts."""
    by_type: dict[str, list[dict]] = {}
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            by_type.setdefault(obj["meta"]["type"], []).append(obj)
    return by_type


# --------------------------------------------------------------------------
# full-regen path (legacy)
# --------------------------------------------------------------------------

def _draft_prompt(spec: dict, n: int, avoid: list[str]) -> str:
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
    by_type: dict[str, list[str]] = {}
    for spec in TYPE_SPECS:
        key = spec["key"]
        raw = llm.complete(_draft_prompt(spec, per_type, avoid=[])) or ""
        queries = parse_query_lines(raw, limit=per_type)
        print(f"  {key} ({spec['label']}): {len(queries)} from first call")
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


# --------------------------------------------------------------------------
# output writers (item-based, so we can mix fresh + preserved + relabeled)
# --------------------------------------------------------------------------

def write_outputs_from_items(
    items_by_type: dict[str, list[dict]],
    out_dir: str,
    *,
    type1_tier_counts: dict[str, int] | None = None,
    type5_labels: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """Write prompts.jsonl + prompts_review.md from per-type EvalItem dicts.

    `type5_labels` maps query -> 'table'/'diagram' for the review annotation.
    `type1_tier_counts` annotates the type1 section with the spread.
    """
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
        counts = {k: len(v) for k, v in items_by_type.items()}
        mf.write(f"Per-type counts: {dict(sorted(counts.items()))} "
                 f"(total {sum(counts.values())}).\n\n")

        for spec in TYPE_SPECS:
            key = spec["key"]
            items = items_by_type.get(key, [])
            mf.write(
                f"## {key} — {spec['label']} "
                f"(expected_behavior: `{spec['expected_behavior']}`)\n\n"
            )
            mf.write(f"_{spec['description']}_\n\n")
            if key == "type1" and type1_tier_counts:
                spread = ", ".join(f"{k}: {v}" for k, v in type1_tier_counts.items())
                mf.write(f"Specificity spread — {spread}.\n\n")
            if key == "type5" and type5_labels:
                n_table = sum(1 for it in items if type5_labels.get(it["query"]) == "table")
                n_diag = len(items) - n_table
                mf.write(f"Format split — table: {n_table}, diagram: {n_diag}.\n\n")
            for item in items:
                jf.write(json.dumps(item) + "\n")
                total += 1
                idx = items.index(item)
                if key == "type5" and type5_labels:
                    fmt = type5_labels.get(item["query"], "diagram")
                    tag = "table" if fmt == "table" else "diagram"
                    mf.write(f"{idx + 1}. [{tag}] {item['query']}\n")
                else:
                    mf.write(f"{idx + 1}. {item['query']}\n")
            mf.write("\n")

    return jsonl_path, md_path, total


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-type", type=int, default=50,
                    help="queries per type (default 50 -> ~250 total)")
    ap.add_argument("--only", choices=["type1"], default=None,
                    help="regenerate ONLY this type (with spread for type1); "
                         "preserve the others verbatim from the existing file")
    ap.add_argument("--relabel-type5", action="store_true",
                    help="keep type5 queries verbatim but reclassify each item's "
                         "constraints as table vs diagram")
    ap.add_argument("--classify-with-llm", action="store_true",
                    help="use one batched Opus call to classify type5 (else rule-based)")
    ap.add_argument("--existing", default=os.path.join(OUT_DIR, "prompts.jsonl"),
                    help="existing prompts.jsonl to preserve untouched types from")
    args = ap.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-1")
    refine = bool(args.only) or args.relabel_type5

    # Full regeneration (legacy) when no refinement flags.
    if not refine:
        print(f"Drafter: {DRAFTER_MODEL} @ {region} | full regen | per_type={args.per_type}")
        llm = BedrockChat(DRAFTER_MODEL, region=region, timeout=300)
        by_type_q = synthesize_with_topup(llm, per_type=args.per_type)
        items_by_type = {
            k: [build_prompt_item(k, q, i).model_dump() for i, q in enumerate(qs)]
            for k, qs in by_type_q.items()
        }
        jsonl_path, md_path, total = write_outputs_from_items(items_by_type, OUT_DIR)
        _print_done(items_by_type, total, jsonl_path, md_path)
        return 0

    # Refinement path: start from existing items, mutate only the targeted types.
    existing = load_existing_items(args.existing)
    items_by_type: dict[str, list[dict]] = {k: list(v) for k, v in existing.items()}
    type1_tier_counts: dict[str, int] | None = None
    type5_labels: dict[str, str] | None = None

    need_llm = (args.only == "type1") or (args.relabel_type5 and args.classify_with_llm)
    llm = None
    if need_llm:
        print(f"Drafter: {DRAFTER_MODEL} @ {region}")
        llm = BedrockChat(DRAFTER_MODEL, region=region, timeout=300)

    if args.only == "type1":
        print("Regenerating type1 with specificity spread...")
        queries, type1_tier_counts = synthesize_type1_spread(llm, per_type=args.per_type)
        items_by_type["type1"] = [
            build_prompt_item("type1", q, i).model_dump() for i, q in enumerate(queries)
        ]

    if args.relabel_type5:
        print("Relabeling type5 constraints (table vs diagram)...")
        t5_items = items_by_type.get("type5", [])
        queries = [it["query"] for it in t5_items]
        if args.classify_with_llm:
            labels = classify_type5_with_llm(llm, queries)
        else:
            labels = [classify_type5_rule_based(q) for q in queries]
        type5_labels = {q: lbl for q, lbl in zip(queries, labels)}
        rebuilt = []
        for i, (it, lbl) in enumerate(zip(t5_items, labels)):
            new_item = build_prompt_item(
                "type5", it["query"], i, constraints=constraints_for_label(lbl)
            )
            rebuilt.append(new_item.model_dump())
        items_by_type["type5"] = rebuilt
        n_table = sum(1 for lbl in labels if lbl == "table")
        print(f"  type5: table={n_table}, diagram={len(labels) - n_table}")

    jsonl_path, md_path, total = write_outputs_from_items(
        items_by_type, OUT_DIR,
        type1_tier_counts=type1_tier_counts,
        type5_labels=type5_labels,
    )
    _print_done(items_by_type, total, jsonl_path, md_path)
    return 0


def _print_done(items_by_type, total, jsonl_path, md_path):
    print("\n=== DONE ===")
    print(f"total items: {total}")
    for spec in TYPE_SPECS:
        k = spec["key"]
        print(f"  {k} ({spec['label']}): {len(items_by_type.get(k, []))}")
    print(f"jsonl:  {os.path.abspath(jsonl_path)}")
    print(f"review: {os.path.abspath(md_path)}")


if __name__ == "__main__":
    sys.exit(main())
