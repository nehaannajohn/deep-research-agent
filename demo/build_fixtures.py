"""Build the demo replay fixtures from the committed sample reports.

Parses each ``docs/sample_reports/<slug>.md`` into a self-contained
``demo/fixtures/<slug>.json`` that holds one payload per pipeline stage, then merges in
the planner block from ``plan_blocks.py`` (the only stage data not present in the
markdown). The Streamlit app (``app.py``) reads these fixtures and never touches the live
pipeline — so the demo needs no AWS/Exa credentials and is byte-consistent with the
reports the repo already ships.

The parser is deliberately tolerant of the exact sample-report shape:
``# Research Report`` → ``**Query:**`` → narrative (optional ```mermaid``` + table) →
``## Detailed Citation Results`` table → ``## Confidence & Coverage`` → ``## Disclaimers``
→ ``## Sources``. If any one report drifts, the offending field fails loudly rather than
silently emitting a half-built fixture.

Run:  ``python -m demo.build_fixtures``  (from the repo root).
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from demo.plan_blocks import PLAN_BLOCKS, TYPE_META

REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "docs" / "sample_reports"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ASSETS_DIR = FIXTURES_DIR / "assets"


# --------------------------------------------------------------------------- parsing
def _query(md: str) -> str:
    m = re.search(r"^\*\*Query:\*\*\s*(.+?)\s*$", md, re.MULTILINE)
    if not m:
        raise ValueError("no **Query:** line found")
    return m.group(1).strip()


def _section(md: str, heading: str) -> str:
    """Return the body of the ``## <heading>`` section (up to the next ## or end)."""
    pat = rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)"
    m = re.search(pat, md, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _narrative(md: str) -> str:
    """Everything between the Query line and the ``---`` that precedes the citation table —
    this is the composed report body (summary, sections, any mermaid block + table)."""
    after_q = md.split("**Query:**", 1)[-1]
    after_q = after_q.split("\n", 1)[-1]  # drop the rest of the query line
    return after_q.split("\n## Detailed Citation Results", 1)[0].rstrip().rstrip("-").rstrip()


def _claims(md: str) -> list[dict]:
    body = _section(md, "Detailed Citation Results")
    claims = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("| c"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            raise ValueError(f"malformed claim row: {line!r}")
        cid, text, verdict, conf, sources = cells[:5]
        claims.append({
            "id": cid,
            "text": text,
            "verdict": verdict.lower(),
            "confidence": float(conf),
            "citations": [s.strip() for s in sources.split(",") if s.strip()],
        })
    if not claims:
        raise ValueError("no claim rows parsed")
    return claims


def _metadata(md: str) -> dict:
    body = _section(md, "Confidence & Coverage")
    conf = re.search(r"Overall confidence:\s*([0-9.]+)", body)
    cov = re.search(r"Coverage:\s*([0-9.]+)", body)
    breakdown: dict[str, int] = {}
    bm = re.search(r"Breakdown:\s*(.+)", body)
    if bm:
        for part in bm.group(1).split("·"):
            tok = part.strip().split()
            if len(tok) == 2 and tok[1].isdigit():
                breakdown[tok[0]] = int(tok[1])
    return {
        "overall_confidence": float(conf.group(1)) if conf else None,
        "coverage": float(cov.group(1)) if cov else None,
        "breakdown": breakdown,
    }


def _disclaimers(md: str) -> list[str]:
    body = _section(md, "Disclaimers")
    return [ln.strip()[2:].strip() for ln in body.splitlines() if ln.strip().startswith("- ")]


def _contradictions(disclaimers: list[str]) -> list[list[str]]:
    pairs = []
    for d in disclaimers:
        m = re.search(r"\[(c\d+)\]\s+and\s+\[(c\d+)\]\s+contradict", d)
        if m:
            pairs.append([m.group(1), m.group(2)])
    return pairs


def _sources(md: str) -> list[dict]:
    body = _section(md, "Sources")
    out = []
    for ln in body.splitlines():
        m = re.match(r"^- \[(.*?)\]\s*(.*)$", ln.strip())
        if not m:
            continue
        ref, title = m.group(1).strip(), m.group(2).strip()
        is_url = ref.startswith("http")
        out.append({
            "ref": ref,
            "title": title or ref,
            "url": ref if is_url else "",
            "domain": urlparse(ref).netloc if is_url else "Exa retrieval id",
        })
    return out


def _mermaid(md: str) -> str | None:
    m = re.search(r"```mermaid\s*\n(.*?)\n```", md, re.DOTALL)
    return m.group(1).strip() if m else None


# ------------------------------------------------------------------- diagram → PNG
def _render_mermaid_png(code: str, out_path: Path) -> bool:
    """Best-effort raster of a mermaid diagram for the PDF. Tries the mermaid CLI, then
    the mermaid.ink web renderer; returns False if neither is available (the app still
    renders the diagram live via mermaid.js, and the PDF falls back to a code block)."""
    # 1) local mermaid-cli (mmdc), if installed
    src = out_path.with_suffix(".mmd")
    try:
        src.write_text(code, encoding="utf-8")
        r = subprocess.run(["mmdc", "-i", str(src), "-o", str(out_path), "-b", "white"],
                           capture_output=True, timeout=60)
        if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return True
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    finally:
        src.unlink(missing_ok=True)
    # 2) mermaid.ink (network, one-time at build; PNG is then committed). A User-Agent
    #    header is required — the service 403s the default urllib agent.
    try:
        b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{b64}?type=png&bgColor=white"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DRA-demo build)"})
        with urllib.request.urlopen(req, timeout=25) as resp:  # noqa: S310 (trusted, build-time)
            data = resp.read()
        if data:
            out_path.write_bytes(data)
            return True
    except Exception:  # noqa: BLE001 — any network/encode failure → graceful fallback
        pass
    return False


# ------------------------------------------------------------------------- assemble
def build_fixture(slug: str) -> dict:
    md = (REPORTS_DIR / f"{slug}.md").read_text(encoding="utf-8")
    disclaimers = _disclaimers(md)
    mermaid = _mermaid(md)
    diagram_png = None
    if mermaid:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        png = ASSETS_DIR / f"{slug}_diagram.png"
        if _render_mermaid_png(mermaid, png):
            diagram_png = f"assets/{png.name}"

    return {
        "slug": slug,
        "type": TYPE_META[slug]["type"],
        "type_label": TYPE_META[slug]["label"],
        "query": _query(md),
        "plan": PLAN_BLOCKS[slug],
        "sources": _sources(md),
        "claims": _claims(md),
        "contradictions": _contradictions(disclaimers),
        "disclaimers": disclaimers,
        "metadata": _metadata(md),
        "narrative": _narrative(md),
        "report_markdown": md,
        "mermaid": mermaid,
        "diagram_png": diagram_png,
    }


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for slug in PLAN_BLOCKS:
        fx = build_fixture(slug)
        (FIXTURES_DIR / f"{slug}.json").write_text(
            json.dumps(fx, indent=2, ensure_ascii=False), encoding="utf-8")
        diag = fx["diagram_png"] or ("code-block fallback" if fx["mermaid"] else "—")
        print(f"  {slug:52s} type {fx['type']} · {len(fx['claims']):2d} claims · "
              f"{len(fx['sources']):2d} sources · diagram: {diag}")
    print(f"\nWrote {len(PLAN_BLOCKS)} fixtures → {FIXTURES_DIR.relative_to(REPO)}/")


if __name__ == "__main__":
    main()
