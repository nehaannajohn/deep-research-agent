"""Live driver for the ±verification ablation (Layer-2 pipeline eval).

Runs our full pipeline over DRA-Bench with the in-loop verifier ON vs OFF and
scores every Layer-2 axis on each arm's reports. Report caching decouples the
expensive pipeline pass from re-scoring: a generated `ResearchReport` is cached
under ``<cache>/<arm>/<id>.json`` and reused on later passes, so re-running only
re-scores (cheap) unless ``--refresh`` is given.

The ±verifier seam (loop.py):
    `dra.loop.run_query` always verifies each claim and composes the report with
    ``with_verification=True``. The "with_verifier" arm is exactly that —
    ``build_deps(cfg)`` with the ensemble verifier. The "without_verifier" arm
    reuses the *same* generator / search / decomposition but (a) injects a
    PASSTHROUGH verifier so every claim stays ``unverified`` (no verdict /
    confidence / disclaimers) and (b) composes with ``with_verification=False`` —
    i.e. `compose_report(..., with_verification=False)` — so claims are surfaced
    UNVERIFIED. We replicate loop.run_query's plan→route→search→synthesize flow
    in `_run_query_without_verifier` rather than mutating the shared `run_query`,
    keeping the live pipeline untouched. The orchestrator + scorers are identical
    across arms, so the only difference measured is verification.

Independence: the Layer-2 grounding judge is a panel-family model (default
``openai.gpt-oss-120b-1:0``), deliberately NOT the in-loop verifier ensemble —
re-using the verifier to score grounding would only measure its self-consistency.

Live: needs AWS creds + EXA_API_KEY. The live wiring (`build_deps`, Bedrock, Exa,
the no-verifier flow) is ``# pragma: no cover``; the orchestration + report-cache
logic it drives is unit-tested in `tests/test_eval_pipeline_harness.py`.

Run on EC2:
    .venv/bin/python -m experiments.run_pipeline_eval --limit 3 --arm both
"""
from __future__ import annotations

import os

ARMS = ("with_verifier", "without_verifier")

# Grounding judge: a panel-family model independent of the in-loop verifier
# ensemble (spec §4). Non-Anthropic on purpose; override via the panel config.
DEFAULT_GROUNDING_MODEL = "openai.gpt-oss-120b-1:0"

FABLE_REFERENCE_DIR = "eval/dra_bench/reference_reports"  # Sonnet-on-Bedrock gold (Fable hit a credit/data-sharing wall); the 75 Fable refs stay under fable_references/ as a spot-check


def fable_reference_lookup(reference_dir=FABLE_REFERENCE_DIR, decomposer=None):
    """Build a ``reference_lookup`` closure: ``item_id -> list[str] | None``.

    Returns parsed Fable reference claim texts when
    ``<reference_dir>/<id>.md`` exists, else ``None`` (similarity skipped — the
    references are still generating). Pure aside from the disk read + the
    injected ``decomposer``; the parse reuses ``gold.fable_reference``.
    """
    from dra.eval.pipeline.gold.fable_reference import parse_reference

    def _lookup(item_id):
        path = os.path.join(reference_dir, f"{item_id}.md")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            markdown = f.read()
        ref = parse_reference(item_id, markdown, decomposer)
        return [c.text for c in ref.claims] or None

    return _lookup


def _passthrough_verifier():  # pragma: no cover - trivial live-arm helper
    """A no-op verifier: leaves every claim ``unverified`` (no verdict/conf)."""
    from dra.schemas import Passage  # noqa: F401  (type clarity)
    from dra.verify.base import Verifier, VerifierResult

    class _Passthrough(Verifier):
        def verify(self, claim, passages):
            # 'unverified' is not a terminal VerifierResult label; the without-
            # verifier flow never reads this result (it skips the verify call),
            # so we return a neutral insufficient/0.0 and never apply it.
            return VerifierResult(label="insufficient", confidence=0.0)

    return _Passthrough()


