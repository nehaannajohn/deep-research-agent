"""Unit tests for the pure claim-level gate + termination logic."""
from __future__ import annotations

from types import SimpleNamespace

from dra.adaptive.control import (
    made_progress,
    needs_repair,
    select_weak_claims,
    should_stop,
)


def test_needs_repair_threshold_and_none():
    assert needs_repair(0.4, 0.7)
    assert not needs_repair(0.8, 0.7)
    assert not needs_repair(0.7, 0.7)        # exactly tau is NOT weak (>= tau)
    assert needs_repair(None, 0.7)           # missing confidence -> weak


def test_select_weak_claims():
    claims = [SimpleNamespace(confidence=c) for c in (0.95, 0.4, 0.71, None)]
    weak = select_weak_claims(claims, tau=0.7)
    assert [c.confidence for c in weak] == [0.4, None]


def test_made_progress():
    assert made_progress(0.4, 0.6, 0.05)
    assert not made_progress(0.40, 0.42, 0.05)   # below eps
    assert not made_progress(0.5, None, 0.05)    # repair produced nothing
    assert made_progress(None, 0.3, 0.05)        # improving from nothing counts


def test_should_stop_cases():
    # accepted: cleared tau
    assert should_stop(iteration=1, confidence=0.9, tau=0.7, progressed=True, max_iters=3)
    # max iters reached
    assert should_stop(iteration=3, confidence=0.5, tau=0.7, progressed=True, max_iters=3)
    # no progress
    assert should_stop(iteration=2, confidence=0.5, tau=0.7, progressed=False, max_iters=3)
    # keep going: below tau, progressing, iters left
    assert not should_stop(iteration=1, confidence=0.5, tau=0.7, progressed=True, max_iters=3)
