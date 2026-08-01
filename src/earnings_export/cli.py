from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from earnings_export.date_window import get_next_week_window
from earnings_export.export.csv_writer import write_export_csv
from earnings_export.export.options_report import OptionsArtifactPaths, write_options_artifacts
from earnings_export.options_config import load_analysis_settings
from earnings_export.options_pipeline import analyze_events
from earnings_export.pipeline import (
    build_export_rows,
    collect_events_for_week,
    lookup_market_caps_for_events,
)
from earnings_export.sources.alpha_vantage_options import AlphaVantageOptionsProvider
from earnings_export.sources.optionslam_evr import OptionSlamEvrProvider
from earnings_export.sources.yahoo_options import YahooOptionsProvider


MIN_OPTIONS_MARKET_CAP = 50_000_000_000


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


def run_analyze_next_week_options(
    today: date | None = None,
    cwd: Path | None = None,
) -> OptionsArtifactPaths:
    today = today or date.today()
    cwd = cwd or Path.cwd()
    settings = load_analysis_settings(os.environ, cwd)
    start_date, end_date = get_next_week_window(today)
    session = requests.Session()
    events = collect_events_for_week(start_date, end_date, session)
    market_caps = lookup_market_caps_for_events(events, session)
    filtered_events = [
        event
        for event in events
        if market_caps.get(event.ticker, 0) >= MIN_OPTIONS_MARKET_CAP
    ]
    run_at = datetime.now(timezone.utc).replace(microsecond=0)
    providers = (
        AlphaVantageOptionsProvider(settings, session),
        YahooOptionsProvider(session),
    )
    result = analyze_events(
        filtered_events,
        providers,
        settings,
        run_at,
        OptionSlamEvrProvider(session),
    )
    return write_options_artifacts(result, settings.output_dir)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["export-next-week"]:
        print(run_export_next_week())
        return 0
    if argv == ["analyze-next-week-options"]:
        paths = run_analyze_next_week_options()
        print(paths.markdown_path)
        print(paths.json_path)
        return 0
    raise SystemExit(
        "Usage: python -m earnings_export "
        "{export-next-week|analyze-next-week-options}"
    )
