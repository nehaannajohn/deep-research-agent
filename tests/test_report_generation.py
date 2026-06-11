from experiments.report_generation import augment_query


def test_augment_query_appends_diagram_instruction():
    out = augment_query("How does X work?")
    assert out.startswith("How does X work?")
    assert "architecture diagram" in out.lower()
