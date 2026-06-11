"""SciFact loader via the direct AllenAI release JSONL (HF script-dataset won't load on datasets 5.x).

Joins each claim to the rationale sentences of its cited abstract in corpus.jsonl.
"""
from __future__ import annotations

import io
import json
import tarfile
import urllib.request
from pathlib import Path

from dra.eval.base import EvalExample
from dra.eval.loaders.base import LABEL_MAP, SAMPLE_CAP, stratified_sample
from dra.schemas import Passage

# Official AllenAI SciFact release tarball (extracts to a `data/` dir).
SCIFACT_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
DATA_DIR = Path("eval/verifier_data/scifact")


def _abstract_passages(doc_id, corpus_by_id: dict, sentence_idxs=None) -> list[Passage]:
    """Build Passages for a doc's abstract. If sentence_idxs is None, use all sentences.

    Defensive: coerce doc_id to int for lookup; skip indices out of range / missing docs.
    """
    try:
        row = corpus_by_id[int(doc_id)]
    except (KeyError, TypeError, ValueError):
        return []
    abstract = row.get("abstract") or []
    title = row.get("title", "")
    idxs = range(len(abstract)) if sentence_idxs is None else sentence_idxs
    passages = []
    for i in idxs:
        if not isinstance(i, int) or i < 0 or i >= len(abstract):
            continue  # skip out-of-range / non-int indices
        passages.append(Passage(source_id=f"{doc_id}:{i}", text=abstract[i], title=title))
    return passages


def scifact_claim_to_example(claim: dict, corpus_by_id: dict) -> EvalExample:
    """Pure mapping of one SciFact claim row -> EvalExample (fixture-testable, no I/O).

    corpus_by_id maps int doc_id -> corpus row.
    """
    evidence = claim.get("evidence") or {}
    if evidence:
        # Take the first (doc_id, ev_sets) pair.
        doc_id, ev_sets = next(iter(evidence.items()))
        gold_label = LABEL_MAP.get(ev_sets[0]["label"], "insufficient")
        passages: list[Passage] = []
        for ev in ev_sets:
            passages.extend(
                _abstract_passages(doc_id, corpus_by_id, ev.get("sentences") or [])
            )
    else:
        # NotEnoughInfo case: fall back to the abstract of the first cited doc (if any).
        gold_label = "insufficient"
        cited = claim.get("cited_doc_ids") or []
        passages = _abstract_passages(cited[0], corpus_by_id) if cited else []

    return EvalExample(
        example_id=str(claim["id"]),
        claim=claim["claim"],
        passages=passages,
        gold_label=gold_label,
        split="test",
        meta={"dataset": "scifact"},
    )


def _ensure_data() -> Path:  # pragma: no cover - live download
    """Download+extract the SciFact release into DATA_DIR (skip if already present)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if (DATA_DIR / "corpus.jsonl").exists():
        return DATA_DIR
    with urllib.request.urlopen(SCIFACT_URL) as resp:
        raw = resp.read()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if name.endswith(".jsonl") and member.isfile():
                fobj = tar.extractfile(member)
                if fobj is not None:
                    (DATA_DIR / name).write_bytes(fobj.read())
    return DATA_DIR


def _read_jsonl(path: Path) -> list[dict]:  # pragma: no cover - live I/O
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def load_scifact(split="dev", n=SAMPLE_CAP, seed=13):  # pragma: no cover - live download
    """Live loader: download the AllenAI release, parse claims_<split> + corpus, map, sample."""
    data_dir = _ensure_data()
    corpus = _read_jsonl(data_dir / "corpus.jsonl")
    corpus_by_id = {int(r["doc_id"]): r for r in corpus}
    claims = _read_jsonl(data_dir / f"claims_{split}.jsonl")
    examples = [scifact_claim_to_example(c, corpus_by_id) for c in claims]
    return stratified_sample(examples, n=n, seed=seed)
