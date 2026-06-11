"""FEVER loader via the pre-joined copenlu/fever_gold_evidence (inline evidence, 3-way labels)."""
from __future__ import annotations

from dra.eval.base import EvalExample
from dra.eval.loaders.base import LABEL_MAP, SAMPLE_CAP, stratified_sample
from dra.schemas import Passage

FEVER_HF = "copenlu/fever_gold_evidence"


def fever_row_to_example(row) -> EvalExample:
    """Pure mapping of one copenlu/fever_gold_evidence row -> EvalExample (fixture-testable)."""
    passages = []
    for ev in row.get("evidence") or []:
        # ev = [page, sent_id, sentence_text]
        if len(ev) >= 3 and isinstance(ev[2], str) and ev[2].strip():
            page, sid, text = ev[0], ev[1], ev[2]
            passages.append(Passage(source_id=f"{page}:{sid}", text=text.strip(), title=str(page)))
    return EvalExample(
        example_id=str(row.get("id")),
        claim=row["claim"],
        passages=passages,
        gold_label=LABEL_MAP.get(row["label"], "insufficient"),
        split="test",
        meta={"dataset": "fever", "source": FEVER_HF},
    )


def load_fever(split="validation", n=SAMPLE_CAP, seed=13):  # pragma: no cover - live download
    import datasets
    ds = datasets.load_dataset(FEVER_HF, split=split)
    examples = [fever_row_to_example(r) for r in ds]
    return stratified_sample(examples, n=n, seed=seed)
