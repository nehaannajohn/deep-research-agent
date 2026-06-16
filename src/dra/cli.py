"""Run the Deep Research Agent end-to-end on a single query.

    python -m dra.cli "your question"            # run, print the report + a summary
    python -m dra.cli "your question" --save out.md
    python -m dra.cli --quiet "your question"    # suppress per-stage progress

Makes live Bedrock + Exa calls (set credentials in `.env` — see `.env.example`), so a
run typically takes 1–3 minutes. The verifier is the configured in-loop ensemble; the
trained cross-encoder (v0) needs a GPU checkpoint and is exercised via the eval drivers.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

DEFAULT_QUERY = "What are the real-world risks and benefits of using synthetic data to train LLMs?"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m dra.cli",
        description="Run the Deep Research Agent end-to-end on one query (live Bedrock + Exa).")
    ap.add_argument("query", nargs="?", default=DEFAULT_QUERY, help="the research question")
    ap.add_argument("--verifier", choices=["ensemble", "v0", "v1"], default="ensemble",
                    help="in-loop verifier: 'ensemble' = 3-model LLM panel (default); "
                         "'v0'/'v1' = trained DeBERTa-v3 cross-encoder (needs torch + checkpoint)")
    ap.add_argument("--save", metavar="PATH", help="write the report markdown to PATH")
    ap.add_argument("--quiet", action="store_true", help="suppress per-stage progress lines")
    a = ap.parse_args(argv if argv is not None else sys.argv[1:])

    from dra.config import load_config
    from dra.loop import build_deps, run_query

    cfg = load_config()

    # Pre-flight: fail fast with a clear message instead of a deep stack trace.
    missing = []
    if not cfg.exa_key:
        missing.append("EXA_API_KEY (retrieval)")
    if not cfg.roles.get("generator"):
        missing.append("BEDROCK_GENERATOR_MODEL")
    if a.verifier == "ensemble" and not cfg.verifier_models and not cfg.roles.get("inloop_judge"):
        missing.append("BEDROCK_VERIFIER_MODELS or BEDROCK_INLOOP_JUDGE_MODEL")
    if missing:
        print("Missing required configuration (set these in .env — see .env.example):",
              file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 2

    # The trained cross-encoder verifier needs torch/transformers + a local checkpoint.
    if a.verifier in ("v0", "v1"):
        import importlib.util
        import os
        problems = []
        if importlib.util.find_spec("torch") is None:
            problems.append("torch/transformers not installed  →  pip install torch transformers "
                            "sentencepiece protobuf")
        ckpt = os.path.join("eval", "verifier_b_models", a.verifier, "best")
        if not os.path.isdir(ckpt):
            problems.append(f"checkpoint missing at {ckpt}/  →  it lives on the EC2 eval host; "
                            "pull it locally (or run this on that host)")
        if problems:
            print(f"Cannot use --verifier {a.verifier}:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 2

    if a.verifier in ("v0", "v1"):
        verifier_desc = f"DeBERTa-v3 cross-encoder ({a.verifier}, Platt-calibrated)"
    else:
        verifier_desc = ("ensemble {" + ", ".join(cfg.verifier_models) + "}"
                         if cfg.verifier_models else cfg.roles["inloop_judge"])
    bar = "=" * 72
    print(bar)
    print("Deep Research Agent — single run")
    print(f"  Query     : {a.query}")
    print(f"  Region    : {cfg.region}")
    print(f"  Generator : {cfg.roles['generator']}")
    print(f"  Verifier  : {verifier_desc}")
    print("  (live Bedrock + Exa calls — typically 1–3 min)")
    print(bar, flush=True)

    t0 = time.time()

    def progress(event, **kw):
        if a.quiet:
            return
        dt = time.time() - t0
        if event == "plan":
            print(f"[{dt:5.1f}s] plan          → {len(kw['subquestions'])} sub-question(s)")
            for i, sq in enumerate(kw["subquestions"], 1):
                print(f"            {i}. {sq}")
        elif event == "retrieve":
            print(f"[{dt:5.1f}s] retrieve      → {kw['n_passages']:2d} passages · {kw['subq'][:58]}")
        elif event == "verify":
            print(f"[{dt:5.1f}s] synth+verify  → {kw['n_claims']:2d} claim(s)  · {kw['subq'][:58]}")
        elif event == "contradiction":
            print(f"[{dt:5.1f}s] contradiction → {kw['n_contradictions']} contested pair(s)")
        elif event == "compose":
            print(f"[{dt:5.1f}s] compose       → report ready", flush=True)

    try:
        deps = build_deps(cfg, verifier=a.verifier)
        report = run_query(a.query, deps, progress=progress)
    except Exception as exc:  # noqa: BLE001 — surface a clean message for CLI users
        print(f"\nRun failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    elapsed = time.time() - t0

    print("\n" + bar + "\nREPORT\n" + bar)
    print(report.report_markdown)

    vc = Counter(c.verdict for c in report.claims)
    m = report.metadata
    print("\n" + bar + "\nSUMMARY\n" + bar)
    print(f"  Claims     : {len(report.claims)}  ("
          + ", ".join(f"{k} {v}" for k, v in vc.most_common()) + ")")
    if m.overall_confidence is not None:
        print(f"  Confidence : {m.overall_confidence:.3f}    Coverage: {m.coverage}")
    print(f"  Sources    : {len(report.sources)}")
    if m.disclaimers:
        print(f"  Disclaimers: {len(m.disclaimers)}")
    print(f"  Elapsed    : {elapsed:.1f}s")

    if a.save:
        with open(a.save, "w", encoding="utf-8") as f:
            f.write(report.report_markdown)
        print(f"\nSaved report → {a.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
