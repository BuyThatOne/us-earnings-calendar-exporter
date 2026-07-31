from datetime import date
from pathlib import Path

from earnings_export.export.csv_writer import build_export_path, write_export_csv
from earnings_export.models import ExportRow


def test_write_export_csv_creates_directory_and_expected_header(tmp_path: Path):
    rows = [
        ExportRow(
            "2026-08-03",
            "AAPL",
            "Apple",
            "NASDAQ",
            50_000_000_000,
            "BMO",
            "https://calendar/b",
            "https://finviz.com/quote.ashx?t=AAPL",
            "2026-07-31T12:00:00Z",
        )
    ]
    output_dir = tmp_path / "exports" / "earnings-calendar"

    output_path = write_export_csv(rows, output_dir, date(2026, 8, 3), date(2026, 8, 7))

    assert output_path == build_export_path(output_dir, date(2026, 8, 3), date(2026, 8, 7))
    lines = output_path.read_text().splitlines()
    assert lines[0] == "earnings_date,ticker,company_name,exchange,market_cap,earnings_time,source_calendar_url,source_market_cap_url,exported_at"
    assert lines[1].startswith("2026-08-03,AAPL,Apple")
