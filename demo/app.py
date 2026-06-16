"""Deep Research Agent — pipeline replay (Streamlit demo).

Pick one of the five DRA-Bench example queries (one per question type) and watch the MVP
pipeline run stage by stage: a progress stepper highlights the active stage and the panel
below shows that stage's real intermediate output — sub-questions, retrieved sources,
atomic claims, per-claim verdict + calibrated confidence, contradictions — ending in the
composed report with a downloadable PDF.

This is a *replay*: every payload is pre-baked from ``docs/sample_reports/`` into
``demo/fixtures/`` by ``build_fixtures.py``. Nothing here calls the live pipeline, so the
demo needs no AWS/Exa credentials, runs instantly, and is consistent with the reports the
repo ships. The verifier behind the numbers is the trained cross-encoder **Verifier B
(v0)** — the configuration these sample reports were generated with.

Run:  ``streamlit run demo/app.py``  (after ``pip install -e ".[demo]"``).
"""
from __future__ import annotations

import json
import re
import sys
import time
from html import escape
from pathlib import Path

# `streamlit run demo/app.py` puts demo/ (not the repo root) on sys.path, so the
# package-qualified `from demo.pdf import ...` below can't resolve. Add the repo root so the
# app works both via `streamlit run demo/app.py` and `python -m demo.app`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st
import streamlit.components.v1 as components

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Stage definitions — name + one-line description, in pipeline order (mirrors dra.loop).
STAGES = [
    ("Plan", "Split the query into sub-questions + extract presentation constraints"),
    ("Route", "Tag each sub-question with a retrieval tool (Exa is the MVP backend)"),
    ("Retrieve", "Fetch verbatim evidence passages (Exa · k=5 · highlights)"),
    ("Synthesize", "Turn passages into atomic claims + candidate citations"),
    ("Verify", "Entailment-check each claim → verdict + calibrated confidence"),
    ("Contradiction", "Flag claim↔claim conflicts as contested"),
    ("Compose", "Assemble the grounded report + claim ledger → ResearchReport"),
]

VERDICT_COLORS = {
    "supported": "#2e7d32", "contested": "#ed6c02",
    "refuted": "#c62828", "insufficient": "#757575", "unverified": "#9e9e9e",
}


# --------------------------------------------------------------------------- data
@st.cache_data(show_spinner=False)
def load_fixtures() -> dict[str, dict]:
    fixtures = {}
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        fx = json.loads(path.read_text(encoding="utf-8"))
        fixtures[fx["slug"]] = fx
    return dict(sorted(fixtures.items(), key=lambda kv: kv[1]["type"]))


@st.cache_data(show_spinner=False)
def make_pdf(slug: str) -> bytes | None:
    """Build the PDF for a fixture; None if the PDF deps aren't installed."""
    from demo.pdf import report_to_pdf

    fx = load_fixtures()[slug]
    png = FIXTURES_DIR / fx["diagram_png"] if fx.get("diagram_png") else None
    return report_to_pdf(fx["report_markdown"], png)


# ----------------------------------------------------------------------- rendering
def render_stepper(slot, active: int, done: bool) -> None:
    """Draw the 7-stage progress bar; `active` is the lit stage, everything before it is
    complete. When `done`, every stage shows complete."""
    chips = []
    for i, (name, _) in enumerate(STAGES):
        if done or i < active:
            bg, fg, mark = "#15233b", "#ffffff", "✓"
        elif i == active:
            bg, fg, mark = "#2a5db0", "#ffffff", str(i + 1)
        else:
            bg, fg, mark = "#e6e9ef", "#9aa3b2", str(i + 1)
        chips.append(
            f'<div style="flex:1;text-align:center;min-width:78px">'
            f'<div style="width:30px;height:30px;line-height:30px;border-radius:50%;'
            f'margin:0 auto;background:{bg};color:{fg};font-weight:700;font-size:13px">{mark}</div>'
            f'<div style="font-size:11px;margin-top:4px;color:{fg if (done or i<=active) else "#9aa3b2"};'
            f'font-weight:{600 if i==active and not done else 400}">{name}</div></div>'
        )
    connectors = '<div style="flex:0 0 14px;border-top:2px solid #cdd3dd;margin-top:15px"></div>'
    slot.markdown(
        '<div style="display:flex;align-items:flex-start;justify-content:space-between">'
        + connectors.join(chips) + "</div>",
        unsafe_allow_html=True,
    )


