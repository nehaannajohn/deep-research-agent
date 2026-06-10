from dra.planner import plan, _PLAN_PROMPT


class FakeLLM:
    def complete_json(self, prompt):
        return {"subquestions": ["What is X?", "How does Y work?", "  ", 5],
                "constraints": {"wants_visual": True, "focus": ["bias"]}}


def test_plan_parses_subquestions_and_constraints():
    p = plan("map the landscape", FakeLLM())
    assert p.subquestions == ["What is X?", "How does Y work?"]  # blank/non-str dropped
    assert p.constraints["wants_visual"] is True
    assert p.constraints["focus"] == ["bias"]


def test_plan_prompt_allows_single_subquestion_and_is_not_padded():
    p = _PLAN_PROMPT.lower()
    # must permit returning the query unchanged as ONE sub-question
    assert "single sub-question" in p or "one sub-question" in p
    # must justify splitting by distinct evidence, not a fixed count
    assert "distinct" in p
    # must NOT hardcode the old 3–6 count
    assert "3-6" not in p and "3–6" not in p
