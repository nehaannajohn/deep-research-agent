from dra.schemas import Citation, Claim, Passage, ResearchReport


def test_claim_defaults_to_unverified():
    c = Claim(id="c1", text="X improves Y", section="intro")
    assert c.verdict == "unverified"
    assert c.confidence is None
    assert c.citations == []


def test_report_roundtrips_json():
    p = Passage(source_id="s1", text="evidence text", url="http://x")
    c = Claim(
        id="c1",
        text="X improves Y",
        section="intro",
        citations=[Citation(source_id="s1", span="evidence text")],
        verdict="supported",
        confidence=0.9,
    )
    r = ResearchReport(query="q", claims=[c], sources=[p])
    back = ResearchReport.model_validate_json(r.model_dump_json())
    assert back.claims[0].verdict == "supported"
    assert back.claims[0].citations[0].source_id == "s1"
