"""Unified evaluation example contract: one (claim, passages, gold_label) the verifier scores."""
from __future__ import annotations

from pydantic import BaseModel, Field

from dra.schemas import Passage

LABELS = ("supported", "refuted", "insufficient", "contested")


class EvalExample(BaseModel):
    example_id: str
    claim: str
    passages: list[Passage] = Field(default_factory=list)
    gold_label: str                 # one of LABELS
    split: str = "test"             # "calibration" | "test"
    meta: dict = Field(default_factory=dict)
