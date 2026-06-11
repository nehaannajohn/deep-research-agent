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