def _chips(items: list[str], color: str = "#e8eef7", fg: str = "#1f3a5f") -> str:
    return " ".join(
        f'<span style="background:{color};color:{fg};border-radius:10px;padding:1px 8px;'
        f'font-size:11px;margin-right:4px;white-space:nowrap">{escape(str(it))}</span>' for it in items
    )


def render_mermaid(fx: dict, height: int = 460) -> None:
    """Show the architecture diagram — the pre-rendered PNG if present (no network), else
    rendered live via mermaid.js."""
    png = FIXTURES_DIR / fx["diagram_png"] if fx.get("diagram_png") else None
    if png and png.exists():
        # Centre the diagram at a modest width — the PNG is tall/narrow, so stretching it
        # to the full container makes it oversized.
        _, mid, _ = st.columns([1, 2, 1])
        mid.image(str(png), use_container_width=True)
    elif fx.get("mermaid"):
        components.html(
            f'<div class="mermaid">{fx["mermaid"]}</div>'
            '<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>'
            "<script>mermaid.initialize({startOnLoad:true,theme:'neutral'});</script>",
            height=height, scrolling=True,
        )


def _claim_table(claims: list[dict], show_verdict: bool) -> str:
    """HTML table of claims. Before Verify: id · claim · citations. After: + verdict badge
    and a calibrated-confidence bar."""
    head = "<tr><th>#</th><th>Claim</th>"
    head += "<th>Cites</th>" if not show_verdict else "<th>Verdict</th><th>Confidence</th>"
    head += "</tr>"
    rows = []
    for c in claims:
        cells = f'<td style="color:#2a5db0;font-weight:600">{escape(c["id"])}</td><td>{escape(c["text"])}</td>'
        if not show_verdict:
            n = len(c["citations"])
            cells += f'<td style="white-space:nowrap;color:#5a6473">{n} src</td>'
        else:
            col = VERDICT_COLORS.get(c["verdict"], "#9e9e9e")
            conf = c["confidence"] or 0.0
            badge = (f'<span style="background:{col};color:#fff;border-radius:9px;padding:1px 8px;'
                     f'font-size:11px">{escape(c["verdict"])}</span>')
            bar = (f'<div style="background:#eceff3;border-radius:6px;width:120px;display:inline-block;'
                   f'vertical-align:middle"><div style="width:{conf*100:.0f}%;background:{col};height:10px;'
                   f'border-radius:6px"></div></div>'
                   f'<span style="font-size:11px;margin-left:6px">{conf:.2f}</span>')
            cells += f"<td>{badge}</td><td style='white-space:nowrap'>{bar}</td>"
        rows.append(f"<tr>{cells}</tr>")
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:12.5px">'
        f'<thead style="text-align:left;color:#15233b;border-bottom:2px solid #15233b">{head}</thead>'
        + "".join(f'<tbody style="border-bottom:1px solid #eceff3">{r}</tbody>' for r in rows)
        + "</table>"
    )


