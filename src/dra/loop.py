"""Pipeline entry point — the single-pass `run_query`.

`query -> plan -> (route -> Exa search -> synthesize -> verify) per sub-question
-> contradiction resolution -> compose ResearchReport`. The confidence-gated
adaptive variant (re-retrieve + repair low-confidence claims) lives in
`dra.adaptive.loop.run_query_adaptive`, which reuses the same `Deps`.
"""
from __future__ import annotations

from dataclasses import dataclass

from dra.planner import plan
from dra.report import compose_report
from dra.router import route
from dra.schemas import ResearchReport
from dra.synthesis import synthesize
from dra.verify.base import Verifier

# Settled retrieval default (experiments/results stage3+4 → VERDICT_k.md): cumulative
# coverage is flat beyond 5 records/sub-question, so 5 is the lean default; the adaptive
# loop (dra.adaptive) re-retrieves (reformulate + diversify) for the rare low-confidence
# sub-question rather than blindly escalating k.
RETRIEVAL_K = 5


@dataclass
class Deps:
    generator: object  # BedrockChat-like: planner/synthesis (complete_json) + router (complete)
    verifier: Verifier
    search: object  # SearchTool
    diagram_generator: object = None  # DiagramGenerator-like; None = no diagram
    contradiction_judge: object = None  # PairContradictionJudge-like; None = skip


def run_query(query: str, deps: "Deps | None" = None, *, progress=None) -> ResearchReport:
    """Run the single-pass pipeline. `progress`, if given, is called at each stage
    boundary as `progress(event, **fields)` — purely observational (CLI/UI feedback);
    `None` leaves behaviour identical."""
    def _emit(event, **fields):
        if progress is not None:
            progress(event, **fields)

    if deps is None:  # Phase-0 skeleton behaviour
        return ResearchReport(query=query)

    p = plan(query, deps.generator)
    _emit("plan", subquestions=list(p.subquestions))
    claims: list = []
    sources: dict = {}
    for subq in p.subquestions:
        route(subq, deps.generator)  # label only (Exa is the single MVP backend)
        passages = deps.search.search(subq, k=RETRIEVAL_K).passages
        _emit("retrieve", subq=subq, n_passages=len(passages))
        for psg in passages:
            sources[psg.source_id] = psg
        new = synthesize(query, subq, passages, deps.generator, start_index=len(claims))
        for c in new:
            cited = [sources[cit.source_id] for cit in c.citations if cit.source_id in sources]
            r = deps.verifier.verify(c.text, cited)
            c.verdict, c.confidence = r.label, r.confidence
        _emit("verify", subq=subq, n_claims=len(new))
        claims.extend(new)

    from dra.contradiction import detect_and_resolve
    claims, contradictions = detect_and_resolve(claims, deps.contradiction_judge)
    _emit("contradiction", n_contradictions=len(contradictions))
    report = compose_report(query, p, claims, list(sources.values()), deps.generator,
                            with_verification=True,
                            diagram_generator=deps.diagram_generator, contradictions=contradictions)
    _emit("compose", n_claims=len(claims), n_sources=len(sources))
    return report


def _pick_torch_device() -> str:
    """Best available torch device for the cross-encoder: CUDA > Apple MPS > CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # noqa: BLE001 — torch absent / probe failed → CPU
        pass
    return "cpu"


def _load_platt(variant: str):
    """Load per-label Platt calibrators for a Verifier B variant from its `platt.json`,
    as a `{label: PlattCalibrator}` dict for `CrossEncoderVerifier(calibrators=)`. Returns
    None (→ uncalibrated) if the file is absent."""
    import json
    import os

    from dra.eval.calibrate import PlattCalibrator

    path = os.path.join("eval", "results", "verifier_b", variant, "platt.json")
    if not os.path.exists(path):
        print(f"[WARN] no Platt calibrator at {path} — running {variant} UNCALIBRATED")
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)

    def _mk(p):
        c = PlattCalibrator()
        c.w, c.b = p["w"], p["b"]
        return c

    by_label = d["labels"] if "labels" in d else {"supported": d}  # new per-label vs legacy
    return {label: _mk(p) for label, p in by_label.items()}


def _build_cross_encoder_verifier(variant: str, cfg):
    """Build the trained DeBERTa-v3 cross-encoder verifier (v0/v1), Platt-calibrated.
    torch/transformers are imported lazily here, only when this path is taken."""
    import os

    from dra.verify.cross_encoder import CrossEncoderVerifier
    from dra.verify.cross_encoder_model import bind_score_fn

    ckpt = os.path.join("eval", "verifier_b_models", variant, "best")
    return CrossEncoderVerifier(
        score_fn=bind_score_fn(ckpt, device=_pick_torch_device()),
        calibrators=_load_platt(variant),
    )


def build_deps(cfg, *, verifier: str = "ensemble") -> Deps:
    """Assemble the pipeline dependencies.

    `verifier` selects the in-loop entailment verifier:
      - "ensemble" (default): the 3-model LLM panel {Sonnet, Mistral, Nova}, cross-model
        agreement as confidence (falls back to the single in-loop judge if none configured);
      - "v0" / "v1": the trained DeBERTa-v3 cross-encoder, Platt-calibrated (needs torch +
        the checkpoint under eval/verifier_b_models/<variant>/best).
    Contradiction detection always stays an LLM judge (Sonnet) — it is a separate, pairwise
    claim↔claim check, not the entailment verifier.
    """
    from dra.diagram import LLMDiagramGenerator
    from dra.llm.bedrock import BedrockChat
    from dra.search import default_search_tool
    from dra.verify.ensemble import EnsembleVerifier
    from dra.verify.llm_judge import LLMJudgeVerifier

    diagram_model = cfg.roles.get("diagram") or cfg.roles["generator"]

    if verifier in ("v0", "v1"):
        in_loop = _build_cross_encoder_verifier(verifier, cfg)
    elif cfg.verifier_models:
        in_loop = EnsembleVerifier(
            [LLMJudgeVerifier(BedrockChat(m, region=cfg.region), n_samples=1)
             for m in cfg.verifier_models]
        )
    else:
        in_loop = LLMJudgeVerifier(BedrockChat(cfg.roles["inloop_judge"], region=cfg.region))

    from dra.contradiction import PairContradictionJudge
    judge_model = cfg.verifier_models[0] if cfg.verifier_models else cfg.roles["inloop_judge"]
    return Deps(
        generator=BedrockChat(cfg.roles["generator"], region=cfg.region),
        verifier=in_loop,
        search=default_search_tool(cfg),
        diagram_generator=LLMDiagramGenerator(BedrockChat(diagram_model, region=cfg.region)),
        contradiction_judge=PairContradictionJudge(BedrockChat(judge_model, region=cfg.region)),
    )
