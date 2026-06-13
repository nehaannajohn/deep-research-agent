from __future__ import annotations

from dra.verify.train.datasets import assemble_variant, class_counts, sampler_weights
from dra.verify.train.pairs import TrainPair


def _pairs(spec):
    out = []
    for label, n, src in spec:
        out += [TrainPair(claim="c", passage="p", label=label, source=src) for _ in range(n)]
    return out


def test_v0_excludes_synthetic_and_curriculum():
    slices = {
        "fever": _pairs([("supported", 3, "fever")]),
        "scifact": _pairs([("refuted", 2, "scifact")]),
        "synthetic": _pairs([("refuted", 5, "synthetic")]),
        "curriculum": _pairs([("nei", 4, "curriculum")]),
    }
    v0 = assemble_variant("v0", slices)
    assert {p.source for p in v0} == {"fever", "scifact"}
    assert len(v0) == 5


def test_v1_includes_everything():
    slices = {
        "fever": _pairs([("supported", 3, "fever")]),
        "scifact": _pairs([("refuted", 2, "scifact")]),
        "synthetic": _pairs([("refuted", 5, "synthetic")]),
        "curriculum": _pairs([("nei", 4, "curriculum")]),
    }
    v1 = assemble_variant("v1", slices)
    assert len(v1) == 14
    assert {p.source for p in v1} == {"fever", "scifact", "synthetic", "curriculum"}


def test_class_counts_and_balanced_sampler_weights():
    pairs = _pairs([("supported", 8, "fever"), ("refuted", 2, "fever"), ("nei", 2, "fever")])
    assert class_counts(pairs) == {"supported": 8, "refuted": 2, "nei": 2}
    w = sampler_weights(pairs)
    sup_w = w[0]; ref_w = w[8]
    assert ref_w > sup_w
    assert abs(sum(w[:8]) - sum(w[8:10])) < 1e-9
