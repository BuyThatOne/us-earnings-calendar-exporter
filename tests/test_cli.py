import pytest
from datetime import date

from earnings_export.cli import main
from earnings_export.cli import run_export_next_week


def test_main_returns_zero_for_stubbed_export_command(monkeypatch):
    monkeypatch.setattr(
        "earnings_export.cli.run_export_next_week",
        lambda today=None, output_dir=None, min_market_cap=50_000_000_000: "exports/earnings-calendar/out.csv",
    )
    assert main(["export-next-week"]) == 0


def test_main_reads_process_arguments_when_argv_is_none(monkeypatch):
    monkeypatch.setattr("sys.argv", ["earnings-export", "not-a-command"])

    with pytest.raises(SystemExit, match="Usage: python -m earnings_export export-next-week"):
        main()


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
