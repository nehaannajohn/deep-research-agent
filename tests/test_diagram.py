from dra.diagram import validate_mermaid, insert_diagram

GOOD = "```mermaid\ngraph LR\n  A[Seed] --> B[Model]\n  B --> C[Output]\n```"


def test_validate_accepts_well_formed_block():
    assert validate_mermaid(GOOD) is True


def test_validate_rejects_empty_or_nonmermaid():
    assert validate_mermaid("") is False
    assert validate_mermaid("```mermaid\n\n```") is False
    assert validate_mermaid("```mermaid\nnot a diagram type\n```") is False


def test_insert_places_diagram_after_summary():
    narrative = "## Summary\nIntro [c0].\n\n## Details\nMore [c1]."
    out = insert_diagram(narrative, GOOD)
    assert "## Architecture" in out
    assert out.index("## Summary") < out.index("## Architecture") < out.index("## Details")


def test_insert_noop_on_invalid_block():
    narrative = "## Summary\nIntro."
    assert insert_diagram(narrative, "garbage") == narrative


def test_llm_diagram_generator_extracts_valid_block():
    from dra.diagram import LLMDiagramGenerator
    class LLM:
        def complete(self, prompt, **kw):
            return "Here:\n```mermaid\nflowchart LR\n  A-->B\n  B-->C\n```\nDone."
    out = LLMDiagramGenerator(LLM()).generate("q", [], "## Summary\nx")
    assert out.startswith("```mermaid") and "flowchart" in out


def test_llm_diagram_generator_empty_on_failure():
    from dra.diagram import LLMDiagramGenerator
    class Boom:
        def complete(self, prompt, **kw):
            raise RuntimeError("down")
    assert LLMDiagramGenerator(Boom()).generate("q", [], "n") == ""


def test_llm_diagram_generator_empty_on_invalid_output():
    from dra.diagram import LLMDiagramGenerator
    class LLM:
        def complete(self, prompt, **kw):
            return "sorry, no diagram"
    assert LLMDiagramGenerator(LLM()).generate("q", [], "n") == ""
