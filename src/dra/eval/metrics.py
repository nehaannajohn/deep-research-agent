"""Classification metrics over the 4-way label space. Pure functions; macro-F1 averages only
over classes present in y_true (so 3-way benchmarks fall out automatically)."""
from __future__ import annotations

from dra.eval.base import LABELS


def per_class_prf(y_true, y_pred):
    """Returns (per_class dict, macro_f1). macro_f1 averages F1 over classes present in y_true."""
    per_class, f1s = {}, []
    for lab in LABELS:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
        if (tp + fn) > 0:
            f1s.append(f1)
    return per_class, (sum(f1s) / len(f1s) if f1s else 0.0)


def macro_f1(y_true, y_pred) -> dict:
    per_class, macro = per_class_prf(y_true, y_pred)
    return {"per_class": per_class, "macro_f1": macro}


def confusion_matrix(y_true, y_pred) -> dict:
    """4x4 count matrix (gold rows x pred cols) + the named false-confidence cells
    (insufficient->supported, refuted->supported)."""
    m = {t: {p: 0 for p in LABELS} for t in LABELS}
    for t, p in zip(y_true, y_pred):
        if t in m and p in m[t]:
            m[t][p] += 1
    false_confidence = {
        "insufficient_to_supported": m["insufficient"]["supported"],
        "refuted_to_supported": m["refuted"]["supported"],
    }
    return {"matrix": m, "false_confidence": false_confidence}


def accuracy(y_true, y_pred) -> float:
    n = len(y_true)
    return sum(1 for t, p in zip(y_true, y_pred) if t == p) / n if n else 0.0
