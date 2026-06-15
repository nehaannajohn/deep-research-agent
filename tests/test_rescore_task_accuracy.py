"""Unit tests for the full-report judge task-accuracy re-scoring (pure logic).

The re-scoring removes extraction + exact-match: a single judge reads the full
report and the references and returns yes / no / abstain.
"""
from __future__ import annotations

from experiments.code.rescore_task_accuracy import rescore, summarize


def _fake_judge(question, report_text, references):
    """yes if the report shares a content word with a reference; abstain if the
    report is non-committal; else no."""
    t = report_text.lower()
    if "it depends" in t or "insufficient" in t or "cannot tell" in t:
        return "abstain"
    rw = set(t.split())
    return "yes" if any(rw & set(r.lower().split()) for r in references) else "no"


def _rows():
    return [
        {"id": "a", "task_accuracy": {"correct": False, "method": "em"}},
        {"id": "b", "task_accuracy": {"correct": False, "method": "em"}},
        {"id": "c", "task_accuracy": {"correct": False, "method": "em"}},
    ]


def _golds():
    return {
        "a": ("What currency?", "the krone", ["Danish krone"]),
        "b": ("Crime rate here?", "It depends on your location", ["I have no comment"]),
        "c": ("Capital of France?", "Paris", []),
    }


def _texts():
    return {
        "a": "Denmark uses the Danish krone as its currency.",   # correct -> yes
        "b": "It depends on which area you mean; I cannot say.",  # non-committal -> abstain
        "c": "The capital is Berlin.",                            # wrong -> no
    }


def test_full_report_judge_yes_no_abstain():
    rows = rescore(_rows(), _golds(), _texts(), _fake_judge)
    assert rows[0]["task_accuracy"] == {"correct": True, "abstained": False, "method": "judge_full"}
    assert rows[1]["task_accuracy"] == {"correct": None, "abstained": True, "method": "judge_full"}
    assert rows[2]["task_accuracy"] == {"correct": False, "abstained": False, "method": "judge_full"}


def test_skips_items_without_gold_or_report():
    rows = rescore(_rows(), {}, {}, _fake_judge)            # nothing to judge
    assert all(r["task_accuracy"]["method"] == "em" for r in rows)


def test_summarize_excludes_abstentions():
    s = summarize(rescore(_rows(), _golds(), _texts(), _fake_judge))
    assert s["n"] == 3 and s["n_abstained"] == 1 and s["n_scored"] == 2
    assert abs(s["task_accuracy"] - 0.5) < 1e-9   # a correct, c wrong, b abstained
