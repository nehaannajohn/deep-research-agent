"""Reporter + CLI harness + A/B registry tests: fakes only, no Bedrock/network."""
from __future__ import annotations

from dra.eval.harness import (
    REGISTRY,
    build_verifier,
    parse_args,
    register_verifier,
)
from dra.eval.report import (
    ab_diff,
    build_report,
    p_supported,
    render_report_md,
)


def _row(example_id, gold, pred, confidence, *, model_calls=3, latency_ms=10.0,
         recommendation="accept", votes=None):
    """A prediction row in the runner's documented shape."""
    return {
        "example_id": example_id,
        "gold": gold,
        "pred": pred,
        "confidence": confidence,
        "recommendation": recommendation,
        "votes": votes or {"a": 2, "b": 1},
        "latency_ms": latency_ms,
        "model_calls": model_calls,
    }


def _fever_rows():
    """A hand-built 3-way fixture with a known confusion structure.

    gold/pred (5 rows):
      ex0 supported   -> supported    (correct)
      ex1 supported   -> refuted      (miss)
      ex2 refuted     -> supported    (FALSE CONFIDENCE: refuted_to_supported)
      ex3 insufficient-> supported    (FALSE CONFIDENCE: insufficient_to_supported)
      ex4 insufficient-> contested    (off-axis: contested pred on 3-way gold)
    """
    return [
        _row("ex0", "supported", "supported", 0.9),
        _row("ex1", "supported", "refuted", 0.7),
        _row("ex2", "refuted", "supported", 0.8),
        _row("ex3", "insufficient", "supported", 0.6),
        _row("ex4", "insufficient", "contested", 0.55),
    ]


# ---------------------------------------------------------------- binary collapse


def test_p_supported_collapse_rule():
    assert p_supported("supported", 0.9) == 0.9
    assert abs(p_supported("refuted", 0.8) - 0.2) < 1e-12
    assert abs(p_supported("insufficient", 0.6) - 0.4) < 1e-12
    assert abs(p_supported("contested", 0.55) - 0.45) < 1e-12


# ---------------------------------------------------------------- report assembly


def test_report_macro_f1_is_three_way_and_excludes_contested():
    rep = build_report({"fever": _fever_rows()})
    ds = rep["datasets"]["fever"]
    # gold only has supported/refuted/insufficient -> macro averages over 3 classes;
    # a `contested` prediction is never folded in (contested absent from y_true).
    assert "contested" not in ds["per_class"] or ds["per_class"]["contested"]["support"] == 0
    present = [lab for lab, v in ds["per_class"].items() if v["support"] > 0]
    assert set(present) == {"supported", "refuted", "insufficient"}
    assert 0.0 <= ds["macro_f1"] <= 1.0


def test_report_confusion_and_false_confidence_cells():
    rep = build_report({"fever": _fever_rows()})
    conf = rep["datasets"]["fever"]["confusion"]
    m = conf["matrix"]
    assert m["supported"]["supported"] == 1
    assert m["supported"]["refuted"] == 1
    assert m["refuted"]["supported"] == 1
    assert m["insufficient"]["supported"] == 1
    assert m["insufficient"]["contested"] == 1
    # named false-confidence cells surfaced
    assert conf["false_confidence"]["refuted_to_supported"] == 1
    assert conf["false_confidence"]["insufficient_to_supported"] == 1


def test_report_per_class_prf_known_values():
    rep = build_report({"fever": _fever_rows()})
    pc = rep["datasets"]["fever"]["per_class"]
    # supported: tp=1 (ex0), fp=2 (ex2,ex3), fn=1 (ex1) -> P=1/3, R=1/2
    assert abs(pc["supported"]["precision"] - 1 / 3) < 1e-9
    assert abs(pc["supported"]["recall"] - 0.5) < 1e-9
    # refuted: tp=0 -> 0
    assert pc["refuted"]["f1"] == 0.0
    assert rep["datasets"]["fever"]["accuracy"] == 1 / 5


