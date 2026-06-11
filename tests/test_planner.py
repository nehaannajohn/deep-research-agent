from dra.planner import plan, _SPLIT_PROMPT, _DECOMPOSE_PROMPT


class FakeLLM:
    """Two-step planner: dispatch on prompt — SPLIT then DECOMPOSE."""

    def complete_json(self, prompt):
        if "core_query" in prompt:  # planner SPLIT call
            return {"core_query": "map the landscape",
                    "constraints": {"wants_visual": True, "focus": ["bias"]}}
        return {"subquestions": ["What is X?", "How does Y work?", "  ", 5]}  # DECOMPOSE


def test_plan_parses_subquestions_and_constraints():
    p = plan("map the landscape, include a diagram", FakeLLM())
    assert p.core_query == "map the landscape"
    assert p.subquestions == ["What is X?", "How does Y work?"]  # blank/non-str dropped
    assert p.constraints["wants_visual"] is True
    assert p.constraints["focus"] == ["bias"]


class FakeAtomicLLM:
    """Atomic query: split returns the query unchanged, decompose returns one sub-question."""

    def complete_json(self, prompt):
        if "core_query" in prompt:
            return {"core_query": "what is the boiling point of water", "constraints": {}}
        return {"subquestions": ["what is the boiling point of water"]}


def test_atomic_query_returns_single_subquestion():
    p = plan("what is the boiling point of water", FakeAtomicLLM())
    assert p.core_query == "what is the boiling point of water"
    assert p.subquestions == ["what is the boiling point of water"]
    assert len(p.subquestions) == 1


class FakeEmptyDecompose:
    """Decompose returns nothing -> fall back to the core_query as a single sub-question."""

    def complete_json(self, prompt):
        if "core_query" in prompt:
            return {"core_query": "explain transformers", "constraints": {}}
        return {"subquestions": []}


def test_empty_decomposition_falls_back_to_core_query():
    p = plan("explain transformers", FakeEmptyDecompose())
    assert p.core_query == "explain transformers"
    assert p.subquestions == ["explain transformers"]


def test_split_prompt_separates_content_from_presentation():
    sp = _SPLIT_PROMPT.lower()
    assert "core_query" in sp
    assert "constraints" in sp
    # must instruct stripping presentation/format instructions
    assert "presentation" in sp or "format" in sp


def test_decompose_prompt_allows_single_subquestion_and_is_not_padded():
    p = _DECOMPOSE_PROMPT.lower()
    # must permit returning the query unchanged as ONE sub-question
    assert "single sub-question" in p or "one sub-question" in p
    # must justify splitting by distinct evidence, not a fixed count
    assert "distinct" in p
    # must NOT hardcode the old 3-6 count
    assert "3-6" not in p and "3–6" not in p
