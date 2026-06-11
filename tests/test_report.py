"""Report composition — deterministic layer + (later) narrative, with a fake LLM."""
from dra.planner import Plan
from dra.schemas import Citation, Claim, Passage
from dra.report import rollup_metadata, render_appendix


def _claim(cid, text, section, verdict="unverified", conf=None, sids=("s1",)):
    return Claim(id=cid, text=text, section=section, verdict=verdict, confidence=conf,
                 citations=[Citation(source_id=s, span="span") for s in sids])


PLAN = Plan(subquestions=["sq A", "sq B"], constraints={})


def test_rollup_verified_confidence_breakdown_coverage_disclaimers():
    plan3 = Plan(subquestions=["sq A", "sq B", "sq C"], constraints={})
    claims = [
        _claim("c0", "A1", "sq A", "supported", 0.9),
        _claim("c1", "A2", "sq A", "contested", 0.6),
        _claim("c2", "B1", "sq B", "insufficient", 0.4),
    ]
    md = rollup_metadata(plan3, claims, verified=True)
    assert md.overall_confidence == round((0.9 + 0.6 + 0.4) / 3, 3)
    assert md.confidence_breakdown["supported"] == {"count": 1, "mean_conf": 0.9}
    assert md.coverage == 0.333  # only sq A had a supported claim, of 3 sub-questions
    assert any("contested" in d for d in md.disclaimers)
    assert any("insufficient" in d for d in md.disclaimers)
    assert any("Coverage is limited" in d for d in md.disclaimers)  # 0.333 < 0.5 threshold


def test_rollup_unverified_has_no_confidence_or_disclaimers():
    claims = [_claim("c0", "A1", "sq A"), _claim("c1", "B1", "sq B")]
    md = rollup_metadata(PLAN, claims, verified=False)
    assert md.overall_confidence is None
    assert md.confidence_breakdown == {}
    assert md.disclaimers == []
    assert md.coverage == 1.0  # both sub-questions have a claim


def test_render_appendix_verified_has_verdict_and_confidence_columns():
    claims = [_claim("c0", "A1", "sq A", "supported", 0.88, ("s1", "s2")),
              _claim("c1", "A2", "sq A", "insufficient", 0.4)]  # -> a disclaimer fires
    md = rollup_metadata(PLAN, claims, verified=True)
    out = render_appendix(claims, [Passage(source_id="s1", text="t", title="T1")], md, verified=True)
    assert "## Detailed Citation Results" in out
    assert "Verdict" in out and "Conf" in out
    assert "supported" in out and "0.88" in out
    assert "## Confidence & Coverage" in out
    assert "## Disclaimers" in out
    assert "## Sources" in out and "[s1]" in out


def test_render_appendix_unverified_omits_verdict_confidence_disclaimers():
    claims = [_claim("c0", "A1", "sq A")]
    md = rollup_metadata(PLAN, claims, verified=False)
    out = render_appendix(claims, [Passage(source_id="s1", text="t")], md, verified=False)
    assert "## Detailed Citation Results" in out
    assert "Verdict" not in out and "Conf" not in out
    assert "## Confidence & Coverage" not in out
    assert "## Disclaimers" not in out
    assert "## Sources" in out


class FakeGen:
    """Fake generator: returns a fixed narrative; records the prompt it received."""
    def __init__(self, narrative):
        self.narrative = narrative
        self.last_prompt = None

    def complete(self, prompt, **kw):
        self.last_prompt = prompt
        return self.narrative


def test_compose_narrative_passes_claim_ids_and_keeps_valid_refs():
    from dra.report import compose_narrative
    gen = FakeGen("## Summary\nWater boils at 100C [c0].")
    claims = [_claim("c0", "Water boils at 100C", "sq A", "supported", 0.9)]
    out = compose_narrative("q", PLAN, claims, gen, verified=True)
    assert "[c0]" in out                       # valid ref kept
    assert "[c0]" in gen.last_prompt            # claim id given to the model


def test_compose_narrative_strips_unknown_claim_refs():
    from dra.report import compose_narrative
    gen = FakeGen("## Summary\nReal [c0]. Hallucinated [c9].")
    claims = [_claim("c0", "Real claim", "sq A")]
    out = compose_narrative("q", PLAN, claims, gen, verified=False)
    assert "[c0]" in out
    assert "[c9]" not in out  # unknown ref dropped (constrain-by-construction guard)


def test_compose_narrative_requests_mermaid_when_wants_visual():
    from dra.report import compose_narrative
    gen = FakeGen("## Summary\n[c0]")
    plan_visual = Plan(subquestions=["sq A"], constraints={"wants_visual": True})
    compose_narrative("q", plan_visual, [_claim("c0", "x", "sq A")], gen, verified=False)
    assert "mermaid" in gen.last_prompt.lower()


def test_compose_narrative_falls_back_on_llm_failure():
    from dra.report import compose_narrative

    class BoomGen:
        def complete(self, prompt, **kw):
            raise RuntimeError("model down")

    out = compose_narrative("the query", PLAN, [_claim("c0", "x", "sq A")], BoomGen(), verified=False)
    assert "## Summary" in out and "the query" in out  # deterministic fallback narrative