def test_report_manifest_has_gold_counts():
    manifest = {"fever": {"id": "copenlu/fever", "revision": "rev1", "seed": 13}}
    rep = build_report({"fever": _fever_rows()}, manifest=manifest)
    m = rep["manifest"]["fever"]
    assert m["id"] == "copenlu/fever"
    assert m["revision"] == "rev1"
    assert m["seed"] == 13
    assert m["gold_counts"] == {"supported": 2, "refuted": 1, "insufficient": 2}


# ---------------------------------------------------------------- calibration block


def _miscalibrated_rows(n=40):
    """Overconfident fixture: high confidence but only half correct -> high ECE."""
    rows = []
    for i in range(n):
        # all predict supported at 0.9; half are actually supported, half refuted
        gold = "supported" if i % 2 == 0 else "refuted"
        rows.append(_row(f"c{i}", gold, "supported", 0.9))
    return rows


def test_calibration_block_before_after_and_bins():
    rows = _fever_rows()
    rep = build_report({"fever": rows}, calib_split_rows=_miscalibrated_rows())
    cal = rep["calibration"]
    assert "ece_before" in cal and "ece_after" in cal
    assert "brier_before" in cal and "brier_after" in cal
    # deliberately miscalibrated -> recalibration should not worsen ECE
    assert cal["ece_after"] <= cal["ece_before"] + 1e-9
    # reliability bin data is pure + present, plus the intended png path
    assert isinstance(cal["reliability_bins"], list)
    assert cal["reliability_bins"], "expected non-empty bin data"
    for b in cal["reliability_bins"]:
        assert {"lo", "hi", "count", "mean_conf", "accuracy"} <= set(b)
    assert isinstance(cal["reliability_diagram_path"], str)
    assert cal["collapse_rule"]  # auditable collapse rule recorded


def test_calibration_falls_back_to_eval_rows_when_no_split():
    rep = build_report({"fever": _fever_rows()})
    assert "ece_before" in rep["calibration"]


def test_calibration_disjoint_split_when_calib_split_set():
    rows = _fever_rows() * 4  # enough rows to partition
    rep = build_report({"fever": rows}, calib_split=0.5)
    c = rep["calibration"]
    assert c["fit_on_disjoint_split"] is True
    assert c["n_fit"] >= 1 and c["n_eval"] >= 1
    assert c["n_fit"] + c["n_eval"] == len(rows)


# ---------------------------------------------------------------- contested subset


def _contested_rows():
    """contested-shaped rows scored separately (gold all contested)."""
    return [
        _row("contested:0", "contested", "contested", 0.7),
        _row("contested:1", "contested", "supported", 0.6),
        _row("contested:2", "contested", "contested", 0.8),
    ]


def test_contested_subset_reported_separately():
    rep = build_report(
        {"fever": _fever_rows(), "contested": _contested_rows()}
    )
    # contested goes into its own block, NOT into the 3-way datasets tables
    assert "contested" not in rep["datasets"]
    cs = rep["contested"]
    assert cs["n"] == 3
    # recall on contested = 2/3 (two of three predicted contested)
    assert abs(cs["per_class"]["contested"]["recall"] - 2 / 3) < 1e-9
    assert "macro_f1" in cs
    assert "confusion" in cs


def test_no_contested_block_when_absent():
    rep = build_report({"fever": _fever_rows()})
    assert rep["contested"] is None


# ---------------------------------------------------------------- cost / latency


def test_cost_and_latency_block():
    rep = build_report(
        {"fever": _fever_rows()},
        manifest=None,
        price_table={"A": 0.01},
        verifier_id="A",
    )
    cost = rep["cost"]["fever"]
    assert cost["n"] == 5
    assert cost["total_model_calls"] == 15  # 5 rows * 3 calls
    assert abs(cost["total_cost"] - 0.15) < 1e-9
    assert cost["mean_latency_ms"] == 10.0


# ---------------------------------------------------------------- markdown render


