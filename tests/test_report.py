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
