"""Render a composed report (markdown) to a downloadable PDF.

``markdown`` → HTML → ``weasyprint``. WeasyPrint gives faithful tables, unicode, and CSS
with very little code — at the cost of one system dependency (``pango``, via
``brew install pango``); the app degrades to a Markdown download if it isn't available. The
one wrinkle is the Mermaid diagram in the type-5 report: PDF engines do not execute
JavaScript, so a pre-rendered PNG (built by ``build_fixtures.py``) is embedded as a base64
data URI when available, falling back to a plain monospace block when it is not.
"""
from __future__ import annotations

import base64
import re
from html import escape
from pathlib import Path

_CSS = """
@page { size: A4; margin: 2cm 1.8cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 18pt; color: #15233b; border-bottom: 2px solid #15233b; padding-bottom: 4px; }
h2 { font-size: 13pt; color: #1f3a5f; margin-top: 16px; }
h3 { font-size: 11pt; color: #1f3a5f; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 8.5pt; }
th { background-color: #15233b; color: #ffffff; text-align: left; padding: 4px 6px; }
td { border-bottom: 1px solid #d8dee9; padding: 4px 6px; vertical-align: top; }
a { color: #2a5db0; text-decoration: none; }
.diagram { text-align: center; margin: 10px 0; }
.diagram img { max-width: 300px; max-height: 420px; }
.mermaid-fallback { background: #f4f6f9; border: 1px solid #d8dee9; padding: 8px; font-family: Courier, monospace; font-size: 8pt; white-space: pre-wrap; }
hr { border: none; border-top: 1px solid #d8dee9; }
"""

_MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)


def _markdown_to_html(text: str) -> str:
    import markdown as md_lib

    return md_lib.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])


def _diagram_html(mermaid_src: str | None, diagram_png_path: str | Path | None) -> str:
    if diagram_png_path and Path(diagram_png_path).exists():
        b64 = base64.b64encode(Path(diagram_png_path).read_bytes()).decode("ascii")
        return f'<div class="diagram"><img src="data:image/png;base64,{b64}" /></div>'
    if mermaid_src:
        return f'<pre class="mermaid-fallback">{escape(mermaid_src)}</pre>'
    return ""


def report_to_pdf(markdown_text: str, diagram_png_path: str | Path | None = None) -> bytes:
    """Return the report as PDF bytes. ``diagram_png_path`` (if given and present) is
    embedded where the Mermaid block sits; otherwise the diagram degrades to a code block."""
    from weasyprint import HTML

    mer = _MERMAID_RE.search(markdown_text)
    mermaid_src = mer.group(1).strip() if mer else None
    text = _MERMAID_RE.sub("\n\n@@DIAGRAM@@\n\n", markdown_text)

    body = _markdown_to_html(text)
    if "@@DIAGRAM@@" in body:
        body = body.replace("@@DIAGRAM@@", _diagram_html(mermaid_src, diagram_png_path))

    html = f"<html><head><meta charset='utf-8'><style>{_CSS}</style></head><body>{body}</body></html>"
    return HTML(string=html).write_pdf()
