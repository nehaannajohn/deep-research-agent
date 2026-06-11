"""Reporter: turn cached prediction rows into the Layer-1 `report.json` + `report.md`.

Pure assembly over the runner's prediction-row shape
(`example_id, gold, pred, confidence, recommendation, votes, latency_ms,
model_calls`), reusing the Phase-1/2 metrics and calibration modules. No
Bedrock/network — the only side-effecting helper (matplotlib reliability plot)
is `# pragma: no cover` and consumes pre-computed pure bin data.

See docs/superpowers/specs/2026-06-11-layer1-verifier-eval-design.md §8.
"""
from __future__ import annotations

from dra.eval.calibrate import ece_before_after, PlattCalibrator
from dra.eval.metrics import accuracy, confusion_matrix, per_class_prf
from dra.eval.runner import cost_summary

# The binary supported-vs-not collapse rule, stated so the report is auditable.
COLLAPSE_RULE = "p(supported) = confidence if pred=='supported' else 1 - confidence"
CONTESTED_DATASET = "contested"


def p_supported(label: str, confidence: float) -> float:
    """Collapse (label, confidence) to a supported-vs-not probability (§4)."""
    return confidence if label == "supported" else 1.0 - confidence


def _gold_counts(rows) -> dict:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["gold"]] = counts.get(r["gold"], 0) + 1
    return counts


def _metric_table(rows) -> dict:
    """3-way (or 4-way) metric table for one dataset's rows.

    macro-F1 averages only over classes present in gold (per_class_prf), so a
    verifier emitting `contested` on 3-way gold is never folded into the headline.
    """
    y_true = [r["gold"] for r in rows]
    y_pred = [r["pred"] for r in rows]
    per_class, macro = per_class_prf(y_true, y_pred)
    return {
        "n": len(rows),
        "macro_f1": macro,
        "per_class": per_class,
        "accuracy": accuracy(y_true, y_pred),
        "confusion": confusion_matrix(y_true, y_pred),
    }


def reliability_bins(probs, outcomes, bins: int = 15) -> list[dict]:
    """Pure reliability-diagram bin data: per equal-width bin, count + mean
    predicted confidence + empirical accuracy. Mirrors the binning in `ece`."""
    out: list[dict] = []
    n = len(probs)
    for k in range(bins):
        lo, hi = k / bins, (k + 1) / bins
        idx = [i for i, p in enumerate(probs)
               if (p > lo or (k == 0 and p >= lo)) and p <= hi]
        if not idx:
            continue
        out.append({
            "lo": lo,
            "hi": hi,
            "count": len(idx),
            "mean_conf": sum(probs[i] for i in idx) / len(idx),
            "accuracy": sum(outcomes[i] for i in idx) / len(idx),
            "fraction": len(idx) / n if n else 0.0,
        })
    return out


def _calibration_block(eval_rows, calib_rows, *, bins: int, diagram_path: str) -> dict:
    """ECE/Brier before & after Platt recalibration on the binary-collapsed signal.

    Fit the calibrator on `calib_rows` (the held-out calibration split); evaluate
    ECE/Brier + reliability bins on `eval_rows`. Falls back to fitting on the eval
    rows themselves when no disjoint split is supplied (still auditable; the
    manifest records which).
    """
    fit_rows = calib_rows if calib_rows else eval_rows
    fit_probs = [p_supported(r["pred"], r["confidence"]) for r in fit_rows]
    fit_outcomes = [1 if r["gold"] == "supported" else 0 for r in fit_rows]

    eval_probs = [p_supported(r["pred"], r["confidence"]) for r in eval_rows]
    eval_outcomes = [1 if r["gold"] == "supported" else 0 for r in eval_rows]

    calibrator = PlattCalibrator().fit(fit_probs, fit_outcomes)
    metrics = ece_before_after(eval_probs, eval_outcomes, calibrator, bins=bins)
    return {
        **metrics,
        "n_fit": len(fit_rows),
        "n_eval": len(eval_rows),
        "fit_on_disjoint_split": bool(calib_rows),
        "collapse_rule": COLLAPSE_RULE,
        "reliability_bins": reliability_bins(eval_probs, eval_outcomes, bins=bins),
        "reliability_bins_after": reliability_bins(
            [calibrator.apply(p) for p in eval_probs], eval_outcomes, bins=bins),
        "reliability_diagram_path": diagram_path,
    }


