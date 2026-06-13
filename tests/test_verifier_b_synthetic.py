from __future__ import annotations

from dra.verify.train.synthetic import (
    PERTURBATIONS,
    PERTURBATION_LABEL,
    build_perturbation_prompt,
    is_genuine_negative,
    parse_synthetic_claim,
)


def test_every_perturbation_has_a_label_in_the_3way_space():
    assert set(PERTURBATIONS) == set(PERTURBATION_LABEL)
    assert set(PERTURBATION_LABEL.values()) <= {"refuted", "nei"}


def test_prompt_contains_passage_and_names_the_perturbation():
    p = build_perturbation_prompt("Aspirin reduced risk by 40% in the trial.", "number")
    assert "Aspirin reduced risk by 40%" in p
    assert "number" in p.lower()


def test_parse_extracts_claim_from_json_or_plain():
    assert parse_synthetic_claim('{"claim": "Aspirin reduced risk by 80%."}') == "Aspirin reduced risk by 80%."
    assert parse_synthetic_claim("Aspirin reduced risk by 80%.") == "Aspirin reduced risk by 80%."
    assert parse_synthetic_claim("") is None
    assert parse_synthetic_claim("   ") is None


class _FakeJudge:
    def __init__(self, verdict): self._v = verdict
    def verdict(self, claim, passages): return self._v


def test_is_genuine_negative_true_when_judge_does_not_support():
    from dra.schemas import Passage
    psg = [Passage(source_id="s", text="passage")]
    assert is_genuine_negative("c", psg, _FakeJudge("refuted")) is True
    assert is_genuine_negative("c", psg, _FakeJudge("insufficient")) is True
    assert is_genuine_negative("c", psg, _FakeJudge("supported")) is False
