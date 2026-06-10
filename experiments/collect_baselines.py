"""
Collect baseline results from OpenAI (o3 + web_search) and Perplexity (sonar-pro)
for the 4 assessment test cases.

Usage:
    .venv/bin/python -m experiments.collect_baselines [--provider openai|perplexity|both] [--case 1|2|3|4|all]

Outputs JSON per (provider, test_case) into eval/results/ at the repo root.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]  # experiments -> repo root
RESULTS_DIR = REPO_ROOT / "eval" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TEST_CASES = {
    1: {
        "label": "Straightforward",
        "query": (
            "What are the real-world risks and benefits of using synthetic data "
            "to train or fine-tune large language models? Focus on data quality, "
            "bias, and evaluation."
        ),
    },
    2: {
        "label": "Contradictory sources",
        "query": (
            "Is chain-of-thought prompting an effective reasoning strategy for LLMs, "
            "or does it primarily improve output formatting? The literature disagrees—"
            "find the real fault lines and explain what accounts for the conflicting results."
        ),
    },
    3: {
        "label": "Sparse & emerging",
        "query": (
            "What is the current state of inference-time compute scaling for LLM reasoning? "
            "Separate what has been empirically validated from what is still speculative, "
            "and identify where the evidence is too thin to draw conclusions."
        ),
    },
    4: {
        "label": "Multi-modal output",
        "query": (
            "Map the research landscape of multi-agent LLM systems. Produce a structured "
            "report that includes a visual taxonomy or design graph showing the major "
            "architectural patterns, how they relate, and where the open problems are."
        ),
    },
}


# ---------------------------------------------------------------------------
# Perplexity
# ---------------------------------------------------------------------------

def call_perplexity(query: str) -> dict:
    api_key = os.environ["PERPLEXITY_API_KEY"]
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a deep research assistant. Produce a structured, "
                    "evidence-backed report. Separate claims from evidence. "
                    "Indicate confidence level for each major claim."
                ),
            },
            {"role": "user", "content": query},
        ],
        "return_citations": True,
        "return_related_questions": False,
    }

    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    elapsed = time.time() - t0
    resp.raise_for_status()
    data = resp.json()

    answer = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    usage = data.get("usage", {})

    return {
        "provider": "perplexity",
        "model": "sonar-pro",
        "query": query,
        "answer": answer,
        "sources_cited": citations,
        "num_sources": len(citations),
        "steps": [],  # Perplexity doesn't expose intermediate search steps
        "total_steps": 1,  # single-pass model
        "wall_clock_seconds": round(elapsed, 2),
        "tokens": {
            "prompt": usage.get("prompt_tokens"),
            "completion": usage.get("completion_tokens"),
            "total": usage.get("total_tokens"),
        },
    }


# ---------------------------------------------------------------------------
# OpenAI (Responses API with web_search tool)
# ---------------------------------------------------------------------------

def call_openai(query: str) -> dict:
    api_key = os.environ["OPENAI_API_KEY"]
    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "o3",
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a deep research assistant. Produce a structured, "
                    "evidence-backed report. Separate claims from evidence. "
                    "Indicate confidence level for each major claim. "
                    "Use web search extensively to ground your claims."
                ),
            },
            {"role": "user", "content": query},
        ],
        "tools": [{"type": "web_search_preview"}],
        "tool_choice": "auto",
    }

    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=300)
    elapsed = time.time() - t0
    resp.raise_for_status()
    data = resp.json()

    # Parse the response output items to extract steps and final answer
    steps = []
    answer_parts = []
    sources = []

    for item in data.get("output", []):
        if item.get("type") == "web_search_call":
            steps.append({
                "type": "web_search",
                "query": item.get("action", {}).get("query", ""),
            })
        elif item.get("type") == "message":
            for content_block in item.get("content", []):
                if content_block.get("type") == "output_text":
                    answer_parts.append(content_block.get("text", ""))
                    # Extract annotations (citations)
                    for ann in content_block.get("annotations", []):
                        if ann.get("type") == "url_citation":
                            sources.append({
                                "url": ann.get("url", ""),
                                "title": ann.get("title", ""),
                            })

    unique_urls = list({s["url"] for s in sources})
    usage = data.get("usage", {})

    return {
        "provider": "openai",
        "model": data.get("model", "o3"),
        "query": query,
        "answer": "\n".join(answer_parts),
        "sources_cited": unique_urls,
        "num_sources": len(unique_urls),
        "steps": steps,
        "total_steps": len(steps),
        "wall_clock_seconds": round(elapsed, 2),
        "tokens": {
            "prompt": usage.get("input_tokens"),
            "completion": usage.get("output_tokens"),
            "total": (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_collection(providers: list[str], cases: list[int]):
    for case_id in cases:
        tc = TEST_CASES[case_id]
        print(f"\n{'='*60}")
        print(f"TC{case_id}: {tc['label']}")
        print(f"Query: {tc['query'][:80]}...")
        print(f"{'='*60}")

        for provider in providers:
            print(f"\n  -> Running {provider}...", flush=True)
            try:
                if provider == "perplexity":
                    result = call_perplexity(tc["query"])
                else:
                    result = call_openai(tc["query"])

                result["test_case_id"] = case_id
                result["test_case_label"] = tc["label"]

                out_path = RESULTS_DIR / f"tc{case_id}_{provider}.json"
                out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
                print(f"     Done in {result['wall_clock_seconds']}s | "
                      f"{result['num_sources']} sources | "
                      f"{result['total_steps']} steps")
                print(f"     Saved: {out_path}")

            except Exception as e:
                print(f"     FAILED: {e}")
                err_path = RESULTS_DIR / f"tc{case_id}_{provider}_error.json"
                err_path.write_text(json.dumps({"error": str(e), "case_id": case_id}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect baseline results")
    parser.add_argument("--provider", choices=["openai", "perplexity", "both"], default="both")
    parser.add_argument("--case", default="all", help="Test case number (1-4) or 'all'")
    args = parser.parse_args()

    providers = ["openai", "perplexity"] if args.provider == "both" else [args.provider]
    cases = list(TEST_CASES.keys()) if args.case == "all" else [int(args.case)]

    run_collection(providers, cases)
    print("\n\nCollection complete. Results in eval/results/")
