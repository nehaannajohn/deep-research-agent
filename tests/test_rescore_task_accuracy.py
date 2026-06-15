"""Unit tests for the equivalence-judge task-accuracy re-scoring (pure logic)."""
from __future__ import annotations

from experiments.rescore_task_accuracy import rescore, summarize


def _word_overlap_judge(q, cand, refs):
    cw = set(cand.lower().split())
    return any(cw & set(r.lower().split()) for r in refs)


def _rows():
    return [
        {"id": "a", "extracted_answer": "Denmark uses the krone",
         "task_accuracy": {"correct": False, "abstained": False, "method": "em"}},
        {"id": "b", "extracted_answer": "INSUFFICIENT",
         "task_accuracy": {"correct": None, "abstained": True, "method": "abstain"}},
        {"id": "c", "extracted_answer": "42",
         "task_accuracy": {"correct": True, "abstained": False, "method": "em"}},
        {"id": "d", "extracted_answer": "totally unrelated",
         "task_accuracy": {"correct": False, "abstained": False, "method": "em"}},
    ]


def test_rescore_judges_only_em_misses():
    golds = {"a": ("What currency?", "the krone", ["Danish krone"]), "d": ("Q", "xyz", [])}
    rows = rescore(_rows(), golds, _word_overlap_judge)
    assert rows[0]["task_accuracy"] == {"correct": True, "abstained": False, "method": "judge"}
    assert rows[1]["task_accuracy"]["abstained"] is True          # abstention preserved
    assert rows[2]["task_accuracy"]["correct"] is True            # EM hit untouched
    assert rows[2]["task_accuracy"]["method"] == "em"
    assert rows[3]["task_accuracy"]["correct"] is False           # judge said no


def test_rescore_skips_unknown_gold():
    rows = rescore(_rows(), {}, _word_overlap_judge)  # no golds -> nothing re-judged
    assert rows[0]["task_accuracy"]["method"] == "em"


def test_summarize_excludes_abstentions_from_accuracy():
    golds = {"a": ("q", "the krone", []), "d": ("q", "xyz", [])}
    s = summarize(rescore(_rows(), golds, _word_overlap_judge))
    assert s["n"] == 4 and s["n_abstained"] == 1 and s["n_scored"] == 3
    assert abs(s["task_accuracy"] - 2 / 3) < 1e-9   # a,c correct; d wrong; b abstained
