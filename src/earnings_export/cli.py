from __future__ import annotations

import errno
import os
import stat
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from earnings_export.date_window import get_next_week_window
from earnings_export.credentials import DEFAULT_CREDENTIALS_PATH
from earnings_export.export.csv_writer import write_export_csv
from earnings_export.export.options_report import OptionsArtifactPaths, write_options_artifacts
from earnings_export.options_config import load_analysis_settings
from earnings_export.options_pipeline import analyze_events, close_options_providers
from earnings_export.pipeline import (
    build_export_rows,
    collect_events_for_week,
    lookup_market_caps_for_events,
)
from earnings_export.sources.alpha_vantage_options import AlphaVantageOptionsProvider
from earnings_export.sources.optionslam_evr import OptionSlamEvrProvider
from earnings_export.sources.yahoo_browser_options import (
    PlaywrightYahooPageReader,
    YahooBrowserOptionsProvider,
)
from earnings_export.sources.yahoo_options import YahooOptionsProvider


MIN_OPTIONS_MARKET_CAP = 50_000_000_000


def _required_posix_no_follow_flag() -> int:
    if os.name != "posix":
        return 0
    try:
        return os.O_NOFOLLOW
    except AttributeError as error:
        raise ValueError(
            "credentials security error: O_NOFOLLOW is unavailable on POSIX"
        ) from error


def _open_existing_credentials_file(path: Path) -> int:
    flags = os.O_WRONLY | _required_posix_no_follow_flag()
    try:
        descriptor = os.open(path, flags)
    except IsADirectoryError as error:
        raise ValueError("credentials path must be a regular file") from error
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError("credentials file must not be a symbolic link") from error
        raise

    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("credentials path must be a regular file")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def initialize_credentials_file(path: Path = DEFAULT_CREDENTIALS_PATH) -> Path:
    no_follow_flag = _required_posix_no_follow_flag()
    directory_mode = 0o700 if os.name == "posix" else 0o777
    path.parent.mkdir(mode=directory_mode, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow_flag
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        if os.name != "posix":
            raise ValueError(
                "credentials security error: cannot initialize an existing credentials "
                "path without atomic no-follow support"
            ) from None
        descriptor = _open_existing_credentials_file(path)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("credentials path must be a regular file")
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)
    return path


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
    browser_reader = PlaywrightYahooPageReader(
        settings.browser_timeout_seconds,
        settings.browser_delay_seconds,
    )
    providers = (
        AlphaVantageOptionsProvider(settings, session),
        YahooOptionsProvider(session),
        YahooBrowserOptionsProvider(
            browser_reader,
            lambda: datetime.now(timezone.utc).replace(microsecond=0),
        ),
    )
    try:
        result = analyze_events(
            filtered_events,
            providers,
            settings,
            run_at,
            OptionSlamEvrProvider(session),
        )
        return write_options_artifacts(result, settings.output_dir)
    finally:
        close_options_providers(providers)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["init-local-credentials"]:
        print(initialize_credentials_file(DEFAULT_CREDENTIALS_PATH))
        return 0
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
        "{init-local-credentials|export-next-week|analyze-next-week-options}"
    )
