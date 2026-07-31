from __future__ import annotations

import sys


def run_export_next_week(today=None, output_dir=None, min_market_cap=50_000_000_000):
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["export-next-week"]:
        raise SystemExit("Usage: python -m earnings_export export-next-week")
    run_export_next_week()
    return 0
