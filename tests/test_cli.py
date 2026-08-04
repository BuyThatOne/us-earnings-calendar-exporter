import json
import os
from datetime import date, datetime, timezone

import pytest

from earnings_export.cli import (
    initialize_credentials_file,
    main,
    run_analyze_next_week_options,
    run_export_next_week,
)
from earnings_export.export.options_report import AnalysisRunResult, OptionsArtifactPaths
from earnings_export.models import EarningsEvent


FIXED_TIME = datetime(2026, 7, 31, 14, 30, tzinfo=timezone.utc)


def _event(ticker: str) -> EarningsEvent:
    return EarningsEvent(
        earnings_date=date(2026, 8, 6),
        ticker=ticker,
        company_name=ticker,
        earnings_time="AMC",
        exchange="NASDAQ",
        source_calendar_url=f"https://calendar.test/{ticker.lower()}",
    )


def _empty_run() -> AnalysisRunResult:
    return AnalysisRunResult(FIXED_TIME, (), {}, (), ())


def test_main_returns_zero_for_stubbed_export_command(monkeypatch):
    monkeypatch.setattr(
        "earnings_export.cli.run_export_next_week",
        lambda today=None, output_dir=None, min_market_cap=50_000_000_000: "exports/earnings-calendar/out.csv",
    )
    assert main(["export-next-week"]) == 0


@pytest.mark.skipif(os.name != "posix", reason="Unix permission bits are POSIX-only")
def test_init_local_credentials_creates_owner_only_file(monkeypatch, tmp_path, capsys):
    credentials = tmp_path / "config" / "credentials.env"
    monkeypatch.setattr("earnings_export.cli.DEFAULT_CREDENTIALS_PATH", credentials)
    assert main(["init-local-credentials"]) == 0
    assert credentials.exists()
    assert credentials.parent.stat().st_mode & 0o777 == 0o700
    assert credentials.stat().st_mode & 0o777 == 0o600
    captured = capsys.readouterr()
    assert captured.out == f"{credentials}\n"
    assert captured.err == ""
    assert credentials.read_text() == ""


def test_initialize_credentials_creates_empty_file_without_chmod_on_non_posix(
    monkeypatch, tmp_path,
):
    credentials = tmp_path / "config" / "credentials.env"
    monkeypatch.setattr("earnings_export.cli.os.name", "nt")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("chmod is unsupported for non-POSIX credentials initialization")

    monkeypatch.setattr("pathlib.Path.chmod", fail_if_called)

    assert initialize_credentials_file(credentials) == credentials
    assert credentials.read_text() == ""


def test_initialize_credentials_fails_closed_for_existing_path_on_non_posix(
    monkeypatch, tmp_path,
):
    credentials = tmp_path / "config" / "credentials.env"
    credentials.parent.mkdir()
    credentials.write_text("unchanged\n")
    monkeypatch.setattr("earnings_export.cli.os.name", "nt")

    with pytest.raises(ValueError, match="atomic no-follow support"):
        initialize_credentials_file(credentials)

    assert credentials.read_text() == "unchanged\n"


@pytest.mark.skipif(os.name != "posix", reason="O_NOFOLLOW is a POSIX-only requirement")
def test_initialize_credentials_fails_closed_when_posix_lacks_o_nofollow(
    monkeypatch, tmp_path,
):
    credentials = tmp_path / "config" / "credentials.env"
    monkeypatch.delattr("earnings_export.cli.os.O_NOFOLLOW")

    with pytest.raises(ValueError, match="O_NOFOLLOW is unavailable on POSIX"):
        initialize_credentials_file(credentials)

    assert not credentials.parent.exists()


def test_initialize_credentials_rejects_symbolic_link_without_modifying_target(tmp_path):
    target = tmp_path / "target.env"
    target.write_text("unchanged\n")
    credentials = tmp_path / "config" / "credentials.env"
    credentials.parent.mkdir()
    try:
        credentials.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symbolic links are unavailable: {error}")

    with pytest.raises(ValueError, match="symbolic link"):
        initialize_credentials_file(credentials)

    assert target.read_text() == "unchanged\n"


def test_initialize_credentials_rejects_non_regular_path(tmp_path):
    credentials = tmp_path / "config" / "credentials.env"
    credentials.mkdir(parents=True)

    with pytest.raises(ValueError, match="regular file"):
        initialize_credentials_file(credentials)


