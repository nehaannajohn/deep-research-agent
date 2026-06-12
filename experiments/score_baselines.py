"""Score the already-collected baseline responses through the Layer-2 instrument.

The baseline COLLECTION is done (`experiments/collect_dra_baselines.py` wrote
``eval/dra_bench/baselines/<provider>/<id>.json``). This driver is the SCORING
side: each saved free-prose response is pushed through the *same* Layer-2
instrument our pipeline uses, so the baseline axis results are directly
comparable to the ±verifier ablation.

Per saved response the flow is::

    record  = load_record(<id>.json)
    gradable = adapter.to_gradable({query, narrative, sources})   # § black box
    result  = score_gradable(gradable, item, deps, seed=13)       # same axes

where ``adapter`` is `PerplexityAdapter` / `OpenAIAdapter` wired with:
  - an injected **decomposer** (free prose -> atomic claim texts) — a small
    Bedrock-backed prompt live, a fake in tests;
  - an injected **matcher** (claim <-> the response's returned sources) — a pure
    text-overlap `keyword_matcher` (no embeddings), so a baseline's claims get
    citations against the sources it actually returned.

``verdict`` / ``confidence`` on the synthesized claims are left ``None`` by the
adapter and assigned downstream by the INDEPENDENT grounding judge (spec §2/§4)
— never the in-loop verifier.

The aggregation reuses `harness._aggregate` (the exact `run_eval` aggregation),
so baseline summaries share the schema of the pipeline summaries.

Resumable per item (skip if already scored) + skip-on-exception. The live
Bedrock/decomposer wiring is ``# pragma: no cover``; the pure helpers
(`load_record`, `normalize_sources`, `keyword_matcher`, `score_record`,
`aggregate`) are unit-tested with fakes in `tests/test_score_baselines.py`.

Usage:
    .venv/bin/python -m experiments.score_baselines --limit 3 --provider both
    .venv/bin/python -m experiments.score_baselines              # full, both
    .venv/bin/python -m experiments.score_baselines --provider perplexity
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

# Make ``src`` importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dra.schemas import Citation, Passage  # noqa: E402

from dra.eval.pipeline.adapters.openai import OpenAIAdapter  # noqa: E402
from dra.eval.pipeline.adapters.perplexity import PerplexityAdapter  # noqa: E402
from dra.eval.pipeline.contracts import EvalItem  # noqa: E402
from dra.eval.pipeline.harness import (  # noqa: E402
    PipelineDeps,
    _aggregate,
    score_gradable,
)

logger = logging.getLogger(__name__)

BASELINES_DIR = REPO_ROOT / "eval" / "dra_bench" / "baselines"
REFERENCE_DIR = REPO_ROOT / "eval" / "dra_bench" / "reference_reports"
DEFAULT_OUT_DIR = "eval/results/baselines"
SEED = 13

# Grounding judge: a panel-family model independent of the in-loop verifier
# ensemble (spec §4), matching the pipeline driver's default.
DEFAULT_GROUNDING_MODEL = "openai.gpt-oss-120b-1:0"

ADAPTERS = {
    "perplexity": PerplexityAdapter,
    "openai": OpenAIAdapter,
}


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested with fakes)
# --------------------------------------------------------------------------- #
def load_record(path: str) -> dict:
    """Read one saved baseline response (collect_dra_baselines.write_record shape)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _search_results(record: dict) -> list[dict]:
    """Perplexity exposes rich sources (title + snippet) under raw.search_results."""
    raw = record.get("raw") or {}
    sr = raw.get("search_results")
    return sr if isinstance(sr, list) else []


def _openai_annotations(record: dict) -> list[dict]:
    """OpenAI exposes url_citation annotations (title + url, no snippet text)."""
    raw = record.get("raw") or {}
    choices = raw.get("choices") or []
    out: list[dict] = []
    for ch in choices:
        msg = ch.get("message") if isinstance(ch, dict) else None
        anns = (msg or {}).get("annotations") or []
        for a in anns:
            if isinstance(a, dict) and a.get("type") == "url_citation":
                uc = a.get("url_citation") or {}
                if uc.get("url"):
                    out.append({"title": uc.get("title", ""), "url": uc["url"],
                                "snippet": ""})
    return out


