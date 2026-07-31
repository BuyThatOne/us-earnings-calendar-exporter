from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from earnings_export.date_window import get_next_week_window
from earnings_export.export.csv_writer import write_export_csv
from earnings_export.pipeline import (
    build_export_rows,
    collect_events_for_week,
    lookup_market_caps_for_events,
)


def run_export_next_week(
    today: date | None = None,
    output_dir: Path | None = None,
    min_market_cap: int = 50_000_000_000,
):
    today = today or date.today()
    output_dir = output_dir or Path("exports/earnings-calendar")
    start_date, end_date = get_next_week_window(today)
    session = requests.Session()
    events = collect_events_for_week(start_date, end_date, session)
    market_caps = lookup_market_caps_for_events(events, session)
    exported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = build_export_rows(events, market_caps, exported_at, min_market_cap)
    if not rows:
        raise RuntimeError("No filtered output could be produced.")
    return write_export_csv(rows, output_dir, start_date, end_date)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["export-next-week"]:
        raise SystemExit("Usage: python -m earnings_export export-next-week")
    output_path = run_export_next_week()
    print(output_path)
    return 0
