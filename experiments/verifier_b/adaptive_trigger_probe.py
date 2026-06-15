"""Adaptive-retrieval feasibility probe: how often would the confidence gate fire?

Before building the adaptive loop, measure — on a DRA-Bench sample — how often the
v0 verifier's *calibrated predicted-label confidence* falls below a threshold τ
(i.e. how often we'd re-retrieve). Uses the SAME frozen upstream as the Layer-2
freeze mode: re-verify the canonical `corrected_verifier` claims with v0 + the new
PER-LABEL calibrators (GPU only — no Bedrock, no re-generation), then aggregate.

The gate fires per SUB-QUESTION (a sub-question's confidence = the min over its
claims — the weakest claim), which is the unit the adaptive loop would repair. We
also report claim-level rates and, among low-confidence claims, the label mix
(is it insufficient/refuted/contested — the cases retrieval can actually help?).

`summarize_triggers` is pure and unit-tested; `run()` is the live (GPU) driver.

Usage (EC2, .venv-train):
  .venv-train/bin/python -m experiments.verifier_b.adaptive_trigger_probe \
      --variant v0 --canon-dir eval/results/pipeline/report_cache --per-type 10
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict


def summarize_triggers(rows: list, taus=(0.5, 0.6, 0.7)) -> dict:
    """rows: dicts with type, item_id, section, label, conf. Returns claim-level
    and sub-question-level trigger rates (fraction with conf < τ) overall and by
    type, plus the label mix among low-confidence claims at the middle τ.

    Sub-question confidence = min over that (item, section)'s claims.
    """
    taus = tuple(taus)

    def _rate(confs, t):
        return round(sum(1 for c in confs if c < t) / len(confs), 3) if confs else None

    def _block(rws):
        confs = [r["conf"] for r in rws]
        return {"n": len(confs),
                "mean_conf": round(sum(confs) / len(confs), 3) if confs else None,
                "trigger_rate": {f"{t:.2f}": _rate(confs, t) for t in taus}}

    types = sorted({r["type"] for r in rows})

    # sub-question aggregation: weakest claim per (item, section)
    subq = defaultdict(lambda: {"type": None, "confs": []})
    for r in rows:
        k = (r["item_id"], r["section"])
        subq[k]["type"] = r["type"]
        subq[k]["confs"].append(r["conf"])
    subq_rows = [{"type": v["type"], "conf": min(v["confs"])} for v in subq.values()]

    mid = taus[len(taus) // 2]
    low = [r for r in rows if r["conf"] < mid]
    by_label = defaultdict(int)
    for r in low:
        by_label[r["label"]] += 1

    return {
        "taus": list(taus),
        "claim_level": {
            "overall": _block(rows),
            "by_type": {ty: _block([r for r in rows if r["type"] == ty]) for ty in types},
        },
        "subquestion_level": {
            "overall": _block(subq_rows),
            "by_type": {ty: _block([r for r in subq_rows if r["type"] == ty]) for ty in types},
        },
        "low_conf_label_mix": {"tau": mid, "n_low_claims": len(low), "by_label": dict(by_label)},
    }


def _build_index(canon_dir: str) -> dict:  # pragma: no cover - disk
    """query -> path for the canonical corrected_verifier reports."""
    canon = os.path.join(canon_dir, "corrected_verifier")
    index = {}
    for fn in os.listdir(canon):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(canon, fn)
        try:
            index[json.load(open(p))["query"]] = p
        except Exception:
            pass
    return index


def run(variant="v0", canon_dir="eval/results/pipeline/report_cache",
        per_type=10, taus=(0.5, 0.6, 0.7)) -> dict:  # pragma: no cover - live (GPU)
    from dra.eval.pipeline.datasets.dra_bench import load_dra_bench
    from dra.schemas import ResearchReport
    from dra.verify.cross_encoder import CrossEncoderVerifier
    from experiments.run_pipeline_eval import _load_platt
    from experiments.verifier_b.evaluate import _bind_score_fn

    ckpt = f"eval/verifier_b_models/{variant}/best"
    verifier = CrossEncoderVerifier(score_fn=_bind_score_fn(ckpt), calibrators=_load_platt(variant))

    items = load_dra_bench()
    index = _build_index(canon_dir)

    pools = defaultdict(list)
    for it in items:
        if it.query in index:
            pools[it.meta.get("type") or it.id.split("-")[1]].append(it)
    sampled = []
    for ty in sorted(pools):
        sampled += sorted(pools[ty], key=lambda x: x.id)[:per_type]
    print(f"[probe] sampled {len(sampled)} items "
          f"({ {ty: min(len(p), per_type) for ty, p in pools.items()} }) "
          f"from {len(index)} canonical reports", flush=True)

    rows = []
    for it in sampled:
        ty = it.meta.get("type") or it.id.split("-")[1]
        rep = ResearchReport.model_validate_json(open(index[it.query]).read())
        sources = {s.source_id: s for s in rep.sources}
        for c in rep.claims:
            cited = [sources[cit.source_id] for cit in c.citations if cit.source_id in sources]
            if not cited:
                continue
            r = verifier.verify(c.text, cited)
            rows.append({"type": ty, "item_id": it.id, "section": c.section,
                         "label": r.label, "conf": float(r.confidence)})

    res = summarize_triggers(rows, taus)
    res["meta"] = {"variant": variant, "n_items": len(sampled), "n_claims": len(rows),
                   "per_type": per_type}
    out = f"eval/results/verifier_b/{variant}/adaptive_trigger_probe.json"
    json.dump(res, open(out, "w"), indent=2)
    print(json.dumps(res, indent=2))
    print(f"[probe] wrote {out}", flush=True)
    return res


def main(argv=None):  # pragma: no cover - live
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="v0", choices=["v0", "v1"])
    ap.add_argument("--canon-dir", default="eval/results/pipeline/report_cache")
    ap.add_argument("--per-type", type=int, default=10)
    ap.add_argument("--taus", type=float, nargs="+", default=[0.5, 0.6, 0.7])
    a = ap.parse_args(argv)
    run(a.variant, a.canon_dir, a.per_type, tuple(a.taus))


if __name__ == "__main__":
    main()
