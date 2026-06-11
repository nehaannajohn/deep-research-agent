"""CLI harness + verifier A/B registry for the Layer-1 verifier-eval.

Arg parsing and the registry are pure/testable. The live orchestration
(load datasets -> run_predictions -> build_report -> write files + plot) is
`# pragma: no cover`: it needs Bedrock + the downloaded benchmarks, exercised
only in the manual Phase-6 run.

A/B readiness: selecting which verifier to run is a registry keyed by id. `A`
builds the selected ensemble + the three solos exactly as
`experiments/verifier_comparison.py` does; `B` is reserved for the future
DeBERTa cross-encoder and raises a clear NotImplementedError until that slice
lands. Tests register a fake under an arbitrary id to prove drop-in symmetry.

See docs/superpowers/specs/2026-06-11-layer1-verifier-eval-design.md §7-8.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass


# ----------------------------------------------------------------- registry


def _build_A(config):  # pragma: no cover - live Bedrock wiring
    """The selected ensemble + 3 solos, built as in verifier_comparison.py."""
    import os

    from dra.llm.bedrock import BedrockChat
    from dra.verify.ensemble import EnsembleVerifier
    from dra.verify.llm_judge import LLMJudgeVerifier

    region = os.environ.get("AWS_REGION", "us-east-1")
    ensemble = EnsembleVerifier(
        [LLMJudgeVerifier(BedrockChat(m, region=region), n_samples=1)
         for m in config.verifier_models]
    )
    return ensemble


def _build_B(config):
    """Reserved for the future fine-tuned DeBERTa cross-encoder (Verifier B)."""
    raise NotImplementedError(
        "Verifier B (DeBERTa cross-encoder) is a separate slice; register it "
        "under id 'B' when it lands — no harness change needed (A/B-ready)."
    )


# id -> factory(config) -> Verifier. Extensible at runtime via register_verifier.
REGISTRY: dict = {
    "A": _build_A,
    "B": _build_B,
}


def register_verifier(verifier_id: str, factory) -> None:
    """Register (or override) a verifier factory under `verifier_id`.

    Lets tests inject a fake `Verifier` and lets Verifier B register itself
    without touching the harness."""
    REGISTRY[verifier_id] = factory


def build_verifier(verifier_id: str, *, config):
    """Build the verifier registered under `verifier_id` (KeyError if unknown)."""
    if verifier_id not in REGISTRY:
        raise KeyError(f"unknown verifier id {verifier_id!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[verifier_id](config)


# ----------------------------------------------------------------- CLI


@dataclass
class HarnessConfig:
    verifier: str
    datasets: list
    sample_seed: int
    calib_split: float
    refresh: bool


def parse_args(argv) -> HarnessConfig:
    """Parse the CLI argv into a HarnessConfig (pure, testable; no live run)."""
    ap = argparse.ArgumentParser(prog="dra-verifier-eval")
    ap.add_argument("--verifier", required=True,
                    help="registry id (A = ensemble + solos; B reserved)")
    ap.add_argument("--datasets", required=True,
                    help="comma-separated, e.g. fever,scifact[,vitaminc]")
    ap.add_argument("--sample-seed", type=int, default=13)
    ap.add_argument("--calib-split", type=float, default=0.5,
                    help="held-out fraction for the calibration partition")
    ap.add_argument("--refresh", action="store_true",
                    help="force re-prediction, ignoring the cache")
    ns = ap.parse_args(argv)
    return HarnessConfig(
        verifier=ns.verifier,
        datasets=[d.strip() for d in ns.datasets.split(",") if d.strip()],
        sample_seed=ns.sample_seed,
        calib_split=ns.calib_split,
        refresh=ns.refresh,
    )


def main(argv=None) -> int:  # pragma: no cover - live orchestration
    """Live entrypoint: load datasets -> run_predictions -> build_report ->
    write report.{json,md} + reliability diagram. Needs AWS creds + benchmarks."""
    import json
    import os

    from dra.config import load_config
    from dra.eval.loaders.fever import load_fever
    from dra.eval.loaders.scifact import load_scifact
    from dra.eval.report import build_report, render_report_md, save_reliability_diagram
    from dra.eval.runner import run_predictions

    cfg = parse_args(argv)
    app_config = load_config()
    verifier = build_verifier(cfg.verifier, config=app_config)

    loaders = {"fever": load_fever, "scifact": load_scifact}
    cache_dir = "eval/results/verifier/predictions"
    out_dir = "eval/results/verifier/reports"
    os.makedirs(out_dir, exist_ok=True)

    predictions: dict = {}
    manifest: dict = {}
    for ds in cfg.datasets:
        examples = loaders[ds](seed=cfg.sample_seed)
        rows = run_predictions(
            verifier, examples,
            verifier_id=cfg.verifier, dataset=ds, split="test",
            dataset_revision="latest", sample_seed=cfg.sample_seed,
            cache_dir=cache_dir, refresh=cfg.refresh,
        )
        predictions[ds] = rows
        manifest[ds] = {"id": ds, "revision": "latest", "seed": cfg.sample_seed}

    diagram_path = os.path.join(out_dir, f"reliability_{cfg.verifier}.png")
    report = build_report(
        predictions, manifest=manifest, verifier_id=cfg.verifier,
        diagram_path=diagram_path,
    )
    save_reliability_diagram(
        report["calibration"]["reliability_bins"],
        report["calibration"]["reliability_bins_after"],
        diagram_path,
    )
    with open(os.path.join(out_dir, f"report_{cfg.verifier}.json"), "w") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(out_dir, f"report_{cfg.verifier}.md"), "w") as f:
        f.write(render_report_md(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