def render_panel(slot, fx: dict, stage: int) -> None:
    """Render the result panel for `stage` into `slot`."""
    with slot.container():
        name, desc = STAGES[stage]
        st.caption(f"**Stage {stage + 1}/7 · {name}** — {desc}")

        if name == "Plan":
            plan = fx["plan"]
            st.markdown(f"**Resolved brief.** {escape(plan['resolved_brief'])}")
            con = plan["constraints"]
            st.markdown(
                "**Extracted constraints.** "
                + _chips([f"wants_visual: {con['wants_visual']}", f"format: {con['format']}",
                          f"focus: {con['focus']}"], color="#fff3e0", fg="#9c5700"),
                unsafe_allow_html=True)
            st.markdown(f"**Decomposition** ({len(plan['subquestions'])} sub-questions):")
            for i, sq in enumerate(plan["subquestions"], 1):
                st.markdown(f"{i}. {escape(sq['text'])}")

        elif name == "Route":
            st.markdown("Each sub-question is tagged with a retrieval tool "
                        "(label only — Exa is the single MVP backend):")
            for sq in fx["plan"]["subquestions"]:
                tag = sq["route"]
                col = "#6a1b9a" if tag == "academic" else "#1565c0"
                st.markdown(
                    f'<span style="background:{col};color:#fff;border-radius:9px;padding:1px 9px;'
                    f'font-size:11px;margin-right:8px">{tag}</span> {escape(sq["text"])}',
                    unsafe_allow_html=True)

        elif name == "Retrieve":
            srcs = fx["sources"]
            st.markdown(f"Retrieved **{len(srcs)} sources** across the sub-questions "
                        "(verbatim highlights, k=5 each):")
            cols = st.columns(2)
            for i, s in enumerate(srcs):
                with cols[i % 2]:
                    link = f'<a href="{escape(s["url"])}" target="_blank">{escape(s["domain"])}</a>' \
                        if s["url"] else f'<span style="color:#888">{escape(s["domain"])}</span>'
                    st.markdown(
                        f'<div style="border:1px solid #e0e4ea;border-radius:8px;padding:8px 10px;'
                        f'margin-bottom:8px"><div style="font-size:12.5px;font-weight:600;color:#15233b">'
                        f'{escape(s["title"][:110])}</div><div style="font-size:11px;margin-top:3px">'
                        f'{link}</div></div>', unsafe_allow_html=True)

        elif name == "Synthesize":
            st.markdown(f"Extracted **{len(fx['claims'])} atomic claims** with candidate citations "
                        "(not yet verified):")
            st.markdown(_claim_table(fx["claims"], show_verdict=False), unsafe_allow_html=True)

        elif name == "Verify":
            meta = fx["metadata"]
            bd = meta.get("breakdown", {})
            c1, c2 = st.columns([1, 2])
            c1.metric("Overall confidence", f"{meta.get('overall_confidence', 0):.3f}")
            c2.markdown("**Verdict breakdown** &nbsp; " + _chips(
                [f"{k}: {v}" for k, v in bd.items()]), unsafe_allow_html=True)
            st.markdown("Each claim is entailment-checked against its cited passages — "
                        "**verdict + calibrated confidence** (Verifier B · v0):")
            st.markdown(_claim_table(fx["claims"], show_verdict=True), unsafe_allow_html=True)

        elif name == "Contradiction":
            pairs = fx["contradictions"]
            by_id = {c["id"]: c for c in fx["claims"]}
            if not pairs:
                st.success("No cross-source contradictions detected — claims are mutually consistent.")
            else:
                st.markdown(f"Detected **{len(pairs)} contradicting claim pair(s)** — both sides are "
                            "kept and flagged, never silently dropped:")
                for a, b in pairs:
                    ca, cb = by_id.get(a), by_id.get(b)
                    if ca and cb:
                        st.markdown(
                            f'<div style="border-left:3px solid #ed6c02;padding:4px 10px;margin-bottom:8px">'
                            f'<b>{a}</b> {escape(ca["text"])}<br><span style="color:#ed6c02">⟷</span> '
                            f'<b>{b}</b> {escape(cb["text"])}</div>', unsafe_allow_html=True)

        elif name == "Compose":
            render_compose(fx)


def render_compose(fx: dict) -> None:
    """Final stage: the composed report (narrative + diagram + ledger + sources) and the
    PDF download."""
    st.markdown("#### 📄 Composed report")
    # Render the narrative, dropping the raw mermaid fence in favour of the rendered
    # diagram shown exactly where it was authored (under the "Architecture" heading).
    narrative = fx["narrative"]
    parts = re.split(r"(?:```mermaid\s*\n.*?\n```)", narrative, maxsplit=1, flags=re.DOTALL) \
        if fx.get("mermaid") else [narrative]
    st.markdown(parts[0])
    if len(parts) > 1:
        render_mermaid(fx)
        st.markdown(parts[1])

    with st.expander("Claim ledger (per-claim verdict + confidence)", expanded=False):
        st.markdown(_claim_table(fx["claims"], show_verdict=True), unsafe_allow_html=True)
    with st.expander(f"Sources ({len(fx['sources'])})", expanded=False):
        for s in fx["sources"]:
            label = s["url"] or s["domain"]
            st.markdown(f"- [{escape(s['title'][:120])}]({label})" if s["url"]
                        else f"- {escape(s['title'][:120])} _(Exa id)_")

    st.divider()
    try:
        pdf = make_pdf(fx["slug"])
        st.download_button("⬇️  Download PDF report", data=pdf,
                           file_name=f"{fx['slug']}.pdf", mime="application/pdf",
                           type="primary", use_container_width=True)
    except Exception as exc:  # noqa: BLE001 — surface a friendly hint, offer markdown instead
        st.warning(f"PDF generation unavailable ({type(exc).__name__}). WeasyPrint needs the "
                   "`pango` system library — `brew install pango`. Markdown download below.")
        st.download_button("⬇️  Download report (Markdown)", data=fx["report_markdown"],
                           file_name=f"{fx['slug']}.md", mime="text/markdown",
                           use_container_width=True)


