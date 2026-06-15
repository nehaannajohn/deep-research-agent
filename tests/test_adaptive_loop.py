"""Integration tests for run_query_adaptive's gate/repair/keep-best orchestration.

plan/route/synthesize/compose_report/detect_and_resolve are monkeypatched to thin
fakes so the test drives the LOOP logic (not re-testing synthesis). The verifier,
search, recommender, and fetcher are injected fakes; a passage whose source_id
starts with "good" verifies high, otherwise low.
"""
from __future__ import annotations

import dra.adaptive.loop as loop
from dra.adaptive.loop import run_query_adaptive
from dra.loop import Deps
from dra.schemas import Citation, Claim, Passage, ResearchReport
from dra.verify.base import VerifierResult


# ---- fakes ----

class _Gen:
    """generator.complete is only used by reformulate here; return a query that
    triggers the fake search to yield a 'good' passage."""
    def complete(self, prompt):
        return "reformulated good query"

    def complete_json(self, prompt):  # unused (synthesize/plan monkeypatched)
        return {}


class _Search:
    def __init__(self):
        self.queries = []

    def search(self, query, k=5):
        self.queries.append(query)
        sid = "good1" if "good" in query.lower() else "weak1"
        return type("R", (), {"passages": [Passage(source_id=sid, text=f"text {sid}",
                                                    url=f"https://src/{sid}")]})()


class _Verifier:
    def verify(self, claim, passages):
        good = any(p.source_id.startswith("good") for p in passages)
        return VerifierResult(label="supported" if good else "insufficient",
                              confidence=0.9 if good else 0.4)


def _fake_plan(query, gen):
    from dra.planner import Plan
    return Plan(core_query=query, subquestions=["sq1"], constraints={})


def _fake_synth(query, subq, passages, llm, start_index=0):
    if not passages:
        return []
    p = passages[-1]  # cite the most recently added passage (fetched/diversify wins)
    return [Claim(id=f"c{start_index}", text=f"claim::{p.source_id}", section=subq,
                  citations=[Citation(source_id=p.source_id, span=p.text)])]


def _fake_compose(query, p, claims, sources, gen, **kw):
    return ResearchReport(query=query, claims=claims, sources=sources)


def _patch(mp):
    mp.setattr(loop, "plan", _fake_plan)
    mp.setattr(loop, "route", lambda subq, gen: "web")
    mp.setattr(loop, "synthesize", _fake_synth)
    mp.setattr(loop, "compose_report", _fake_compose)
    mp.setattr(loop, "detect_and_resolve", lambda claims, judge: (claims, []))


def _deps(search):
    return Deps(generator=_Gen(), verifier=_Verifier(), search=search,
                diagram_generator=None, contradiction_judge=None)


# ---- tests ----

def test_no_repair_when_base_is_confident(monkeypatch):
    _patch(monkeypatch)

    class _GoodSearch(_Search):
        def search(self, query, k=5):
            return type("R", (), {"passages": [Passage(source_id="good1", text="t",
                                                       url="https://s/good1")]})()

    trace = []
    rep = run_query_adaptive("q", _deps(_GoodSearch()), tau=0.7, trace=trace)
    assert trace[0]["iters"] == 0 and trace[0]["via"] == "base"
    assert rep.claims[0].confidence == 0.9


def test_reformulate_repairs_weak_subquery(monkeypatch):
    _patch(monkeypatch)
    search = _Search()  # base "sq1" -> weak; reformulated "...good..." -> good
    trace = []
    rep = run_query_adaptive("q", _deps(search), tau=0.7, trace=trace)
    assert trace[0]["iters"] == 1
    assert trace[0]["via"] == "reformulate"
    assert trace[0]["final_score"] == 0.9
    assert rep.claims[0].confidence == 0.9


def test_no_progress_stops_after_one_iter(monkeypatch):
    _patch(monkeypatch)

    class _AlwaysWeak(_Search):
        def search(self, query, k=5):  # reformulation never helps
            return type("R", (), {"passages": [Passage(source_id="weak1", text="t",
                                                       url="https://s/weak1")]})()

    trace = []
    run_query_adaptive("q", _deps(_AlwaysWeak()), tau=0.7, eps=0.05, max_iters=3, trace=trace)
    # incumbent stays weak, no candidate beats it -> no progress -> stop after 1 iter
    assert trace[0]["iters"] == 1 and trace[0]["via"] == "base"
    assert trace[0]["final_score"] == 0.4


def test_diversify_repairs_when_reformulate_cannot(monkeypatch):
    _patch(monkeypatch)

    class _WeakSearch(_Search):
        def search(self, query, k=5):  # both base AND reformulation stay weak
            return type("R", (), {"passages": [Passage(source_id="weak1", text="t",
                                                       url="https://s/weak1")]})()

    class _RecLLM:
        def complete(self, prompt):
            return '[{"url": "https://new.gov/data", "kind": "stats", "covers": "x"}]'

    class _Fetcher:
        def fetch_many(self, urls, query):
            return [Passage(source_id="good_fetched", text="t", url=urls[0])] if urls else []

    trace = []
    rep = run_query_adaptive("q", _deps(_WeakSearch()), tau=0.7,
                             recommender_llm=_RecLLM(), fetcher=_Fetcher(), trace=trace)
    assert trace[0]["via"] == "diversify"
    assert trace[0]["final_score"] == 0.9
    assert trace[0]["n_recs"] == 1 and trace[0]["n_fetched"] == 1
    assert rep.claims[0].confidence == 0.9


def test_none_deps_returns_skeleton():
    rep = run_query_adaptive("q", None)
    assert isinstance(rep, ResearchReport) and rep.query == "q"
