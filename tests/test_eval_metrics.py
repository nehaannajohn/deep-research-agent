from dra.eval.base import EvalExample, LABELS
from dra.eval.metrics import per_class_prf, macro_f1, confusion_matrix, accuracy
from dra.schemas import Passage


def test_eval_example_contract():
    ex = EvalExample(example_id="e1", claim="c",
                     passages=[Passage(source_id="s", text="t")], gold_label="supported")
    assert ex.split == "test" and ex.passages[0].source_id == "s" and ex.meta == {}


def test_macro_f1_perfect():
    y = ["supported", "refuted", "insufficient", "contested"]
    assert macro_f1(y, y)["macro_f1"] == 1.0


def test_macro_f1_partial_and_only_present_classes():
    yt = ["supported", "supported", "refuted"]   # only 2 classes present
    yp = ["supported", "refuted", "refuted"]
    m = macro_f1(yt, yp)
    assert round(m["per_class"]["supported"]["f1"], 3) == 0.667
    assert round(m["per_class"]["refuted"]["f1"], 3) == 0.667
    assert round(m["macro_f1"], 3) == 0.667        # averaged over the 2 present classes only


def test_confusion_matrix_false_confidence_cells():
    yt = ["insufficient", "refuted", "supported"]
    yp = ["supported", "supported", "supported"]
    cm = confusion_matrix(yt, yp)
    assert cm["false_confidence"]["insufficient_to_supported"] == 1
    assert cm["false_confidence"]["refuted_to_supported"] == 1
    assert cm["matrix"]["supported"]["supported"] == 1


def test_accuracy():
    assert accuracy(["a", "b", "c"], ["a", "x", "c"]) == 2 / 3