def build_report(
    predictions_by_dataset: dict,
    *,
    calib_split_rows=None,
    manifest=None,
    price_table=None,
    verifier_id: str = "A",
    bins: int = 15,
    diagram_path: str = "results/verifier/reports/reliability.png",
) -> dict:
    """Assemble cached predictions into the `report.json` structure.

    `predictions_by_dataset` maps a dataset name -> list of prediction rows. The
    ``contested`` key (if present) is scored *separately* and never mixed into
    the 3-way public-set tables. `calib_split_rows` is the held-out calibration
    partition (binary-collapsed); when absent, calibration fits on the pooled
    public rows. `manifest` carries per-dataset id/revision/seed.
    """
    price_table = price_table or {}
    manifest = manifest or {}

    public = {ds: rows for ds, rows in predictions_by_dataset.items()
              if ds != CONTESTED_DATASET}
    contested_rows = predictions_by_dataset.get(CONTESTED_DATASET)

    datasets = {ds: _metric_table(rows) for ds, rows in public.items()}

    report_manifest = {}
    for ds, rows in public.items():
        meta = manifest.get(ds, {})
        report_manifest[ds] = {
            "id": meta.get("id"),
            "revision": meta.get("revision"),
            "seed": meta.get("seed"),
            "n": len(rows),
            "gold_counts": _gold_counts(rows),
        }

    # Calibration: pool all public rows for the eval signal; fit on the calib split.
    pooled = [r for rows in public.values() for r in rows]
    calibration = _calibration_block(
        pooled, calib_split_rows, bins=bins, diagram_path=diagram_path)

    contested = _metric_table(contested_rows) if contested_rows else None

    cost = {ds: cost_summary(rows, price_table, verifier_id=verifier_id)
            for ds, rows in public.items()}

    return {
        "verifier_id": verifier_id,
        "manifest": report_manifest,
        "datasets": datasets,
        "confusion_labels": ["supported", "refuted", "insufficient", "contested"],
        "calibration": calibration,
        "contested": contested,
        "cost": cost,
    }


# ----------------------------------------------------------------- A/B diff


def _per_class_delta(a: dict, b: dict) -> dict:
    out = {}
    for lab in set(a) | set(b):
        pa, pb = a.get(lab, {}), b.get(lab, {})
        out[lab] = {
            "f1_delta": pb.get("f1", 0.0) - pa.get("f1", 0.0),
            "precision_delta": pb.get("precision", 0.0) - pa.get("precision", 0.0),
            "recall_delta": pb.get("recall", 0.0) - pa.get("recall", 0.0),
        }
    return out


def ab_diff(report_a: dict, report_b: dict) -> dict:
    """Per-dataset deltas (B - A) on the decisive axes: macro-F1, accuracy, the
    grounding-relevant per-class F1/P/R, ECE-after, and cost/latency. Built now;
    exercised when Verifier B lands."""
    da, db = report_a["datasets"], report_b["datasets"]
    datasets = {}
    for ds in set(da) | set(db):
        ta, tb = da.get(ds, {}), db.get(ds, {})
        datasets[ds] = {
            "macro_f1_delta": tb.get("macro_f1", 0.0) - ta.get("macro_f1", 0.0),
            "accuracy_delta": tb.get("accuracy", 0.0) - ta.get("accuracy", 0.0),
            "per_class": _per_class_delta(
                ta.get("per_class", {}), tb.get("per_class", {})),
        }

    ca, cb = report_a["calibration"], report_b["calibration"]
    calibration = {
        "ece_after_delta": cb.get("ece_after", 0.0) - ca.get("ece_after", 0.0),
        "ece_before_delta": cb.get("ece_before", 0.0) - ca.get("ece_before", 0.0),
        "brier_after_delta": cb.get("brier_after", 0.0) - ca.get("brier_after", 0.0),
    }

    costa, costb = report_a["cost"], report_b["cost"]
    cost = {}
    for ds in set(costa) | set(costb):
        xa, xb = costa.get(ds, {}), costb.get(ds, {})
        cost[ds] = {
            "mean_cost_delta": xb.get("mean_cost", 0.0) - xa.get("mean_cost", 0.0),
            "mean_latency_ms_delta": (
                xb.get("mean_latency_ms", 0.0) - xa.get("mean_latency_ms", 0.0)),
        }

    return {
        "a": report_a.get("verifier_id"),
        "b": report_b.get("verifier_id"),
        "datasets": datasets,
        "calibration": calibration,
        "cost": cost,
    }


# ----------------------------------------------------------------- markdown render


