"""Unit tests for the pure helpers in ``experiments.collect_agentic_baselines``.

Only the pure path-builders and the record shaper are tested here; the live
loaders / API calls are ``# pragma: no cover`` and exercised in the manual run.
"""
from __future__ import annotations

import json

from experiments.code.collect_agentic_baselines import (
    baselines_dir,
    build_record,
    out_path,
)


def test_baselines_dir_per_dataset():
    assert baselines_dir("frames").name == "frames_baselines"
    assert baselines_dir("truthfulqa").name == "truthfulqa_baselines"


def test_out_path_namespaces_provider_and_id():
    p = out_path("frames", "perplexity", "frames-007")
    assert p.parts[-3:] == ("frames_baselines", "perplexity", "frames-007.json")


def test_build_record_matches_scorer_shape():
    result = {
        "text": "Paris is the capital of France.",
        "urls": ["https://example.com/a", "https://example.com/b"],
        "citations": [{"url": "https://example.com/a"}],
        "raw": {"search_results": [{"url": "https://example.com/a", "title": "A"}]},
    }
    rec = build_record("perplexity", "frames-001", "What is the capital of France?", result)

    # Keys the scorer's load_record / normalize_sources / score_record read.
    assert rec["id"] == "frames-001"
    assert rec["provider"] == "perplexity"
    assert rec["query"] == "What is the capital of France?"
    assert rec["narrative"] == "Paris is the capital of France."
    assert rec["sources"] == ["https://example.com/a", "https://example.com/b"]
    assert rec["raw"]["search_results"][0]["url"] == "https://example.com/a"
    assert "collected_at" in rec
    # Round-trips through JSON (build_record validates this internally too).
    assert json.loads(json.dumps(rec))["narrative"] == rec["narrative"]


def test_build_record_defaults_when_fields_missing():
    rec = build_record("openai", "truthfulqa-010", "Q?", {})
    assert rec["narrative"] == ""
    assert rec["sources"] == []
    assert rec["citations"] == []
    assert rec["raw"] == {}
