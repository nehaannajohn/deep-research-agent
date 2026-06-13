"""Verifier B training-data transforms (pure) + label constants for the 3-way head."""
from __future__ import annotations

LABEL3 = ("supported", "refuted", "nei")
LABEL2ID = {"supported": 0, "refuted": 1, "nei": 2}
ID2LABEL = {0: "supported", 1: "refuted", 2: "nei"}
# pipeline 4-way verdict -> 3-way head. contested is NOT a head class; it folds to
# nei for the head (and is handled separately by the pairwise/contradiction path).
TO3 = {"supported": "supported", "refuted": "refuted", "insufficient": "nei", "contested": "nei"}