# ---------------------------------------------------------------------------- main
def main() -> None:
    st.set_page_config(page_title="Deep Research Agent — pipeline replay",
                       page_icon="🔎", layout="wide")
    st.title("🔎 Deep Research Agent — pipeline replay")
    st.caption("Watch the MVP pipeline run stage by stage on a DRA-Bench example. "
               "Replayed from pre-computed runs (Verifier B · v0) — no live API calls.")

    fixtures = load_fixtures()
    if not fixtures:
        st.error("No fixtures found. Generate them first:  `python -m demo.build_fixtures`")
        return

    n = len(STAGES)
    st.session_state.setdefault("stage", {})  # slug -> current stage index (-1 = not started)

    # Stage navigation uses on_click callbacks so the state mutates BEFORE the script
    # reruns — keeping the Back/Next disabled states and the rendered panel consistent
    # (reading session_state after the button instead would lag one click behind).
    def _start(s: str) -> None:
        st.session_state.stage[s] = 0

    def _step(s: str, delta: int) -> None:
        st.session_state.stage[s] = max(0, min(st.session_state.stage.get(s, 0) + delta, n - 1))

    with st.sidebar:
        st.header("Example query")
        labels = {s: f"Type {fx['type']} · {fx['type_label'].split('·')[0].strip()}"
                  for s, fx in fixtures.items()}
        slug = st.radio("DRA-Bench question type", list(fixtures),
                        format_func=lambda s: labels[s])
        fx = fixtures[slug]
        st.markdown(f"**Query**\n\n> {fx['query']}")
        st.markdown(f"<small>Expected behavior: <b>{escape(fx['type_label'])}</b></small>",
                    unsafe_allow_html=True)
        st.divider()

        cur = st.session_state.stage.get(slug, -1)
        started = cur >= 0
        manual = st.toggle("Step through manually", value=True,
                           help="On: advance one stage at a time with Back / Next. "
                                "Off: auto-play through all stages.")
        run, speed = False, "normal"
        if manual:
            st.button("↻  Restart" if started else "▶️  Start", type="primary",
                      use_container_width=True, on_click=_start, args=(slug,))
            c1, c2 = st.columns(2)
            c1.button("◀ Back", use_container_width=True, disabled=not started or cur <= 0,
                      on_click=_step, args=(slug, -1))
            c2.button("Next ▶", use_container_width=True, disabled=not started or cur >= n - 1,
                      on_click=_step, args=(slug, 1))
        else:
            speed = st.select_slider("Auto-play speed",
                                     ["very slow", "slow", "normal", "fast", "instant"], "slow")
            run = st.button("▶️  Run the pipeline", type="primary", use_container_width=True)

    delay = {"very slow": 2.5, "slow": 1.6, "normal": 0.9, "fast": 0.4, "instant": 0.0}[speed]

    if run:  # auto-play just triggered — start at the first stage
        cur = 0
    if cur < 0:  # not started yet — greyed stepper + a prompt
        render_stepper(st.empty(), active=-1, done=False)
        how = ("press **Start**, then move with **Back / Next**" if manual
               else "press **Run the pipeline**")
        st.info(f"⬅️  Pick a query and {how} to watch it work, stage by stage.")
        return

    step_slot, panel_slot = st.empty(), st.empty()
    if run and not manual:  # auto-play: animate through every stage
        for i in range(n):
            render_stepper(step_slot, active=i, done=(i == n - 1))
            render_panel(panel_slot, fx, i)
            if i < n - 1 and delay:
                time.sleep(delay)
        st.session_state.stage[slug] = n - 1
    else:  # manual stepping, or a static rerun (e.g. PDF download click)
        render_stepper(step_slot, active=cur, done=(cur == n - 1))
        render_panel(panel_slot, fx, cur)
        if manual and cur < n - 1:
            st.caption(f"⬅️  Use **Back / Next** in the sidebar to move between stages "
                       f"— stage {cur + 1} of {n}.")


if __name__ == "__main__":
    main()
