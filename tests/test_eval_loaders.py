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


def test_scifact_mapping_supported_uses_rationale_sentences():
    from dra.eval.loaders.scifact import scifact_claim_to_example
    corpus = {7: {"doc_id": 7, "title": "T", "abstract": ["S0.", "S1 rationale.", "S2 rationale.", "S3."]}}
    claim = {"id": 42, "claim": "C", "cited_doc_ids": [7],
             "evidence": {"7": [{"sentences": [1, 2], "label": "SUPPORT"}]}}
    ex = scifact_claim_to_example(claim, corpus)
    assert ex.gold_label == "supported" and ex.example_id == "42"
    assert [p.text for p in ex.passages] == ["S1 rationale.", "S2 rationale."]
    assert ex.passages[0].source_id == "7:1" and ex.meta["dataset"] == "scifact"


def test_scifact_mapping_contradict_is_refuted():
    from dra.eval.loaders.scifact import scifact_claim_to_example
    corpus = {3: {"doc_id": 3, "title": "T", "abstract": ["only sentence."]}}
    claim = {"id": 1, "claim": "C", "cited_doc_ids": [3],
             "evidence": {"3": [{"sentences": [0], "label": "CONTRADICT"}]}}
    assert scifact_claim_to_example(claim, corpus).gold_label == "refuted"


def test_scifact_mapping_no_evidence_is_insufficient():
    from dra.eval.loaders.scifact import scifact_claim_to_example
    corpus = {9: {"doc_id": 9, "title": "T", "abstract": ["a.", "b."]}}
    claim = {"id": 5, "claim": "C", "cited_doc_ids": [9], "evidence": {}}
    ex = scifact_claim_to_example(claim, corpus)
    assert ex.gold_label == "insufficient"
    assert [p.text for p in ex.passages] == ["a.", "b."]   # falls back to cited abstract