@pytest.mark.parametrize("argument", ["unexpected", "ALPHAVANTAGE_API_KEY=secret"])
def test_init_local_credentials_rejects_arguments_without_creating_credentials(
    argument, monkeypatch, tmp_path, capsys,
):
    credentials = tmp_path / "config" / "credentials.env"
    monkeypatch.setattr("earnings_export.cli.DEFAULT_CREDENTIALS_PATH", credentials)

    with pytest.raises(SystemExit) as error:
        main(["init-local-credentials", argument])

    assert str(error.value) == (
        "Usage: python -m earnings_export "
        "{init-local-credentials|export-next-week|analyze-next-week-options}"
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert not credentials.parent.exists()
    assert not credentials.exists()


def test_main_reads_process_arguments_when_argv_is_none(monkeypatch):
    monkeypatch.setattr("sys.argv", ["earnings-export", "not-a-command"])

    with pytest.raises(
        SystemExit,
        match=r"Usage: python -m earnings_export \{init-local-credentials\|export-next-week\|analyze-next-week-options\}",
    ):
        main()


def test_main_dispatches_options_command(monkeypatch, tmp_path, capsys):
    paths = OptionsArtifactPaths(
        tmp_path / "report.md",
        tmp_path / "order-intents.json",
        tmp_path / "snapshots.json",
    )
    monkeypatch.setattr("earnings_export.cli.run_analyze_next_week_options", lambda: paths)

    assert main(["analyze-next-week-options"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        str(paths.markdown_path),
        str(paths.json_path),
    ]


def test_run_export_next_week_orchestrates_pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr("earnings_export.cli.get_next_week_window", lambda today: (date(2026, 8, 3), date(2026, 8, 7)))
    monkeypatch.setattr("earnings_export.cli.collect_events_for_week", lambda start_date, end_date, session: ["event"])
    monkeypatch.setattr("earnings_export.cli.lookup_market_caps_for_events", lambda events, session: {"AAPL": 50_000_000_000})
    monkeypatch.setattr("earnings_export.cli.build_export_rows", lambda events, market_caps, exported_at, min_market_cap: ["row"])
    monkeypatch.setattr("earnings_export.cli.write_export_csv", lambda rows, output_dir, start_date, end_date: tmp_path / "out.csv")

    output_path = run_export_next_week(today=date(2026, 7, 31), output_dir=tmp_path)

    assert output_path == tmp_path / "out.csv"


def test_main_prints_export_path(monkeypatch, capsys):
    monkeypatch.setattr(
        "earnings_export.cli.run_export_next_week",
        lambda today=None, output_dir=None, min_market_cap=50_000_000_000: "exports/earnings-calendar/out.csv",
    )

    assert main(["export-next-week"]) == 0

    assert "exports/earnings-calendar/out.csv" in capsys.readouterr().out


def test_run_export_next_week_raises_when_no_rows_survive_filter(monkeypatch, tmp_path):
    monkeypatch.setattr("earnings_export.cli.get_next_week_window", lambda today: (date(2026, 8, 3), date(2026, 8, 7)))
    monkeypatch.setattr("earnings_export.cli.collect_events_for_week", lambda start_date, end_date, session: ["event"])
    monkeypatch.setattr("earnings_export.cli.lookup_market_caps_for_events", lambda events, session: {})
    monkeypatch.setattr("earnings_export.cli.build_export_rows", lambda events, market_caps, exported_at, min_market_cap: [])

    with pytest.raises(RuntimeError, match="No filtered output could be produced."):
        run_export_next_week(today=date(2026, 7, 31), output_dir=tmp_path)


def test_options_run_filters_market_cap_before_analysis_and_writes_empty_result(
    monkeypatch, tmp_path,
):
    events = [_event("AAPL"), _event("SMALL")]
    analyzed_events = []
    evr_provider_names = []
    monkeypatch.setattr(
        "earnings_export.cli.get_next_week_window",
        lambda today: (date(2026, 8, 3), date(2026, 8, 7)),
    )
    monkeypatch.setattr("earnings_export.cli.collect_events_for_week", lambda *args: events)
    monkeypatch.setattr(
        "earnings_export.cli.lookup_market_caps_for_events",
        lambda *args: {"AAPL": 1_000_000_000_000, "SMALL": 49_999_999_999},
    )

    def fake_analyze(filtered_events, providers, settings, run_at, evr_provider):
        analyzed_events.extend(filtered_events)
        evr_provider_names.append(evr_provider.name)
        return _empty_run()

    monkeypatch.setattr("earnings_export.cli.analyze_events", fake_analyze)

    paths = run_analyze_next_week_options(today=date(2026, 7, 31), cwd=tmp_path)

    assert [event.ticker for event in analyzed_events] == ["AAPL"]
    assert evr_provider_names == ["optionslam"]
    assert paths.json_path.exists()
    assert paths.markdown_path.exists()


def test_options_run_writes_empty_artifacts_for_malformed_alpha_history(
    monkeypatch, tmp_path,
):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class Session:
        def get(self, url, params, timeout):
            if params.get("function") == "REALTIME_OPTIONS":
                return Response({"data": []})
            if params.get("function") == "HISTORICAL_OPTIONS":
                return Response([])
            return Response({"optionChain": {"result": []}})

    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "fixture-key")
    monkeypatch.setattr("earnings_export.cli.requests.Session", Session)
    monkeypatch.setattr("earnings_export.cli.collect_events_for_week", lambda *args: [_event("AAPL")])
    monkeypatch.setattr(
        "earnings_export.cli.lookup_market_caps_for_events",
        lambda *args: {"AAPL": 1_000_000_000_000},
    )

    paths = run_analyze_next_week_options(today=date(2026, 7, 31), cwd=tmp_path)

    assert "No eligible candidate was found" in paths.markdown_path.read_text()
    assert json.loads(paths.json_path.read_text())["candidates"] == []
    assert json.loads(paths.snapshots_path.read_text())["snapshots"] == []


def test_existing_export_command_remains_supported(monkeypatch):
    monkeypatch.setattr("earnings_export.cli.run_export_next_week", lambda: "out.csv")

    assert main(["export-next-week"]) == 0