def _make_run_query_with_verifier(cfg):  # pragma: no cover - live Bedrock/Exa
    """The normal pipeline: ensemble verifier ON, ``with_verification=True``."""
    from dra.loop import build_deps, run_query

    deps = build_deps(cfg)

    def _run(query):
        return run_query(query, deps)

    return _run


def _make_run_query_verifier_only(cfg):  # pragma: no cover - live Bedrock/Exa
    """Verifier ON, contradiction layer OFF. `contradiction_judge=None` makes
    `detect_and_resolve` a no-op, so `contested` can come ONLY from the verifier
    (claim-vs-its-evidence), never from claim-vs-claim text comparison. Tests
    whether the over-flagging claim-vs-claim layer earns its place."""
    import dataclasses

    from dra.loop import build_deps, run_query

    deps = dataclasses.replace(build_deps(cfg), contradiction_judge=None)

    def _run(query):
        return run_query(query, deps)

    return _run


def _load_platt(variant):  # pragma: no cover - trivial disk read
    """Load persisted PER-LABEL Platt calibrators for a Verifier B variant.

    Returns a {label: PlattCalibrator} dict for `CrossEncoderVerifier(calibrators=)`,
    or None (→ UNCALIBRATED) if the file is absent — LOUDLY warned, since the
    `verifier_b_*` arms are meant to be the *calibrated* drop-in. Reads both the
    new per-label format ({"labels": {sup: {w,b}, ...}}) and the legacy single
    supported-detector format ({w, b}), which maps to {"supported": .}."""
    import json
    from dra.eval.calibrate import PlattCalibrator
    path = f"eval/results/verifier_b/{variant}/platt.json"
    if not os.path.exists(path):
        print(f"[WARN] no Platt calibrator at {path} — running {variant} UNCALIBRATED", flush=True)
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)

    def _mk(p):
        c = PlattCalibrator()
        c.w, c.b = p["w"], p["b"]
        return c

    by_label = d["labels"] if "labels" in d else {"supported": d}  # new vs legacy
    return {label: _mk(p) for label, p in by_label.items()}


_FROZEN_CANON_DIR = None  # set in main(): the canonical (corrected_verifier) report-cache dir to reuse claims+passages from


def _make_run_query_frozen_cross_encoder(cfg, variant):  # pragma: no cover - live Bedrock + torch
    """FREEZE-UPSTREAM mode. Reuse the claims + retrieved passages from the canonical
    (corrected_verifier) reports — identical no matter the verifier, since there is no
    adaptive loop — and only swap in the v0/v1 cross-encoder, then re-run the real
    downstream (contradiction -> composition). This isolates the verifier and skips the
    expensive plan/search/synthesize regeneration. Indexed by query text."""
    import json

    from dra.contradiction import PairContradictionJudge, detect_and_resolve
    from dra.diagram import LLMDiagramGenerator
    from dra.llm.bedrock import BedrockChat
    from dra.planner import Plan
    from dra.report import compose_report
    from dra.schemas import ResearchReport
    from dra.verify.cross_encoder import CrossEncoderVerifier
    from experiments.code.evaluate import _bind_score_fn

    ckpt = f"eval/verifier_b_models/{variant}/best"
    verifier = CrossEncoderVerifier(score_fn=_bind_score_fn(ckpt), calibrators=_load_platt(variant))
    generator = BedrockChat(cfg.roles["generator"], region=cfg.region)
    diagram_model = cfg.roles.get("diagram") or cfg.roles["generator"]
    diagram_generator = LLMDiagramGenerator(BedrockChat(diagram_model, region=cfg.region))
    judge_model = cfg.verifier_models[0] if cfg.verifier_models else cfg.roles["inloop_judge"]
    contradiction_judge = PairContradictionJudge(BedrockChat(judge_model, region=cfg.region))

    canon = os.path.join(_FROZEN_CANON_DIR, "corrected_verifier")
    index = {}  # query -> path
    for fn in os.listdir(canon):
        if fn.endswith(".json"):
            try:
                index[json.load(open(os.path.join(canon, fn)))["query"]] = os.path.join(canon, fn)
            except Exception:
                pass

    def _run(query):
        rep = ResearchReport.model_validate_json(open(index[query]).read())
        sources = {s.source_id: s for s in rep.sources}
        claims = rep.claims
        for c in claims:  # re-verify each frozen claim with the cross-encoder
            cited = [sources[cit.source_id] for cit in c.citations if cit.source_id in sources]
            r = verifier.verify(c.text, cited)
            c.verdict, c.confidence, c.iterations = r.label, r.confidence, 0
        subqs = list(dict.fromkeys(c.section for c in claims)) or [query]
        wants_visual = "```mermaid" in (rep.report_markdown or "")
        plan = Plan(core_query=query, subquestions=subqs,
                    constraints={"wants_visual": True} if wants_visual else {})
        claims2, contradictions = detect_and_resolve(claims, contradiction_judge)
        return compose_report(query, plan, claims2, list(sources.values()), generator,
                              with_verification=True, diagram_generator=diagram_generator,
                              contradictions=contradictions)

    return _run


