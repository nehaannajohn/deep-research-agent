"""Search backends behind one `SearchTool` interface."""


def default_search_tool(cfg):
    """Default retrieval backend = **Exa**, per the Phase-1 bake-off
    (`data/bakeoff_results.json`): best judged relevance (0.92), best recall@k
    (0.33 overall, 0.80 on technical), and fastest (1.4s) — and it covers both
    academic and general/web, so one backend suffices for the MVP. Tavily is a
    viable but slower/lower-relevance fallback; Semantic Scholar was deprioritized
    (keyless rate-limiting; redundant with Exa for papers)."""
    from dra.search.exa import ExaSearch

    return ExaSearch(cfg.exa_key)
