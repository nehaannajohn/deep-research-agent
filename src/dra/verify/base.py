"""Verifier contract: judge a claim against all its cited passages.

Returns a 4-way label + reasoning + a (model-generated) recommendation + a
MEASURED confidence (self-consistency or ensemble agreement; never the model's
verbalized number). Both the LLM-judge and (future) cross-encoder implement this.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

from dra.schemas import Passage, VerdictLabel

Recommendation = Literal["accept", "gather_more", "reformulate", "revise", "flag_contested"]


class VerifierResult(BaseModel):
    label: VerdictLabel = "insufficient"   # one of the 4 terminal labels; never "unverified"
    confidence: float = 0.0                # measured (raw, not recalibrated)
    reasoning: str = ""
    recommendation: Recommendation = "gather_more"
    votes: dict[str, int] = Field(default_factory=dict)


class Verifier(ABC):
    @abstractmethod
    def verify(self, claim: str, passages: list[Passage]) -> VerifierResult:
        raise NotImplementedError
