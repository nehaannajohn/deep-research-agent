"""Command-line entry: `python -m dra.cli "your query"` runs the single-pass agent."""
from __future__ import annotations

import sys


def main(argv=None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    query = argv[0] if argv else "What are the real-world risks and benefits of using synthetic data to train LLMs?"

    from dra.config import load_config
    from dra.loop import build_deps, run_query

    report = run_query(query, build_deps(load_config()))
    print(report.report_markdown)
    print(f"\n[{report.metadata.descriptive_summary}]")


if __name__ == "__main__":
    main()