def test_render_report_md_contains_sections():
    rep = build_report(
        {"fever": _fever_rows(), "contested": _contested_rows()},
        calib_split_rows=_miscalibrated_rows(),
        manifest={"fever": {"id": "x", "revision": "r", "seed": 1}},
        price_table={"A": 0.01},
        verifier_id="A",
    )
    md = render_report_md(rep)
    assert isinstance(md, str)
    assert "# " in md  # has a heading
    assert "fever" in md
    assert "Confusion" in md or "confusion" in md
    assert "ECE" in md
    assert "Contested" in md or "contested" in md
    assert "Cost" in md or "cost" in md
    assert "refuted_to_supported" in md


# ---------------------------------------------------------------- A/B symmetry + diff


def test_ab_shape_symmetry_via_fake_registry():
    # An "A"-shaped report from canned rows.
    rep_a = build_report({"fever": _fever_rows()}, verifier_id="A")
    # A "B"-shaped report from a different fake's canned rows: identical key structure.
    rep_b = build_report({"fever": _fever_rows_b()}, verifier_id="B")

    def shape(d):
        if isinstance(d, dict):
            return {k: shape(v) for k, v in sorted(d.items())}
        if isinstance(d, list):
            return [shape(d[0])] if d else []
        return type(d).__name__

    assert shape(rep_a) == shape(rep_b)


def _fever_rows_b():
    # Different numbers, same shape (a drop-in Verifier B's predictions).
    return [
        _row("ex0", "supported", "supported", 0.6),
        _row("ex1", "supported", "supported", 0.55),
        _row("ex2", "refuted", "refuted", 0.7),
        _row("ex3", "insufficient", "insufficient", 0.65),
        _row("ex4", "insufficient", "supported", 0.5),
    ]


def test_ab_diff_deltas():
    rep_a = build_report({"fever": _fever_rows()}, price_table={"A": 0.01}, verifier_id="A")
    rep_b = build_report({"fever": _fever_rows_b()}, price_table={"B": 0.0}, verifier_id="B")
    diff = ab_diff(rep_a, rep_b)
    d = diff["datasets"]["fever"]
    # B is strictly better on macro-F1 here (B gets 4/5 right vs A's 1/5)
    assert d["macro_f1_delta"] == rep_b["datasets"]["fever"]["macro_f1"] - rep_a["datasets"]["fever"]["macro_f1"]
    assert d["macro_f1_delta"] > 0
    assert "accuracy_delta" in d
    assert "per_class" in d  # grounding-relevant per-class deltas
    assert "ece_after_delta" in diff["calibration"]
    assert "mean_cost_delta" in diff["cost"]["fever"]


# ---------------------------------------------------------------- registry / harness


class _FakeVerifier:
    def verify(self, claim, passages):  # pragma: no cover - not invoked here
        raise NotImplementedError


def test_registry_has_A_and_B_reserved():
    assert "A" in REGISTRY
    # B is reserved -> raising factory until the DeBERTa slice lands
    try:
        build_verifier("B", config=None)
        raised = False
    except NotImplementedError:
        raised = True
    assert raised


def test_register_fake_verifier_and_build():
    register_verifier("FAKE", lambda config: _FakeVerifier())
    v = build_verifier("FAKE", config=None)
    assert isinstance(v, _FakeVerifier)


def test_cli_arg_parsing():
    cfg = parse_args([
        "--verifier", "A",
        "--datasets", "fever,scifact",
        "--sample-seed", "7",
        "--calib-split", "0.5",
        "--refresh",
    ])
    assert cfg.verifier == "A"
    assert cfg.datasets == ["fever", "scifact"]
    assert cfg.sample_seed == 7
    assert cfg.calib_split == 0.5
    assert cfg.refresh is True


def test_cli_arg_parsing_defaults():
    cfg = parse_args(["--verifier", "A", "--datasets", "fever"])
    assert cfg.datasets == ["fever"]
    assert cfg.refresh is False
