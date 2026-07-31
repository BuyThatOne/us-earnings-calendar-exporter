from __future__ import annotations

import csv
from datetime import date
from pathlib import Path


CSV_COLUMNS = [
    "earnings_date",
    "ticker",
    "company_name",
    "exchange",
    "market_cap",
    "earnings_time",
    "source_calendar_url",
    "source_market_cap_url",
    "exported_at",
]


def build_export_path(output_dir: Path, start_date: date, end_date: date) -> Path:
    filename = f"us_earnings_next_week_{start_date.isoformat()}_to_{end_date.isoformat()}.csv"
    return output_dir / filename


def write_export_csv(rows, output_dir: Path, start_date: date, end_date: date) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_export_path(output_dir, start_date, end_date)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)
    return output_path
