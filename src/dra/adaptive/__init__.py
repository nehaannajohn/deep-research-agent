"""Adaptive retrieval: a confidence-gated, claim-level repair loop.

Gate on the verifier's calibrated predicted-label confidence (claim-level, τ=0.7);
for each weak claim, repair in parallel (reformulate + diversify sources), re-verify,
keep the highest-confidence candidate; stop on τ / no-progress / max-iters. See
docs/archive/2026-06-14-adaptive-retrieval-design.md.
"""
