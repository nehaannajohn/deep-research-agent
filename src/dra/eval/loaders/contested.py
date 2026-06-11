"""Contested-set construction (the 4th verdict label).

Builds the synthetic `contested` evaluation set that the public 3-way
benchmarks (FEVER/SciFact) can't natively provide. See design §3.

Contract: start from a held-out `supported` (claim C, evidence E) pair, have an
LLM synthesize a plausible refuting passage E', and keep the example only if an
injected verifier confirms verify(C,[E])->supported AND verify(C,[E'])->refuted.
The resulting contested example is a SINGLE holistic input — passages=[E, E'] —
that the verifier under test should later label `contested`. Those component
checks are the construction QA gate, NOT how contested is scored.
"""
from __future__ import annotations

import json

from dra.eval.base import EvalExample
from dra.schemas import Passage

BENCH_PATH = "experiments/results/verifier/bench.json"

_SYSTEM = (
    "You are an adversarial evidence writer for a fact-checking benchmark. "
    "Given a claim and a passage that supports it, write a single short, "
    "plausible evidence passage that REFUTES the claim, in the same register "
    "and length as the supporting passage. Output only the refuting passage."
)


def build_contested_example(
    claim: str, support: Passage, refute: Passage, example_id: str
) -> EvalExample:
    """Bundle a support/refute pair into one holistic contested EvalExample."""
    return EvalExample(
        example_id=example_id,
        claim=claim,
        passages=[support, refute],
        gold_label="contested",
        split="test",
        meta={
            "dataset": "contested",
            "construction": "synthetic",
            "support_id": support.source_id,
            "refute_id": refute.source_id,
        },
    )


def synthesize_refuting_evidence(claim: str, support: Passage, llm) -> Passage:
    """Prompt `llm` (a `complete`-style object) to write a passage that
    plausibly refutes `claim`, wrapped as a Passage derived from `support`."""
    prompt = (
        f"{_SYSTEM}\n\n"
        f"Claim: {claim}\n"
        f"Supporting passage: {support.text}\n\n"
        "Refuting passage:"
    )
    text = llm.complete(prompt).strip()
    return Passage(
        source_id=f"{support.source_id}::refute",
        text=text,
        title=support.title,
    )


def is_valid_contested(claim: str, support: Passage, refute: Passage, verifier) -> bool:
    """Construction QA gate: keep only if E supports C and E' refutes C."""
    return (
        verifier.verify(claim, [support]).label == "supported"
        and verifier.verify(claim, [refute]).label == "refuted"
    )


def build_contested_set(supported, llm, verifier, n=None, seed=13) -> list[EvalExample]:
    """For each supported EvalExample (first passage = E), synthesize E',
    run the QA gate, and emit a contested EvalExample for those that pass.

    Deterministic order (input order); stops once `n` have been emitted.
    `seed` is accepted for signature stability / future sampling (unused here).
    """
    out: list[EvalExample] = []
    for ex in supported:
        if n is not None and len(out) >= n:
            break
        if not ex.passages:
            continue
        support = ex.passages[0]
        refute = synthesize_refuting_evidence(ex.claim, support, llm)
        if is_valid_contested(ex.claim, support, refute, verifier):
            out.append(
                build_contested_example(
                    ex.claim, support, refute, example_id=f"contested:{ex.example_id}"
                )
            )
    return out


def load_prior_contested_cases(bench_path: str = BENCH_PATH) -> list[EvalExample]:
    """Parse the panel-validated `contested` entries from bench.json.

    bench.json is a list of {case, intended, panel_labels, claim}; the contested
    cases carry no separable support/refute evidence, so passages stay empty and
    gold_label stays "contested". Defensive: tolerate missing keys / bad shape.
    """
    try:
        with open(bench_path) as f:
            rows = json.load(f)
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive I/O
        return []
    if not isinstance(rows, list):  # pragma: no cover - defensive shape
        return []
    out: list[EvalExample] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("intended") != "contested":
            continue
        claim = row.get("claim")
        if not claim:
            continue
        case = row.get("case") or f"prior{i}"
        out.append(
            EvalExample(
                example_id=f"contested:prior:{case}",
                claim=claim,
                passages=[],
                gold_label="contested",
                split="test",
                meta={
                    "dataset": "contested",
                    "construction": "panel_validated",
                    "case": case,
                    "panel_labels": row.get("panel_labels", []),
                },
            )
        )
    return out


def assemble_contested_set(
    supported, llm, verifier, n=None, seed=13, bench_path: str = BENCH_PATH
) -> list[EvalExample]:
    """Synthetic constructed set + the prior panel-validated cases, concatenated."""
    return build_contested_set(supported, llm, verifier, n=n, seed=seed) + (
        load_prior_contested_cases(bench_path)
    )


def build_contested_set_live(supported, n=None, seed=13):  # pragma: no cover - live Bedrock
    """Real entrypoint: wire a Bedrock LLM + the in-loop judge verifier and build.

    Not exercised in unit tests (no network / no creds). Construction-only:
    the synthesized refuting evidence and the QA gate both call Bedrock.
    """
    from dra.config import load_config
    from dra.llm.bedrock import BedrockChat
    from dra.verify.llm_judge import LLMJudgeVerifier

    cfg = load_config()
    judge_model = cfg.roles["inloop_judge"]
    llm = BedrockChat(judge_model)
    verifier = LLMJudgeVerifier(BedrockChat(judge_model))
    return build_contested_set(supported, llm, verifier, n=n, seed=seed)
