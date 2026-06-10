from dra.loop import StubDeps, run_query
from dra.schemas import ResearchReport


def test_run_query_returns_empty_report():
    r = run_query("q", deps=StubDeps())
    assert isinstance(r, ResearchReport)
    assert r.query == "q"
    assert r.claims == []
