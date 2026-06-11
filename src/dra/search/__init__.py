"""Search backends behind one `SearchTool` interface."""

# Settled excerpt budget (experiments/results stage2 → VERDICT_maxchars.md): 2k reliably
# captures the substantive span (results + framing) without 4k's redundancy/context bloat.
EXA_MAX_CHARS = 2000


def default_search_tool(cfg):
    """Default retrieval backend = **Exa**, per the Phase-1 bake-off
    (`data/bakeoff_results.json`): best judged relevance (0.92), best recall@k
    (0.33 overall, 0.80 on technical), and fastest (1.4s) — and it covers both
    academic and general/web, so one backend suffices for the MVP. Tavily is a
    viable but slower/lower-relevance fallback; Semantic Scholar was deprioritized
    (keyless rate-limiting; redundant with Exa for papers).

    Wrapped in a TTL'd retrieval cache when `cfg.retrieval_cache_enabled`
    (default on) so repeated eval runs reuse passages; experiment scripts build
    ExaSearch directly to bypass it."""
    from dra.search.exa import ExaSearch

    exa = ExaSearch(cfg.exa_key, max_chars=EXA_MAX_CHARS)
    if getattr(cfg, "retrieval_cache_enabled", True):  # on by default; matches Config default
        from dra.search.cache import CachingSearchTool

        return CachingSearchTool(
            exa,
            cache_dir=cfg.retrieval_cache_dir,
            ttl_seconds=cfg.retrieval_cache_ttl_s,
        )
    return exa
