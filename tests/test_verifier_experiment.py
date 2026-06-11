from experiments.verifier_comparison import macro_f1, passed_validation


def test_macro_f1_perfect():
    y_true = ["supported", "refuted", "insufficient", "contested"]
    y_pred = ["supported", "refuted", "insufficient", "contested"]
    m = macro_f1(y_true, y_pred)
    assert m["macro_f1"] == 1.0
    assert m["per_class"]["supported"]["f1"] == 1.0


def test_macro_f1_partial():
    y_true = ["supported", "supported", "refuted"]
    y_pred = ["supported", "refuted", "refuted"]
    m = macro_f1(y_true, y_pred)
    assert round(m["per_class"]["supported"]["f1"], 3) == 0.667
    assert round(m["per_class"]["refuted"]["f1"], 3) == 0.667
    assert round(m["macro_f1"], 3) == 0.667


def test_validation_gate_threshold():
    assert passed_validation(["refuted", "refuted", "supported"], "refuted", threshold=2) is True
    assert passed_validation(["refuted", "supported", "insufficient"], "refuted", threshold=2) is False