def _make_run_query_with_cross_encoder(cfg, variant):  # pragma: no cover - live Bedrock/Exa + torch
    """In-loop verifier = the fine-tuned DeBERTa cross-encoder (Verifier B
    <variant>, Platt-calibrated), dropped into the SAME pipeline + contradiction
    layer as the with/corrected arm (only the verifier changes). Requires torch
    — run under `.venv-train`."""
    import dataclasses

    from dra.loop import build_deps, run_query
    from dra.verify.cross_encoder import CrossEncoderVerifier
    from experiments.code.evaluate import _bind_score_fn

    ckpt = f"eval/verifier_b_models/{variant}/best"
    verifier = CrossEncoderVerifier(score_fn=_bind_score_fn(ckpt), calibrators=_load_platt(variant))
    deps = dataclasses.replace(build_deps(cfg), verifier=verifier)

    def _run(query):
        return run_query(query, deps)

    return _run


def _make_run_query_without_verifier(cfg):  # pragma: no cover - live Bedrock/Exa
    """No-verification arm: same generator/search/decomposition as the normal
    pipeline, but claims are NEVER verified and the report is composed with
    ``with_verification=False`` (claims surfaced unverified). Mirrors
    `dra.loop.run_query` minus the per-claim `verifier.verify` call."""
    from dra.diagram import LLMDiagramGenerator
    from dra.llm.bedrock import BedrockChat
    from dra.loop import RETRIEVAL_K
    from dra.planner import plan
    from dra.report import compose_report
    from dra.router import route
    from dra.search import default_search_tool
    from dra.synthesis import synthesize

    generator = BedrockChat(cfg.roles["generator"], region=cfg.region)
    search = default_search_tool(cfg)
    diagram_model = cfg.roles.get("diagram") or cfg.roles["generator"]
    diagram_generator = LLMDiagramGenerator(BedrockChat(diagram_model, region=cfg.region))

    def _run(query):
        p = plan(query, generator)
        claims: list = []
        sources: dict = {}
        for subq in p.subquestions:
            route(subq, generator)
            passages = search.search(subq, k=RETRIEVAL_K).passages
            for psg in passages:
                sources[psg.source_id] = psg
            new = synthesize(query, subq, passages, generator, start_index=len(claims))
            # NO verification: claims keep verdict='unverified', confidence=None.
            claims.extend(new)
        return compose_report(
            query, p, claims, list(sources.values()), generator,
            with_verification=False, diagram_generator=diagram_generator,
        )

    return _run