def normalize_sources(record: dict) -> list[Passage]:
    """Recover the response's returned sources as `Passage`s (provenance for the
    matcher + grounding judge).

    A black-box baseline returns URLs, optionally with provider-specific richer
    metadata: Perplexity carries ``title`` + ``snippet`` under
    ``raw.search_results``; OpenAI carries ``title`` under message
    ``annotations``. We use the richest available text per URL and fall back to
    the bare URL list (title/text empty) so the matcher always has something.
    Each passage gets a stable ``source_id`` (``s0``, ``s1`` ...) so claims can
    cite it.
    """
    rich: list[dict] = _search_results(record) or _openai_annotations(record)

    entries: list[dict] = []
    seen_urls: set[str] = set()
    for r in rich:
        url = (r.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        entries.append({
            "url": url,
            "title": r.get("title", "") or "",
            "text": r.get("snippet", "") or r.get("text", "") or "",
        })

    # Fall back to / top up with the bare URL list (no text).
    for url in record.get("sources", []) or []:
        url = (url or "").strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            entries.append({"url": url, "title": "", "text": ""})

    return [
        Passage(
            source_id=f"s{i}",
            text=e["text"],
            url=e["url"],
            title=e["title"],
        )
        for i, e in enumerate(entries)
    ]


_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "of", "in", "to", "and",
    "on", "for", "with", "as", "by", "at", "it", "its", "that", "this", "these",
    "those", "from", "or", "but", "they", "them", "can", "do", "does", "how",
    "what", "which", "when", "their", "have", "has", "had",
}


def _keywords(text: str) -> set[str]:
    return {t.strip(".,;:!?()[]\"'").lower() for t in text.split()} - _STOP - {""}


