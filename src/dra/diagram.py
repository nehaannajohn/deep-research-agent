"""Dedicated diagram generation (Feature 1): a focused, swappable unit that produces
a Mermaid diagram for a report when the query asks for one (plan.constraints.wants_visual).
Isolated from narrative composition so it can be improved/replaced independently.
See docs/superpowers/specs/2026-06-11-report-composition-followups-design.md."""
from __future__ import annotations

import re
from typing import Protocol

_MERMAID_TYPES = ("graph", "flowchart", "sequenceDiagram", "classDiagram",
                  "stateDiagram", "erDiagram", "gantt", "pie", "mindmap", "journey")


class DiagramGenerator(Protocol):
    def generate(self, query: str, claims, narrative: str) -> str:
        """Return a Mermaid code block (```mermaid ... ```), or "" if none/failure."""
        ...


def validate_mermaid(block: str) -> bool:
    """Dependency-free structural check: a fenced ```mermaid block whose body starts
    with a known diagram type and has at least 2 non-empty body lines."""
    if not block:
        return False
    m = re.search(r"```mermaid\s*\n(.*?)```", block, re.DOTALL)
    body = (m.group(1) if m else "").strip()
    if not body:
        return False
    lines = [ln for ln in body.splitlines() if ln.strip()]
    return bool(lines) and any(lines[0].strip().startswith(t) for t in _MERMAID_TYPES) and len(lines) >= 2


def insert_diagram(narrative: str, block: str, heading: str = "Architecture") -> str:
    """Insert a VALID diagram as a new `## {heading}` section immediately after the
    `## Summary` section (before the next `## ` heading), else append at the end.
    An empty/invalid block returns the narrative unchanged."""
    if not validate_mermaid(block):
        return narrative
    section = f"## {heading}\n\n{block.strip()}"
    lines = narrative.splitlines()
    insert_at = len(lines)
    seen_summary = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.lower().startswith("## summary"):
            seen_summary = True
        elif seen_summary and s.startswith("## "):
            insert_at = i
            break
    out = lines[:insert_at] + ["", section, ""] + lines[insert_at:]
    return "\n".join(out).strip() + "\n"


_DIAGRAM_PROMPT = """Produce a detailed, accurate Mermaid diagram of the architecture, pipeline,
or process described in the research report below.
- Use a suitable Mermaid type (flowchart/graph LR or TD, sequenceDiagram, etc.).
- Be detailed: enough nodes/steps to be informative, with LABELED edges and subgraphs where helpful.
- Base it ONLY on the report content; do not invent components the report does not imply.
- Output ONLY a single ```mermaid ... ``` code block — no prose before or after.
- Use VALID Mermaid syntax. Labeled edges are written `A -->|label| B` — a single closing '|', NO trailing '>'.

QUERY: {query}

REPORT:
{narrative}"""


def _extract_mermaid(text: str) -> str:
    m = re.search(r"```mermaid\s*\n.*?```", text or "", re.DOTALL)
    return m.group(0) if m else ""


def _sanitize_mermaid(block: str) -> str:
    """Fix common LLM Mermaid quirks: a labeled edge `-->|label|>` (stray '>') -> `-->|label|`."""
    return block.replace("|>", "|")


class LLMDiagramGenerator:
    """Focused, single-purpose Mermaid generator — a dedicated LLM call (separate from
    narrative composition) so it produces richer diagrams. Returns "" on failure/empty/invalid."""
    def __init__(self, llm):
        self.llm = llm

    def generate(self, query: str, claims, narrative: str) -> str:
        try:
            out = self.llm.complete(_DIAGRAM_PROMPT.format(query=query, narrative=narrative))
        except Exception:
            return ""
        block = _sanitize_mermaid(_extract_mermaid(out or ""))
        return block if validate_mermaid(block) else ""
