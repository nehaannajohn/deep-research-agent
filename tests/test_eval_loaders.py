from dra.eval.loaders.base import stratified_sample, LABEL_MAP
from dra.eval.loaders.fever import fever_row_to_example
from dra.eval.base import EvalExample


def test_fever_row_mapping_supported():
    row = {"id": "x1", "claim": "C", "label": "SUPPORTS",
           "evidence": [["Page_A", "0", "Evidence sentence one."],
                        ["Page_A", "1", "Evidence sentence two."]]}
    ex = fever_row_to_example(row)
    assert ex.gold_label == "supported" and ex.example_id == "x1"
    assert [p.text for p in ex.passages] == ["Evidence sentence one.", "Evidence sentence two."]
    assert ex.passages[0].source_id == "Page_A:0" and ex.meta["dataset"] == "fever"


def test_fever_label_map():
    assert LABEL_MAP["REFUTES"] == "refuted"
    assert LABEL_MAP["NOT ENOUGH INFO"] == "insufficient"
    assert fever_row_to_example({"id": "a", "claim": "c", "label": "NOT ENOUGH INFO", "evidence": []}).gold_label == "insufficient"


def test_stratified_sample_caps_and_balances():
    exs = ([EvalExample(example_id=f"s{i}", claim="c", gold_label="supported") for i in range(50)]
           + [EvalExample(example_id=f"r{i}", claim="c", gold_label="refuted") for i in range(50)])
    out = stratified_sample(exs, n=10, seed=1)
    assert len(out) == 10
    labels = [e.gold_label for e in out]
    assert labels.count("supported") == 5 and labels.count("refuted") == 5  # balanced


def test_stratified_sample_returns_all_when_small():
    exs = [EvalExample(example_id="a", claim="c", gold_label="supported")]
    assert len(stratified_sample(exs, n=10)) == 1