def keyword_matcher(claim_text: str, sources: list[Passage]) -> list[Citation]:
    """Match a claim to the baseline's returned sources by keyword overlap.

    Pure, no embeddings (spec: a simple text-overlap matcher): a source is a
    match when its title+text shares a meaningful fraction of the claim's
    keywords. Returns a `Citation` per matched source (``span`` is a short
    snippet from the source text/title). When nothing matches the claim is left
    uncited — which the grounding scorer correctly treats as a hallucination.
    """
    claim_kw = _keywords(claim_text)
    if not claim_kw:
        return []

    # require a meaningful share of the (shorter) claim keywords to overlap.
    need = max(1, (len(claim_kw) + 2) // 3)

    citations: list[Citation] = []
    for p in sources:
        src_kw = _keywords(f"{p.title} {p.text}")
        if not src_kw:
            continue
        overlap = claim_kw & src_kw
        if len(overlap) >= need:
            span = (p.text or p.title or p.url)[:200]
            citations.append(Citation(source_id=p.source_id, span=span))
    return citations


def baseline_grounding(gradable, grounding_judge) -> Optional[dict]:
    """Judge a black-box baseline's grounding against its FULL source set.

    A black-box system exposes sources but never the claim->source links, so the
    keyword matcher under-counts and (for title-only sources like OpenAI's)
    matches nothing — making the matcher-based grounding meaningless. Instead we
    let the independent grounding judge reason over the system's OWN evidence:
    each claim is judged against ALL of the report's text-bearing sources.

    Applicability: grounding is **N/A** (``{"applicable": False}``) when no source
    carries usable evidence text (no `Passage` with non-empty ``text``) — we
    literally cannot check grounding, so we don't fabricate a 0. The judge is not
    called in that case.

    When applicable: ``grounding_rate`` = supported / n_claims,
    ``hallucination_rate`` = (n_claims - supported) / n_claims. Citation
    precision/recall are ``None`` (a black-box system's claim->source links are
    unrecoverable). Returns ``applicable: True`` plus ``n_claims``.
    """
    text_sources = [p for p in gradable.sources if (p.text or "").strip()]
    if not text_sources:
        return {"applicable": False}

    claims = gradable.claims
    n = len(claims)
    supported = sum(
        1 for c in claims if grounding_judge.verdict(c.text, text_sources) == "supported"
    )

    return {
        "applicable": True,
        "grounding_rate": (supported / n) if n else 0.0,
        "hallucination_rate": ((n - supported) / n) if n else 0.0,
        "citation_precision": None,
        "citation_recall": None,
        "n_claims": n,
    }


def score_record(record: dict, item: EvalItem, adapter, deps: PipelineDeps, *,
                 seed: int = SEED) -> dict:
    """Score one saved baseline response through the Layer-2 instrument.

    Builds the adapter-facing normalized shape (``query``/``narrative``/
    ``sources`` as `Passage`s recovered from the record), runs the injected
    adapter's ``to_gradable`` (decomposer -> claims, matcher -> citations), then
    delegates every axis to the shared `score_gradable` — the SAME helper our
    pipeline's `evaluate_item` calls.
    """
    raw_response = {
        "query": record.get("query", item.query),
        "narrative": record.get("narrative", ""),
        "sources": normalize_sources(record),
        "constraints": item.constraints,
    }
    gradable = adapter.to_gradable(raw_response)
    result = score_gradable(gradable, item, deps, seed=seed)
    # Overwrite the matcher-based grounding with the full-source-set judgement:
    # for a black box, grounding is either judged over its own evidence or N/A.
    result["grounding"] = baseline_grounding(gradable, deps.grounding_judge)
    return result


def aggregate(results: list[dict]) -> dict:
    """Aggregate per-item baseline results — reuses the `run_eval` aggregation."""
    return _aggregate(results)


# --------------------------------------------------------------------------- #
# Per-provider driver (resumable + skip-on-exception)
# --------------------------------------------------------------------------- #
def _items_by_id() -> dict[str, EvalItem]:
    """Index DRA-Bench items by id (for constraints / expected_behavior / gold)."""
    from dra.eval.pipeline.datasets.dra_bench import load_dra_bench

    return {it.id: it for it in load_dra_bench()}


def _saved_ids(provider: str) -> list[str]:
    """Sorted ids of saved responses for a provider (the 50-item subset)."""
    pdir = BASELINES_DIR / provider
    if not pdir.is_dir():
        return []
    return sorted(p.stem for p in pdir.glob("*.json"))


def _already_scored(out_dir: str, provider: str) -> dict[str, dict]:
    """Resumability: load any per_item.json already written for this provider."""
    path = Path(out_dir) / provider / "per_item.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return {r["id"]: r for r in rows if "id" in r}
    except Exception:  # noqa: BLE001 - corrupt partial file -> rescore all
        return {}


def score_provider(provider: str, deps_factory: Callable[[], PipelineDeps], *,
                   adapter, items: dict[str, EvalItem], out_dir: str,
                   limit: Optional[int] = None, workers: int = 6,
                   seed: int = SEED) -> dict:  # pragma: no cover - live orchestration
    """Score every saved response for ``provider``; write per_item + summary.

    Resumable (skips items already in per_item.json) and never fatal (an item
    whose scoring raises is logged and skipped). Returns the summary dict.
    """
    ids = _saved_ids(provider)
    if limit is not None:
        ids = ids[:limit]

    done = _already_scored(out_dir, provider)
    todo = [i for i in ids if i not in done]
    deps = deps_factory()

    def _score(item_id: str):
        try:
            record = load_record(str(BASELINES_DIR / provider / f"{item_id}.json"))
            item = items.get(item_id)
            if item is None:
                logger.warning("[%s] %s: no matching EvalItem; skipping", provider, item_id)
                return None
            return score_record(record, item, adapter, deps, seed=seed)
        except Exception:  # noqa: BLE001 - skip a pathological item, don't abort
            logger.warning("[%s] %s scoring raised; skipping\n%s",
                           provider, item_id, traceback.format_exc())
            return None

    if workers and workers > 1 and todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fresh = list(pool.map(_score, todo))
    else:
        fresh = [_score(i) for i in todo]

    results = list(done.values()) + [r for r in fresh if r is not None]
    # stable ordering by id for reproducible output
    results.sort(key=lambda r: r["id"])

    summary = {"provider": provider, "seed": seed, "overall": aggregate(results)}

    pdir = Path(out_dir) / provider
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "per_item.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (pdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _build_live_deps(cfg) -> PipelineDeps:  # pragma: no cover - live Bedrock wiring
    """Assemble real `PipelineDeps` (grounding judge + panel + extractor +
    reference_lookup) once; the adapter owns the decomposer + matcher."""
    from dra.eval.pipeline.judges.grounding_judge import LLMGroundingJudge
    from dra.eval.pipeline.judges.panel import JudgePanel
    from dra.llm.bedrock import BedrockChat

    panel_models = cfg.panel_models or [DEFAULT_GROUNDING_MODEL]
    grounding_model = os.environ.get("BEDROCK_GROUNDING_JUDGE_MODEL") or DEFAULT_GROUNDING_MODEL

    grounding_judge = LLMGroundingJudge(BedrockChat(grounding_model, region=cfg.region))
    panel = JudgePanel([BedrockChat(m, region=cfg.region) for m in panel_models])
    extractor = BedrockChat(panel_models[0], region=cfg.region)

    return PipelineDeps(
        run_query=lambda q: (_ for _ in ()).throw(  # never used by score_gradable
            RuntimeError("baseline scoring does not run the pipeline")),
        grounding_judge=grounding_judge,
        panel=panel,
        extractor=extractor,
        reference_lookup=_reference_lookup(),
    )


def _reference_lookup():  # pragma: no cover - disk read
    """Sonnet gold reference loader: ``id -> [claim texts] | None`` if present.

    Returns the raw markdown split into non-empty lines as crude reference
    "claims" for citation-recall; absent reference -> None (similarity skipped).
    A model-backed decomposer is overkill here — recall is a keyword-overlap
    check (grounding.py), so line granularity suffices.
    """
    def _lookup(item_id: str):
        path = REFERENCE_DIR / f"{item_id}.md"
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        lines = [ln.strip() for ln in text.splitlines()]
        claims = [ln.lstrip("#-* ").strip() for ln in lines if ln and not ln.startswith("#")]
        return [c for c in claims if c] or None

    return _lookup


def _bedrock_decomposer(cfg):  # pragma: no cover - live Bedrock wiring
    """Free-prose -> atomic claim texts via a panel-family Bedrock model.

    The same instrument that decomposes our own reports is approximated here
    with a small prompt so the baseline's prose is reduced to atomic claims by a
    comparable mechanism (spec §2: audit the black box with our own instrument).
    """
    from dra.llm.bedrock import BedrockChat

    model = (cfg.panel_models or [DEFAULT_GROUNDING_MODEL])[0]
    llm = BedrockChat(model, region=cfg.region)

    prompt_tmpl = (
        "Extract the atomic factual claims from this research report, one per "
        "line. Each line must be a single self-contained factual assertion with "
        "no bullets, numbering, or commentary.\n\nREPORT:\n{narrative}\n\nCLAIMS:"
    )

    def _decompose(narrative: str) -> list[str]:
        if not (narrative or "").strip():
            return []
        out = llm.complete(prompt_tmpl.format(narrative=narrative))
        claims = [ln.lstrip("-*0123456789. \t").strip() for ln in out.splitlines()]
        return [c for c in claims if c]

    return _decompose


def main(argv=None):  # pragma: no cover - live Bedrock wiring
    import argparse

    from dotenv import load_dotenv

    from dra.config import load_config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["perplexity", "openai", "both"],
                        default="both")
    parser.add_argument("--limit", type=int, default=None, help="first N saved items")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv()
    cfg = load_config()

    items = _items_by_id()
    decomposer = _bedrock_decomposer(cfg)
    providers = ["perplexity", "openai"] if args.provider == "both" else [args.provider]

    for provider in providers:
        adapter = ADAPTERS[provider](decomposer=decomposer, matcher=keyword_matcher)
        summary = score_provider(
            provider,
            deps_factory=lambda: _build_live_deps(cfg),
            adapter=adapter,
            items=items,
            out_dir=args.out_dir,
            limit=args.limit,
            workers=args.workers,
        )
        overall = summary["overall"]
        print(f"[{provider}] n={overall['n']} grounding_rate={overall['grounding_rate']} "
              f"relevance_mean={overall['relevance_mean']} -> {args.out_dir}/{provider}/")


if __name__ == "__main__":  # pragma: no cover
    main()
