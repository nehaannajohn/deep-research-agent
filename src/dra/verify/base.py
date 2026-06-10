"""Verifier contract: given a claim and its evidence, return a label + confidence.

Both variant A (LLM-judge) and variant B (fine-tuned cross-encoder) implement this,
so they're drop-in interchangeable for the ablation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

EntailmentLabel = Literal["supported", "refuted", "insufficient"]


class Verdict(BaseModel):
    label: EntailmentLabel = "insufficient"
    confidence: float = 0.0


class Verifier(ABC):
    @abstractmethod
    def verify(self, claim: str, evidence: str) -> Verdict:
        raise NotImplementedError
