"""DRA-Bench gold: Fable reference-report generator (spec §10 D1, plan Phase G — live run).

For each of the 250 DRA-Bench prompts, ask Fable (`claude-fable-5`) for a
detailed, well-structured Markdown research report via the minimal `FABLE_PROMPT`
(per D1 — no elaborate prompting), and write it to
`eval/dra_bench/fable_references/<id>.md`. These `.md` reports are the gold
*reference* reports; they are parsed downstream by the shared decomposer into a
`GradableReport` and scored on the same axes as our own / the baseline reports.

Fable can be reached two ways (`--via`):
  - **anthropic** — the user's personal Anthropic account via the public Messages
    API (`AnthropicChat`). Preferred default when `ANTHROPIC_API_KEY` is set,
    because Bedrock's Fable requires a data-sharing opt-in the user won't enable.
  - **bedrock** — `BedrockChat("us.anthropic.claude-fable-5")` (needs live AWS
    creds). `auto` (default) picks anthropic when the key is present, else bedrock.

Properties:
  - **Parallel** — independent generations via ThreadPoolExecutor (default 4
    workers; personal-account rate limits, with 429 backoff in the client).
  - **Resumable** — prompts whose `<id>.md` already exists are skipped, so a
    re-run only fills gaps.
  - **Skip-on-exception** — a failing prompt is logged and the run continues;
    failures are reported at the end.

Usage:
  .venv/bin/python experiments/generate_fable_references.py [--limit N] [--via auto|anthropic|bedrock]

For `anthropic`: set `ANTHROPIC_API_KEY` (in env or `.env`).
For `bedrock`: live AWS creds (e.g. `AWS_PROFILE=Arenal-science`); region from
`AWS_REGION` (default us-east-1).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Load .env so AWS_PROFILE / AWS_REGION are picked up if present.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional
    pass

from dra.eval.pipeline.gold.fable_reference import generate_reference
from dra.llm.anthropic_api import AnthropicChat
from dra.llm.bedrock import BedrockChat

# Fable is not available for on-demand throughput under its bare model ID; Bedrock
# requires the cross-region inference profile ID.
FABLE_BEDROCK_MODEL_ID = "us.anthropic.claude-fable-5"
# The Anthropic public API uses the bare model id.
FABLE_ANTHROPIC_MODEL_ID = "claude-fable-5"
REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_PATH = REPO_ROOT / "eval" / "dra_bench" / "prompts.jsonl"
OUTPUT_DIR = REPO_ROOT / "eval" / "dra_bench" / "fable_references"
# Lower default concurrency for personal-account rate limits (429 backoff in client).
MAX_WORKERS = 4


def build_fable_llm(via: str):
    """Construct the Fable LLM per `--via`. Returns (llm, label)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if via == "auto":
        via = "anthropic" if api_key else "bedrock"

    if via == "anthropic":
        if not api_key:
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set (env or .env). Set it or use --via bedrock."
            )
        # Fable uses extended thinking on complex prompts; a detailed report can
        # exceed a small cap (thinking + text), so give it generous headroom to
        # avoid truncating the gold reference mid-sentence.
        llm = AnthropicChat(api_key, model=FABLE_ANTHROPIC_MODEL_ID, max_tokens=16000)
        return llm, f"anthropic-api:{FABLE_ANTHROPIC_MODEL_ID}"

    region = os.environ.get("AWS_REGION", "us-east-1")
    llm = BedrockChat(FABLE_BEDROCK_MODEL_ID, region=region)
    return llm, f"bedrock:{FABLE_BEDROCK_MODEL_ID} region={region}"


def load_prompts(path: Path) -> list[dict]:
    items: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def generate_one(item: dict, fable, output_dir: Path) -> tuple[str, str, str | None]:
    """Generate + write one reference. Returns (id, status, error).

    status in {"written", "skipped", "failed"}.
    """
    item_id = item["id"]
    out_path = output_dir / f"{item_id}.md"
    if out_path.exists():
        return item_id, "skipped", None
    try:
        markdown = generate_reference(item["query"], fable)
        if not markdown or not markdown.strip():
            return item_id, "failed", "empty response"
        # Atomic-ish write: temp then rename so a crash never leaves a partial .md
        # that the resumability check would treat as done.
        tmp_path = out_path.with_suffix(".md.tmp")
        tmp_path.write_text(markdown)
        tmp_path.rename(out_path)
        return item_id, "written", None
    except Exception as e:  # skip-on-exception per prompt
        return item_id, "failed", f"{type(e).__name__}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N prompts (smoke run).")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="ThreadPoolExecutor worker count.")
    parser.add_argument(
        "--via",
        choices=["auto", "anthropic", "bedrock"],
        default="auto",
        help="How to reach Fable: anthropic (personal API), bedrock, or auto (anthropic if ANTHROPIC_API_KEY set).",
    )
    args = parser.parse_args()

    fable, label = build_fable_llm(args.via)

    items = load_prompts(PROMPTS_PATH)
    if args.limit is not None:
        items = items[: args.limit]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Model: {label}")
    print(f"Prompts: {len(items)}  output: {OUTPUT_DIR}")
    print(f"Workers: {args.workers}")

    written, skipped, failed = [], [], []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(generate_one, item, fable, OUTPUT_DIR): item["id"] for item in items}
        for fut in as_completed(futures):
            item_id, status, err = fut.result()
            if status == "written":
                written.append(item_id)
                print(f"[written] {item_id}  ({len(written)}/{len(items)})")
            elif status == "skipped":
                skipped.append(item_id)
            else:
                failed.append((item_id, err))
                print(f"[FAILED]  {item_id}: {err}", file=sys.stderr)

    print("\n=== SUMMARY ===")
    print(f"written: {len(written)}")
    print(f"skipped (already existed): {len(skipped)}")
    print(f"failed:  {len(failed)}")
    if failed:
        print("Failures:")
        for item_id, err in failed:
            print(f"  {item_id}: {err}")

    total_on_disk = len(list(OUTPUT_DIR.glob("*.md")))
    print(f"total references on disk: {total_on_disk}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