def _make_run_query_adaptive(cfg, variant, out_dir):  # pragma: no cover - live Bedrock/Exa + torch
    """ADAPTIVE arm: the full pipeline with the v0 cross-encoder (per-label
    calibrated) as the in-loop verifier, wrapped in the confidence-gated repair
    loop (reformulate ∥ diversify). NOT freeze-upstream — adaptive re-retrieval
    changes upstream, so it regenerates. The Sonnet recommender + Exa /contents
    fetcher power the diversify repair. Per-sub-question traces (iters / winning
    repair / recs+fetched / gaps) are written under ``<out_dir>/trace/`` for the
    cost-by-type analysis, keyed by a query hash."""
    import dataclasses
    import hashlib
    import json

    from dra.adaptive.loop import run_query_adaptive
    from dra.llm.bedrock import BedrockChat
    from dra.loop import build_deps
    from dra.search.fetch import ExaContentsFetcher
    from dra.verify.cross_encoder import CrossEncoderVerifier
    from experiments.code.evaluate import _bind_score_fn

    ckpt = f"eval/verifier_b_models/{variant}/best"
    verifier = CrossEncoderVerifier(score_fn=_bind_score_fn(ckpt), calibrators=_load_platt(variant))
    deps = dataclasses.replace(build_deps(cfg), verifier=verifier)
    rec_model = cfg.verifier_models[0] if cfg.verifier_models else cfg.roles["inloop_judge"]
    recommender_llm = BedrockChat(rec_model, region=cfg.region)   # Sonnet-family source recommender
    fetcher = ExaContentsFetcher(cfg.exa_key)
    trace_dir = os.path.join(out_dir, "trace")
    os.makedirs(trace_dir, exist_ok=True)

    def _run(query):
        trace = []
        rep = run_query_adaptive(query, deps, recommender_llm=recommender_llm,
                                 fetcher=fetcher, trace=trace)
        slug = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
        with open(os.path.join(trace_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump({"query": query, "trace": trace}, f, ensure_ascii=False, indent=2)
        return rep

    return _run


def build_pipeline_deps(cfg, arm, *, decomposer=None, out_dir=None):  # pragma: no cover - live wiring
    """Assemble real `PipelineDeps` for one arm.

    - ``run_query`` — the with/without-verifier flow above.
    - ``grounding_judge`` — INDEPENDENT panel-family `LLMGroundingJudge`.
    - ``panel`` — blind `JudgePanel` over the configured panel models.
    - ``extractor`` — a panel-family answer extractor.
    - ``reference_lookup`` — Fable reference loader (None when absent).
    """
    from dra.eval.pipeline.harness import PipelineDeps
    from dra.eval.pipeline.judges.grounding_judge import LLMGroundingJudge
    from dra.eval.pipeline.judges.panel import JudgePanel
    from dra.llm.bedrock import BedrockChat

    if arm in ("with_verifier", "corrected_verifier"):
        # corrected_verifier = the same full pipeline; the over-flagging fix lives in
        # src/dra/contradiction.py (structured-reasoning prompt), so it flows through
        # build_deps automatically. Separate arm name → separate cache/output dir,
        # preserving the original with_verifier results.
        run_query = _make_run_query_with_verifier(cfg)
    elif arm == "verifier_only":
        run_query = _make_run_query_verifier_only(cfg)   # verifier on, contradiction layer off
    elif arm in ("verifier_b_v0", "verifier_b_v1"):
        # FREEZE-UPSTREAM: reuse corrected_verifier's claims+passages, swap only the verifier
        run_query = _make_run_query_frozen_cross_encoder(cfg, arm.replace("verifier_b_", ""))
    elif arm in ("verifier_b_v0_adaptive", "verifier_b_v1_adaptive"):
        # ADAPTIVE: full pipeline + confidence-gated repair loop (regenerates upstream)
        variant = arm.replace("verifier_b_", "").replace("_adaptive", "")
        run_query = _make_run_query_adaptive(cfg, variant, out_dir or os.path.join("eval/results/pipeline", arm))
    elif arm == "without_verifier":
        run_query = _make_run_query_without_verifier(cfg)
    else:
        raise ValueError(f"unknown arm {arm!r}; expected with/without/corrected/verifier_only/"
                         "verifier_b_v0/verifier_b_v1/verifier_b_v0_adaptive/verifier_b_v1_adaptive")

    panel_models = cfg.panel_models or [DEFAULT_GROUNDING_MODEL]
    grounding_model = os.environ.get("BEDROCK_GROUNDING_JUDGE_MODEL") or DEFAULT_GROUNDING_MODEL

    grounding_judge = LLMGroundingJudge(BedrockChat(grounding_model, region=cfg.region))
    panel = JudgePanel([BedrockChat(m, region=cfg.region) for m in panel_models])
    extractor = BedrockChat(panel_models[0], region=cfg.region)

    return PipelineDeps(
        run_query=run_query,
        grounding_judge=grounding_judge,
        panel=panel,
        extractor=extractor,
        reference_lookup=fable_reference_lookup(decomposer=decomposer),
        arm=arm,
    )


def _arms_for(choice):
    """Expand the --arm choice into the ordered list of arms to run."""
    return list(ARMS) if choice == "both" else [choice]


def main(argv=None):  # pragma: no cover - live Bedrock/Exa wiring
    import argparse
    import json

    from dra.config import load_config
    from dra.eval.pipeline.datasets.dra_bench import load_dra_bench
    from dra.eval.pipeline.harness import run_eval

    parser = argparse.ArgumentParser(description="±verifier pipeline-eval driver")
    parser.add_argument("--arm",
                        choices=("with_verifier", "without_verifier", "corrected_verifier",
                                 "verifier_only", "verifier_b_v0", "verifier_b_v1",
                                 "verifier_b_v0_adaptive", "verifier_b_v1_adaptive", "both"),
                        default="both")
    parser.add_argument("--dataset", choices=("dra_bench", "frames", "truthfulqa"),
                        default="dra_bench", help="which benchmark to run the pipeline over")
    parser.add_argument("--n", type=int, default=100,
                        help="sample size for frames / truthfulqa")
    parser.add_argument("--limit", type=int, default=None, help="evaluate only the first N items")
    parser.add_argument("--ids", default=None,
                        help="comma-separated item ids to run (overrides --limit; for targeted sanity checks)")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out-dir", default=None,
                        help="results dir (default: eval/results/pipeline[_<dataset>])")
    parser.add_argument("--refresh", action="store_true",
                        help="force pipeline regeneration (ignore cached reports)")
    parser.add_argument("--cache-dir", default=None,
                        help="report cache dir (default: <out-dir>/report_cache)")
    args = parser.parse_args(argv)

    cfg = load_config()
    cfg.assert_independence()

    # Default out-dir is dataset-namespaced so a FRAMES run never clobbers the
    # DRA-Bench ±verifier results (and vice versa).
    if args.dataset == "frames":
        from dra.eval.pipeline.datasets.agentic import load_frames
        items = load_frames(args.n)
        default_out = "eval/results/pipeline_frames"
    elif args.dataset == "truthfulqa":
        from dra.eval.pipeline.datasets.truthfulqa import load_truthfulqa
        items = load_truthfulqa(args.n)
        default_out = "eval/results/pipeline_truthfulqa"
    else:
        items = load_dra_bench()
        default_out = "eval/results/pipeline"
    args.out_dir = args.out_dir or default_out
    if args.ids:
        wanted = set(args.ids.split(","))
        items = [it for it in items if it.id in wanted]
    elif args.limit is not None:
        items = items[: args.limit]

    cache_dir = args.cache_dir or os.path.join(args.out_dir, "report_cache")
    global _FROZEN_CANON_DIR  # the freeze-upstream arms reuse corrected_verifier's reports from here
    _FROZEN_CANON_DIR = cache_dir

    # Panel-family decomposer reused by the Fable reference parser.
    from dra.llm.bedrock import BedrockChat
    decomposer_model = (cfg.panel_models or [DEFAULT_GROUNDING_MODEL])[0]
    decomposer = BedrockChat(decomposer_model, region=cfg.region)

    for arm in _arms_for(args.arm):
        arm_out = os.path.join(args.out_dir, arm)
        deps = build_pipeline_deps(cfg, arm, decomposer=decomposer, out_dir=arm_out)
        summary = run_eval(
            items, deps, out_dir=arm_out, max_workers=args.workers,
            report_cache_dir=cache_dir, arm=arm, refresh=args.refresh,
        )
        os.makedirs(arm_out, exist_ok=True)
        with open(os.path.join(arm_out, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"[{arm}] n={summary['overall']['n']} -> {arm_out}/summary.json")


if __name__ == "__main__":  # pragma: no cover
    main()
