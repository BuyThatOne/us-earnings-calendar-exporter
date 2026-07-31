from earnings_export.cli import main


def test_main_returns_zero_for_stubbed_export_command(monkeypatch):
    monkeypatch.setattr(
        "earnings_export.cli.run_export_next_week",
        lambda today=None, output_dir=None, min_market_cap=50_000_000_000: "exports/earnings-calendar/out.csv",
    )
    assert main(["export-next-week"]) == 0
