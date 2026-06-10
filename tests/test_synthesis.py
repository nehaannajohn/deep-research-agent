from dra.schemas import Passage
from dra.synthesis import synthesize


class FakeLLM:
    def complete_json(self, prompt):
        return {"claims": [
            {"text": "Claim A", "citations": ["s1"]},
            {"text": "Claim B", "citations": ["s2", "s_bogus"]},
            {"text": "  ", "citations": ["s1"]},          # empty text -> dropped
            {"text": "Ungrounded", "citations": ["nope"]},  # no valid citation -> dropped
        ]}


def test_synthesize_builds_grounded_claims():
    passages = [Passage(source_id="s1", text="Evidence one."), Passage(source_id="s2", text="Evidence two.")]
    claims = synthesize("subq", passages, FakeLLM())
    assert [c.text for c in claims] == ["Claim A", "Claim B"]
    assert claims[0].citations[0].source_id == "s1"
    assert claims[0].citations[0].span == "Evidence one."  # span = verbatim passage text
    assert [c.source_id for c in claims[1].citations] == ["s2"]  # bogus id dropped
    assert claims[0].id == "c0" and claims[1].id == "c1"
    assert claims[0].section == "subq"
