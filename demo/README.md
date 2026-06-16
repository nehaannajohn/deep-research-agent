# Demo — Deep Research Agent pipeline replay

An interactive [Streamlit](https://streamlit.io) app that shows **how the agent works**:
pick one of the five DRA-Bench example queries (one per question type), then watch the MVP
pipeline run **stage by stage** — a progress stepper highlights the active stage and shows
that stage's real intermediate output, ending in the composed report with a **downloadable
PDF**.

It is a **replay**, not a live run: every payload is pre-baked from the committed sample
reports in [`docs/sample_reports/`](../docs/sample_reports/). That means the demo:

- needs **no AWS / Exa credentials** and makes **no API calls** — it always works, instantly;
- is **consistent** with the reports the repo already ships (the numbers behind it come from
  the trained cross-encoder **Verifier B · v0**, the configuration those reports used).

## Run it

```bash
brew install pango           # one system lib WeasyPrint needs for PDF export (macOS)
pip install -e ".[demo]"     # streamlit + markdown + weasyprint
python -m demo.build_fixtures # one-time: parse docs/sample_reports/ → demo/fixtures/
streamlit run demo/app.py
```

> The PDF export uses WeasyPrint, which needs the `pango` system library (`brew install
> pango` on macOS; `apt-get install libpango-1.0-0` on Debian/Ubuntu). If it isn't present,
> the app still runs and offers the report as a **Markdown** download instead.

The `build_fixtures` step is only needed once (or after the sample reports change); the
generated `demo/fixtures/*.json` are committed, so `streamlit run demo/app.py` works on a
fresh clone without it.

## The stages it visualizes

Mirrors `dra.loop.run_query`:

1. **Plan** — resolved brief + extracted constraints (`wants_visual` / `format` / `focus`) + sub-questions
2. **Route** — each sub-question tagged academic / web (Exa is the single MVP backend)
3. **Retrieve** — the source cards pulled for the sub-questions
4. **Synthesize** — atomic claims with candidate citations
5. **Verify** — per-claim **verdict + calibrated confidence** (the differentiator)
6. **Contradiction** — contested claim pairs, both sides kept
7. **Compose** — the grounded report (narrative + table / diagram + claim ledger) → **Download PDF**

## Files

| File | Role |
|---|---|
| `app.py` | the Streamlit UI — query picker, stage stepper, per-stage panels, PDF download |
| `build_fixtures.py` | parses `docs/sample_reports/*.md` (+ `plan_blocks.py`) → `fixtures/*.json` |
| `plan_blocks.py` | the planner outputs (sub-questions + constraints) — the only data not in the reports |
| `pdf.py` | report markdown → styled PDF (pure-Python: `markdown` → `xhtml2pdf`) |
| `fixtures/` | generated per-stage replay data (`*.json`) + pre-rendered diagram (`assets/*.png`) |

> The planning blocks in `plan_blocks.py` are reconstructed (the composed reports don't
> persist the planner's sub-questions) and are labelled as such in the UI. Everything else
> — sources, claims, verdicts, confidence, contradictions, narrative — is parsed directly
> from the committed reports.
