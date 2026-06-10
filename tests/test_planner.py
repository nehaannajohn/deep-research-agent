from dra.planner import plan


class FakeLLM:
    def complete_json(self, prompt):
        return {"subquestions": ["What is X?", "How does Y work?", "  ", 5],
                "constraints": {"wants_visual": True, "focus": ["bias"]}}


def test_plan_parses_subquestions_and_constraints():
    p = plan("map the landscape", FakeLLM())
    assert p.subquestions == ["What is X?", "How does Y work?"]  # blank/non-str dropped
    assert p.constraints["wants_visual"] is True
    assert p.constraints["focus"] == ["bias"]