_LABELS = ("supported", "refuted", "insufficient", "contested")


def _fmt(x, nd=3) -> str:
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else str(x)


def _metric_table_md(name: str, table: dict) -> list[str]:
    lines = [f"### {name}", "",
             f"macro-F1: **{_fmt(table['macro_f1'])}** | "
             f"accuracy: **{_fmt(table['accuracy'])}** | n: {table['n']}", "",
             "| class | precision | recall | f1 | support |",
             "|---|---|---|---|---|"]
    for lab in _LABELS:
        pc = table["per_class"].get(lab)
        if not pc:
            continue
        lines.append(f"| {lab} | {_fmt(pc['precision'])} | {_fmt(pc['recall'])} | "
                     f"{_fmt(pc['f1'])} | {pc['support']} |")
    lines += ["", _confusion_md(table["confusion"]), ""]
    return lines


def _confusion_md(conf: dict) -> str:
    m = conf["matrix"]
    header = "| gold\\pred | " + " | ".join(_LABELS) + " |"
    sep = "|" + "---|" * (len(_LABELS) + 1)
    rows = [header, sep]
    for g in _LABELS:
        rows.append("| " + g + " | " + " | ".join(str(m[g][p]) for p in _LABELS) + " |")
    fc = conf["false_confidence"]
    rows.append("")
    rows.append("**Confusion matrix** (false-confidence cells: "
                f"`insufficient_to_supported`={fc['insufficient_to_supported']}, "
                f"`refuted_to_supported`={fc['refuted_to_supported']})")
    return "\n".join(rows)


def render_report_md(report: dict) -> str:
    """Readable Markdown rendering of `report.json`."""
    out = [f"# Verifier-eval report — {report.get('verifier_id', '?')}", ""]

    out += ["## Manifest", "",
            "| dataset | id | revision | seed | n | gold counts |",
            "|---|---|---|---|---|---|"]
    for ds, m in report["manifest"].items():
        gc = ", ".join(f"{k}={v}" for k, v in m["gold_counts"].items())
        out.append(f"| {ds} | {m['id']} | {m['revision']} | {m['seed']} | {m['n']} | {gc} |")
    out.append("")

    out += ["## Per-dataset metrics", ""]
    for ds, table in report["datasets"].items():
        out += _metric_table_md(ds, table)

    cal = report["calibration"]
    out += ["## Calibration", "",
            f"ECE before -> after: **{_fmt(cal['ece_before'])} -> {_fmt(cal['ece_after'])}**  "
            f"(Brier {_fmt(cal['brier_before'])} -> {_fmt(cal['brier_after'])})",
            "",
            f"Collapse rule: `{cal['collapse_rule']}`  "
            f"(fit on disjoint split: {cal['fit_on_disjoint_split']}, "
            f"n_fit={cal['n_fit']}, n_eval={cal['n_eval']})",
            "",
            f"Reliability diagram: `{cal['reliability_diagram_path']}`", ""]

    if report.get("contested"):
        out += ["## Contested conflict-subset (scored separately)", ""]
        out += _metric_table_md("contested", report["contested"])

    out += ["## Cost / latency", "",
            "| dataset | n | total model calls | total cost | mean cost | mean latency (ms) |",
            "|---|---|---|---|---|---|"]
    for ds, c in report["cost"].items():
        out.append(f"| {ds} | {c['n']} | {c['total_model_calls']} | "
                   f"{_fmt(c['total_cost'], 4)} | {_fmt(c['mean_cost'], 4)} | "
                   f"{_fmt(c['mean_latency_ms'], 1)} |")
    out.append("")
    return "\n".join(out)


def save_reliability_diagram(bins_before, bins_after, path: str) -> None:  # pragma: no cover - plotting
    """Render the reliability diagram from pre-computed pure bin data.

    Side-effecting (matplotlib + file write); the bin computation itself is the
    pure, unit-tested `reliability_bins`. Imported lazily so the eval extra
    (matplotlib) is only required at plot time.
    """
    import os

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="perfect")
    for bins_data, label in ((bins_before, "before"), (bins_after, "after")):
        xs = [b["mean_conf"] for b in bins_data]
        ys = [b["accuracy"] for b in bins_data]
        ax.plot(xs, ys, marker="o", label=label)
    ax.set_xlabel("predicted confidence")
    ax.set_ylabel("empirical accuracy")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend()
    ax.set_title("Reliability diagram (supported-vs-not)")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
