"""Command-line entry: `python -m dra.cli "your query"`."""
from __future__ import annotations

import sys

from dra.loop import run_query


def main(argv=None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    query = argv[0] if argv else "test query"
    print(run_query(query).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
