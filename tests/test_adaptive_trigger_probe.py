"""Unit tests for the adaptive-retrieval trigger-rate aggregation (pure)."""
from __future__ import annotations

from experiments.verifier_b.adaptive_trigger_probe import summarize_triggers


def _rows():
    # type1: two claims in one sub-question (s1) — one high, one low -> subq min low.
    # type2: one claim, high.
    return [
        {"type": "type1", "item_id": "a", "section": "s1", "label": "supported", "conf": 0.95},
        {"type": "type1", "item_id": "a", "section": "s1", "label": "insufficient", "conf": 0.40},
        {"type": "type2", "item_id": "b", "section": "s1", "label": "supported", "conf": 0.90},
    ]


def test_claim_level_trigger_rate():
    s = summarize_triggers(_rows(), taus=(0.6,))
    # 1 of 3 claims below 0.6
    assert s["claim_level"]["overall"]["n"] == 3
    assert s["claim_level"]["overall"]["trigger_rate"]["0.60"] == round(1 / 3, 3)


def test_subquestion_aggregation_uses_min():
    s = summarize_triggers(_rows(), taus=(0.6,))
    # two sub-questions: (a,s1) conf=min(0.95,0.40)=0.40 -> fires; (b,s1)=0.90 -> not
    assert s["subquestion_level"]["overall"]["n"] == 2
    assert s["subquestion_level"]["overall"]["trigger_rate"]["0.60"] == 0.5


def test_by_type_breakdown_and_low_label_mix():
    s = summarize_triggers(_rows(), taus=(0.6,))
    assert s["subquestion_level"]["by_type"]["type1"]["trigger_rate"]["0.60"] == 1.0
    assert s["subquestion_level"]["by_type"]["type2"]["trigger_rate"]["0.60"] == 0.0
    # the one low-confidence claim is the insufficient one
    assert s["low_conf_label_mix"]["by_label"] == {"insufficient": 1}


def test_query_level_affected_counts():
    s = summarize_triggers(_rows(), taus=(0.6,))
    # query "a" has a claim at 0.40 (<0.6) -> affected; query "b" min 0.90 -> not
    q = s["query_level"]["0.60"]
    assert q["n_queries"] == 2
    assert q["n_affected"] == 1
    assert q["affected_rate"] == 0.5
    assert q["mean_low_claims_per_query"] == 0.5  # (1 + 0) / 2


def test_empty_rows_safe():
    s = summarize_triggers([], taus=(0.7,))
    assert s["claim_level"]["overall"]["n"] == 0
    assert s["claim_level"]["overall"]["mean_conf"] is None
