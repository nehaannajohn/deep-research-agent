"""Build the silver transfer-validation set from cached pipeline reports + the
independent grounding judge's per-claim verdicts, and select a stratified subset
for human anchoring.

Each transfer example is (claim text, its CITED passages, silver 3-way label),
matching exactly what Verifier B sees at inference. Labels come from the
grounding judge (panel-family, independent of Verifier A) — never from Verifier A
(circular) and never from the relevance/quality panel (report-level rubric).
"""
from __future__ import annotations

import random
from typing import Optional

from pydantic import BaseModel, Field

from dra.schemas import Passage
from dra.verify.train import TO3


class TransferExample(BaseModel):
    example_id: str
    claim: str
    passages: list[Passage] = Field(default_factory=list)
    label: str          # one of LABEL3 (silver)
    human_label: Optional[str] = None   # filled by the anchor labeling pass


def _cited_passages(claim: dict, sources_by_id: dict) -> list[Passage]:
    out: list[Passage] = []
    for cit in claim.get("citations") or []:
        s = sources_by_id.get(cit.get("source_id"))
        if s and (s.get("text") or "").strip():
            out.append(Passage(source_id=s["source_id"], text=s["text"],
                               url=s.get("url", ""), title=s.get("title", "")))
    return out


def build_transfer_examples(reports: dict, per_items: dict) -> list[TransferExample]:
    """Join cached reports (id -> report dict) with per_item dicts (id -> per_item).

    ``report`` shape: ``{claims:[{id,text,citations}], sources:[{source_id,text,...}]}``.
    ``per_item`` shape: ``{grounding:{per_claim:[{id,verdict}]}}``.
    """
    out: list[TransferExample] = []
    for rid, report in reports.items():
        pi = per_items.get(rid) or {}
        verdicts = {c["id"]: c.get("verdict")
                    for c in ((pi.get("grounding") or {}).get("per_claim") or [])
                    if "id" in c}
        sources_by_id = {s["source_id"]: s for s in (report.get("sources") or [])}
        for claim in report.get("claims") or []:
            v = verdicts.get(claim.get("id"))
            if v is None:
                continue
            out.append(TransferExample(
                example_id=f"{rid}:{claim['id']}",
                claim=claim.get("text", ""),
                passages=_cited_passages(claim, sources_by_id),
                label=TO3.get(v, "nei"),
            ))
    return out


def stratified_anchor(examples: list[TransferExample], *, n: int, seed: int = 13) -> list[TransferExample]:
    """Pick up to ``n`` examples balanced across labels (minority classes first)."""
    by_label: dict[str, list[TransferExample]] = {}
    for e in examples:
        by_label.setdefault(e.label, []).append(e)
    rng = random.Random(seed)
    for v in by_label.values():
        rng.shuffle(v)
    out: list[TransferExample] = []
    labels = sorted(by_label, key=lambda l: len(by_label[l]))  # rarest first
    i = 0
    while len(out) < n and any(by_label[l] for l in labels):
        lab = labels[i % len(labels)]
        if by_label[lab]:
            out.append(by_label[lab].pop())
        i += 1
    return out[:n]
