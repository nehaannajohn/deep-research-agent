from __future__ import annotations

import random

from dra.verify.train.transfer import TransferExample, build_transfer_examples, stratified_anchor


def _report(rid, claims, sources):
    return {"query": "q", "claims": claims, "sources": sources}


def test_join_claim_to_grounding_judge_label():
    report = _report(
        "dra-type3-000",
        claims=[{"id": "c0", "text": "claim zero", "citations": [{"source_id": "s0", "span": "x"}]}],
        sources=[{"source_id": "s0", "text": "evidence text", "url": "u", "title": "t"}],
    )
    per_item = {"id": "dra-type3-000",
                "grounding": {"per_claim": [{"id": "c0", "verdict": "insufficient"}]}}
    out = build_transfer_examples({"dra-type3-000": report}, {"dra-type3-000": per_item})
    assert len(out) == 1
    ex = out[0]
    assert ex.claim == "claim zero"
    assert ex.passages[0].text == "evidence text"
    assert ex.label == "nei"
    assert ex.example_id == "dra-type3-000:c0"


def test_claims_without_a_judge_verdict_are_skipped():
    report = _report("r", claims=[{"id": "c0", "text": "t", "citations": []}], sources=[])
    per_item = {"id": "r", "grounding": {"per_claim": []}}
    assert build_transfer_examples({"r": report}, {"r": per_item}) == []


def test_stratified_anchor_balances_labels():
    exs = (
        [TransferExample(example_id=f"s{i}", claim="c", passages=[], label="supported") for i in range(50)]
        + [TransferExample(example_id=f"n{i}", claim="c", passages=[], label="nei") for i in range(5)]
        + [TransferExample(example_id=f"r{i}", claim="c", passages=[], label="refuted") for i in range(5)]
    )
    anchor = stratified_anchor(exs, n=12, seed=0)
    counts = {}
    for e in anchor:
        counts[e.label] = counts.get(e.label, 0) + 1
    assert counts.get("nei", 0) >= 4 and counts.get("refuted", 0) >= 4
    assert counts.get("supported", 0) <= 4
