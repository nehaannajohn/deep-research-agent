from dra.loop import Deps, run_query
from dra.schemas import Passage
from dra.search.base import SearchResult, SearchTool
from dra.verify.base import Verifier, VerifierResult


class FakeGen:
    """One fake stands in for planner (complete_json), synthesis (complete_json),
    and router (complete), dispatching on prompt content."""

    def complete(self, prompt, **kw):  # router label (unused) + report narrative
        return "## Summary\nFinding [c0]."

    def complete_json(self, prompt):
        if "subquestions" in prompt:  # planner prompt
            return {"subquestions": ["sq1"], "constraints": {}}
        return {"claims": [{"text": "Claim X", "citations": ["s1"]}]}  # synthesis prompt


class FakeSearch(SearchTool):
    name = "fake"

    def search(self, query, k=10):
        return SearchResult(passages=[Passage(source_id="s1", text="Evidence.", url="u", title="T")])


class FakeVerifier(Verifier):
    def verify(self, claim, passages):
        return VerifierResult(label="supported", confidence=0.8)


def test_singlepass_end_to_end():
    report = run_query("explain X", Deps(generator=FakeGen(), verifier=FakeVerifier(), search=FakeSearch()))
    assert len(report.claims) == 1
    c = report.claims[0]
    assert c.text == "Claim X"
    assert c.verdict == "supported"
    assert c.confidence == 0.8
    assert c.citations[0].source_id == "s1"
    assert len(report.sources) == 1
    assert report.resolved_brief == "sq1"
    assert "Claim X" in report.report_markdown
    assert "## Detailed Citation Results" in report.report_markdown
