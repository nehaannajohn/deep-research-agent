from dra.loop import run_query
from dra.schemas import ResearchReport


def test_run_query_none_deps_returns_empty_report():
    r = run_query("q")
    assert isinstance(r, ResearchReport)
    assert r.query == "q"
    assert r.claims == []
