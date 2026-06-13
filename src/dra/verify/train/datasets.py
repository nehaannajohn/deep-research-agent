"""Assemble the v0 / v1 training mixes and compute class-balanced sampler weights.

v0 = fever + scifact (public only).
v1 = fever + scifact + synthetic + curriculum (public + our-distribution).
Balancing is by a WeightedRandomSampler (weights here), not downsampling, so no
data is discarded; the model sees ~equal {supported, refuted, nei} exposure.
"""
from __future__ import annotations

from collections import Counter

from dra.verify.train.pairs import TrainPair

_VARIANTS = {
    "v0": ("fever", "scifact"),
    "v1": ("fever", "scifact", "synthetic", "curriculum"),
}


def assemble_variant(variant: str, slices: dict[str, list[TrainPair]]) -> list[TrainPair]:
    """Concatenate the slices included in ``variant`` (order: as in _VARIANTS)."""
    if variant not in _VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; expected {sorted(_VARIANTS)}")
    out: list[TrainPair] = []
    for name in _VARIANTS[variant]:
        out.extend(slices.get(name, []))
    return out


def class_counts(pairs: list[TrainPair]) -> dict[str, int]:
    return dict(Counter(p.label for p in pairs))


def sampler_weights(pairs: list[TrainPair]) -> list[float]:
    """Per-example weight = 1 / count(its class). Equalizes per-class total weight,
    so a WeightedRandomSampler draws ~balanced batches."""
    counts = class_counts(pairs)
    return [1.0 / counts[p.label] for p in pairs]
