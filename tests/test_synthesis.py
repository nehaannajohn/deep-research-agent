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
    claims = synthesize("overall query", "subq", passages, FakeLLM())
    assert [c.text for c in claims] == ["Claim A", "Claim B"]
    assert claims[0].citations[0].source_id == "s1"
    assert claims[0].citations[0].span == "Evidence one."  # span = verbatim passage text
    assert [c.source_id for c in claims[1].citations] == ["s2"]  # bogus id dropped
    assert claims[0].id == "c0" and claims[1].id == "c1"
    assert claims[0].section == "subq"


class CapturingLLM:
    def __init__(self):
        self.prompt = None

    def complete_json(self, prompt):
        self.prompt = prompt
        return {"claims": [{"text": "C", "citations": ["s1"]}]}


def test_synthesize_includes_overall_query_and_full_passage_text():
    llm = CapturingLLM()
    long_text = "X" * 1200  # > old 600-char truncation
    synthesize("OVERALL QUERY TEXT", "the sub-question", [Passage(source_id="s1", text=long_text)], llm)
    assert "OVERALL QUERY TEXT" in llm.prompt
    assert "the sub-question" in llm.prompt
    assert long_text in llm.prompt  # full passage, not truncated to 600
