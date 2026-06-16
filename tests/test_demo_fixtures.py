"""Tests for the demo fixture builder — the parser that turns committed sample reports
into replay fixtures. No network, no Streamlit, no PDF deps required."""
from __future__ import annotations

import pytest

from demo import build_fixtures as bf
from demo.plan_blocks import PLAN_BLOCKS

SAMPLE = """# Research Report
**Query:** Does X cause Y?

## Summary
A short summary [c0].

```mermaid
graph LR
    A --> B
```

## Detail
More prose [c1].

---

## Detailed Citation Results
| # | Claim | Verdict | Conf | Sources |
|---|---|---|---|---|
| c0 | X is associated with Y. | contested | 0.87 | https://a.example/p, 123456 |
| c1 | Z is unrelated. | supported | 0.42 | https://b.example/q |

## Confidence & Coverage
- Overall confidence: 0.645   ·   Coverage: 1.0
- Breakdown: supported 1 · contested 1

## Disclaimers
- 1 finding(s) are contested — sources disagree; both sides are shown.
- Findings [c0] and [c1] contradict each other; both sides are shown.

## Sources
- [https://a.example/p] Source A Title
- [123456] Bare Exa Id Title
- [https://b.example/q] Source B Title
"""


def test_query_parsed():
    assert bf._query(SAMPLE) == "Does X cause Y?"


def test_claims_parsed_with_verdict_confidence_and_citations():
    claims = bf._claims(SAMPLE)
    assert [c["id"] for c in claims] == ["c0", "c1"]
    assert claims[0]["verdict"] == "contested"
    assert claims[0]["confidence"] == pytest.approx(0.87)
    assert claims[0]["citations"] == ["https://a.example/p", "123456"]
    assert claims[1]["verdict"] == "supported"


def test_metadata_and_breakdown():
    meta = bf._metadata(SAMPLE)
    assert meta["overall_confidence"] == pytest.approx(0.645)
    assert meta["coverage"] == pytest.approx(1.0)
    assert meta["breakdown"] == {"supported": 1, "contested": 1}


def test_contradictions_extracted_from_disclaimers():
    pairs = bf._contradictions(bf._disclaimers(SAMPLE))
    assert pairs == [["c0", "c1"]]


def test_sources_distinguish_url_from_bare_id():
    srcs = bf._sources(SAMPLE)
    assert len(srcs) == 3
    assert srcs[0]["url"] == "https://a.example/p" and srcs[0]["domain"] == "a.example"
    assert srcs[1]["url"] == "" and "Exa" in srcs[1]["domain"]  # bare id → no URL


def test_mermaid_extracted():
    assert bf._mermaid(SAMPLE).startswith("graph LR")
    assert bf._mermaid("no diagram here") is None


def test_narrative_stops_before_citation_table():
    narr = bf._narrative(SAMPLE)
    assert "A short summary" in narr
    assert "Detailed Citation Results" not in narr


def test_malformed_claim_row_fails_loudly():
    bad = SAMPLE.replace("| c1 | Z is unrelated. | supported | 0.42 | https://b.example/q |",
                         "| c1 | broken |")
    with pytest.raises(ValueError):
        bf._claims(bad)


def test_every_sample_report_builds_a_complete_fixture():
    """Smoke test against the real committed reports — every fixture has the fields the
    app reads, for all five DRA-Bench types."""
    for slug in PLAN_BLOCKS:
        fx = bf.build_fixture(slug)
        assert fx["query"] and fx["claims"] and fx["sources"]
        assert fx["plan"]["subquestions"]
        assert set(fx["metadata"]) == {"overall_confidence", "coverage", "breakdown"}
        for c in fx["claims"]:
            assert c["verdict"] in {"supported", "refuted", "insufficient", "contested", "unverified"}
            assert 0.0 <= (c["confidence"] or 0) <= 1.0
