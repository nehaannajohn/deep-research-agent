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

FABLE_REFERENCE_DIR = "eval/dra_bench/fable_references"


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


def build_pipeline_deps(cfg, arm, *, decomposer=None):  # pragma: no cover - live wiring
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

    if arm == "with_verifier":
        run_query = _make_run_query_with_verifier(cfg)
    elif arm == "without_verifier":
        run_query = _make_run_query_without_verifier(cfg)
    else:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS}")

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
    parser.add_argument("--arm", choices=("with_verifier", "without_verifier", "both"),
                        default="both")
    parser.add_argument("--limit", type=int, default=None, help="evaluate only the first N items")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out-dir", default="eval/results/pipeline")
    parser.add_argument("--refresh", action="store_true",
                        help="force pipeline regeneration (ignore cached reports)")
    parser.add_argument("--cache-dir", default=None,
                        help="report cache dir (default: <out-dir>/report_cache)")
    args = parser.parse_args(argv)

    cfg = load_config()
    cfg.assert_independence()

    items = load_dra_bench()
    if args.limit is not None:
        items = items[: args.limit]

    cache_dir = args.cache_dir or os.path.join(args.out_dir, "report_cache")

    # Panel-family decomposer reused by the Fable reference parser.
    from dra.llm.bedrock import BedrockChat
    decomposer_model = (cfg.panel_models or [DEFAULT_GROUNDING_MODEL])[0]
    decomposer = BedrockChat(decomposer_model, region=cfg.region)

    for arm in _arms_for(args.arm):
        deps = build_pipeline_deps(cfg, arm, decomposer=decomposer)
        arm_out = os.path.join(args.out_dir, arm)
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
