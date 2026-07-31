# US Earnings Next-Week Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python CLI that exports the next US business week's earnings calendar to CSV, filtered to companies with market capitalization greater than or equal to 50 billion USD, with zero signup and no API keys.

**Architecture:** The CLI will compute the next Monday-through-Friday window, fetch daily earnings rows from NASDAQ public calendar data, normalize those rows into a small internal model, enrich each ticker with current market cap from Finviz, filter by the 50 billion USD threshold, and write one deterministic CSV file into `exports/earnings-calendar/`. Source-specific parsing will stay inside small adapters protected by fixture-based tests so public-source changes fail in isolated places rather than in the CLI flow.

**Tech Stack:** Python 3, `requests`, `pytest`, standard-library `csv`, standard-library `datetime`, optional lightweight Finviz helper only if it materially reduces parsing risk

## Global Constraints

- Export the file in a dedicated folder in the project.
- Export the file in CSV.
- Include only companies that have market capitalization greater than or equal to 50 billion USD.
- Use public data sources with no signup requirement.
- The solution must require zero signup and no API keys.
- It will run manually as a local script, not as a scheduled job.
- No scheduler, cron integration, or hosted automation.
- No database or long-term storage beyond CSV exports.
- No web UI.
- No support for non-US markets in the initial version.
- Keep the implementation small, reviewable, and runnable from the command line.
- `exports/earnings-calendar/` is the dedicated folder for generated CSV files.
- The default "next week" window means the next Monday-through-Friday window after the current local date.
- As of Friday, July 31, 2026, the default "next week" window is Monday, August 3, 2026 through Friday, August 7, 2026.
- Overwrite an existing output file by default for deterministic reruns.
- Tests that hit live public sources are not required for normal local verification; use recorded fixtures for parsing tests.
- Do not add heavy frameworks.
- The current workspace is not a git repository, so `git commit` steps apply only after the user initializes git for this project.

---

## File Structure

- `pyproject.toml`: project metadata, dependency declarations, pytest config, and console-script entrypoint
- `src/earnings_export/__init__.py`: package marker and version placeholder if needed
- `src/earnings_export/__main__.py`: `python -m earnings_export` entrypoint
- `src/earnings_export/cli.py`: CLI command wiring and top-level orchestration
- `src/earnings_export/date_window.py`: next-week window calculation helpers
- `src/earnings_export/models.py`: normalized dataclasses for earnings events and export rows
- `src/earnings_export/pipeline.py`: source orchestration, filtering, sorting, and result assembly
- `src/earnings_export/sources/nasdaq_calendar.py`: NASDAQ calendar fetch and parse adapter
- `src/earnings_export/sources/finviz_market_cap.py`: Finviz market-cap fetch, parse, and symbol normalization
- `src/earnings_export/export/csv_writer.py`: deterministic CSV path generation and writing
- `tests/test_date_window.py`: date-window unit tests
- `tests/test_models_and_pipeline.py`: threshold filtering and sorting tests
- `tests/test_csv_writer.py`: CSV output tests
- `tests/sources/test_nasdaq_calendar.py`: NASDAQ parsing tests from fixtures
- `tests/sources/test_finviz_market_cap.py`: Finviz parsing and market-cap normalization tests
- `tests/fixtures/nasdaq_calendar/*.json`: recorded NASDAQ response fixtures
- `tests/fixtures/finviz_market_cap/*.html`: recorded Finviz HTML fixtures
- `exports/earnings-calendar/.gitkeep`: dedicated output directory marker if git is later initialized

### Task 1: Scaffold the Python package and test harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/earnings_export/__init__.py`
- Create: `src/earnings_export/__main__.py`
- Create: `src/earnings_export/cli.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `src/earnings_export/cli.py::main(argv: list[str] | None = None) -> int`
  - `src/earnings_export/__main__.py` calling `raise SystemExit(main())`

- [ ] **Step 1: Write the failing test**

```python
from earnings_export.cli import main


def test_main_returns_zero_for_stubbed_export_command(monkeypatch):
    monkeypatch.setattr(
        "earnings_export.cli.run_export_next_week",
        lambda today=None, output_dir=None, min_market_cap=50_000_000_000: "exports/earnings-calendar/out.csv",
    )
    assert main(["export-next-week"]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_main_returns_zero_for_stubbed_export_command -v`
Expected: FAIL with `ModuleNotFoundError` or missing `earnings_export.cli`

- [ ] **Step 3: Write minimal implementation**

```python
# src/earnings_export/cli.py
from __future__ import annotations


def run_export_next_week(today=None, output_dir=None, min_market_cap=50_000_000_000):
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    argv = ["export-next-week"] if argv is None else argv
    if argv != ["export-next-week"]:
        raise SystemExit("Usage: python -m earnings_export export-next-week")
    run_export_next_week()
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_main_returns_zero_for_stubbed_export_command -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/earnings_export/__init__.py src/earnings_export/__main__.py src/earnings_export/cli.py tests/conftest.py tests/test_cli.py
git commit -m "chore: scaffold earnings export package"
```

### Task 2: Implement and test next-week window calculation

**Files:**
- Create: `src/earnings_export/date_window.py`
- Create: `tests/test_date_window.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `get_next_week_window(today: date) -> tuple[date, date]`
  - `iter_weekdays(start_date: date, end_date: date) -> list[date]`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from earnings_export.date_window import get_next_week_window, iter_weekdays


def test_get_next_week_window_from_2026_07_31():
    start_date, end_date = get_next_week_window(date(2026, 7, 31))
    assert start_date == date(2026, 8, 3)
    assert end_date == date(2026, 8, 7)


def test_iter_weekdays_returns_monday_through_friday():
    days = iter_weekdays(date(2026, 8, 3), date(2026, 8, 7))
    assert days == [
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
        date(2026, 8, 6),
        date(2026, 8, 7),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_date_window.py -v`
Expected: FAIL with missing `earnings_export.date_window`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from datetime import date, timedelta


def get_next_week_window(today: date) -> tuple[date, date]:
    days_until_next_monday = 7 - today.weekday()
    start_date = today + timedelta(days=days_until_next_monday)
    end_date = start_date + timedelta(days=4)
    return start_date, end_date


def iter_weekdays(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_date_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/earnings_export/date_window.py tests/test_date_window.py
git commit -m "feat: add next-week window calculation"
```

### Task 3: Define normalized models and threshold filtering

**Files:**
- Create: `src/earnings_export/models.py`
- Create: `src/earnings_export/pipeline.py`
- Create: `tests/test_models_and_pipeline.py`

**Interfaces:**
- Consumes:
  - `get_next_week_window(today: date) -> tuple[date, date]`
  - `iter_weekdays(start_date: date, end_date: date) -> list[date]`
- Produces:
  - `EarningsEvent`
  - `ExportRow`
  - `filter_and_sort_events(events: list[EarningsEvent], market_caps: dict[str, int], exported_at: str, min_market_cap: int) -> list[ExportRow]`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from earnings_export.models import EarningsEvent
from earnings_export.pipeline import filter_and_sort_events


def test_filter_and_sort_events_keeps_threshold_and_sorts():
    events = [
        EarningsEvent(date(2026, 8, 4), "MSFT", "Microsoft", "AMC", "NASDAQ", "https://calendar/a"),
        EarningsEvent(date(2026, 8, 3), "AAPL", "Apple", "BMO", "NASDAQ", "https://calendar/b"),
        EarningsEvent(date(2026, 8, 3), "XYZ", "Small Cap", "AMC", "NYSE", "https://calendar/c"),
    ]
    market_caps = {
        "AAPL": 50_000_000_000,
        "MSFT": 3_000_000_000_000,
        "XYZ": 49_999_999_999,
    }

    rows = filter_and_sort_events(
        events,
        market_caps=market_caps,
        exported_at="2026-07-31T12:00:00Z",
        min_market_cap=50_000_000_000,
    )

    assert [row.ticker for row in rows] == ["AAPL", "MSFT"]
    assert rows[0].market_cap == 50_000_000_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_and_pipeline.py::test_filter_and_sort_events_keeps_threshold_and_sorts -v`
Expected: FAIL with missing model or function definitions

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EarningsEvent:
    earnings_date: date
    ticker: str
    company_name: str
    earnings_time: str | None
    exchange: str | None
    source_calendar_url: str


@dataclass(frozen=True)
class ExportRow:
    earnings_date: str
    ticker: str
    company_name: str
    exchange: str | None
    market_cap: int
    earnings_time: str | None
    source_calendar_url: str
    source_market_cap_url: str
    exported_at: str
```

```python
from __future__ import annotations

from earnings_export.models import EarningsEvent, ExportRow


def filter_and_sort_events(events, market_caps, exported_at, min_market_cap):
    rows = []
    for event in events:
        market_cap = market_caps.get(event.ticker)
        if market_cap is None or market_cap < min_market_cap:
            continue
        rows.append(
            ExportRow(
                earnings_date=event.earnings_date.isoformat(),
                ticker=event.ticker,
                company_name=event.company_name,
                exchange=event.exchange,
                market_cap=market_cap,
                earnings_time=event.earnings_time,
                source_calendar_url=event.source_calendar_url,
                source_market_cap_url=f"https://finviz.com/quote.ashx?t={event.ticker}",
                exported_at=exported_at,
            )
        )
    return sorted(rows, key=lambda row: (row.earnings_date, row.ticker))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models_and_pipeline.py::test_filter_and_sort_events_keeps_threshold_and_sorts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/earnings_export/models.py src/earnings_export/pipeline.py tests/test_models_and_pipeline.py
git commit -m "feat: add normalized models and filtering"
```

### Task 4: Build the CSV writer and deterministic export path

**Files:**
- Create: `src/earnings_export/export/__init__.py`
- Create: `src/earnings_export/export/csv_writer.py`
- Create: `tests/test_csv_writer.py`
- Create: `exports/earnings-calendar/.gitkeep`

**Interfaces:**
- Consumes:
  - `ExportRow`
- Produces:
  - `build_export_path(output_dir: Path, start_date: date, end_date: date) -> Path`
  - `write_export_csv(rows: list[ExportRow], output_dir: Path, start_date: date, end_date: date) -> Path`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_csv_writer.py::test_write_export_csv_creates_directory_and_expected_header -v`
Expected: FAIL with missing csv writer module

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_csv_writer.py::test_write_export_csv_creates_directory_and_expected_header -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/earnings_export/export/__init__.py src/earnings_export/export/csv_writer.py tests/test_csv_writer.py exports/earnings-calendar/.gitkeep
git commit -m "feat: add deterministic csv export writer"
```

### Task 5: Implement the NASDAQ earnings calendar adapter from fixtures

**Files:**
- Create: `src/earnings_export/sources/__init__.py`
- Create: `src/earnings_export/sources/nasdaq_calendar.py`
- Create: `tests/sources/test_nasdaq_calendar.py`
- Create: `tests/fixtures/nasdaq_calendar/sample_day.json`

**Interfaces:**
- Consumes:
  - `EarningsEvent`
- Produces:
  - `build_nasdaq_calendar_url(day: date) -> str`
  - `parse_nasdaq_calendar_payload(payload: dict, source_url: str) -> list[EarningsEvent]`
  - `fetch_nasdaq_earnings_for_day(day: date, session: requests.Session) -> list[EarningsEvent]`

- [ ] **Step 1: Write the failing test**

```python
import json
from datetime import date
from pathlib import Path

from earnings_export.sources.nasdaq_calendar import build_nasdaq_calendar_url, parse_nasdaq_calendar_payload


def test_parse_nasdaq_calendar_payload_returns_normalized_events():
    fixture_path = Path("tests/fixtures/nasdaq_calendar/sample_day.json")
    payload = json.loads(fixture_path.read_text())
    source_url = build_nasdaq_calendar_url(date(2026, 8, 3))

    events = parse_nasdaq_calendar_payload(payload, source_url)

    assert events[0].ticker == "AAPL"
    assert events[0].earnings_date == date(2026, 8, 3)
    assert events[0].source_calendar_url == source_url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sources/test_nasdaq_calendar.py::test_parse_nasdaq_calendar_payload_returns_normalized_events -v`
Expected: FAIL with missing NASDAQ adapter

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from datetime import date

import requests

from earnings_export.models import EarningsEvent


def build_nasdaq_calendar_url(day: date) -> str:
    return f"https://api.nasdaq.com/api/calendar/earnings?date={day.isoformat()}"


def parse_nasdaq_calendar_payload(payload: dict, source_url: str) -> list[EarningsEvent]:
    rows = payload["data"]["rows"]
    events = []
    for row in rows:
        ticker = row["symbol"].strip().upper()
        events.append(
            EarningsEvent(
                earnings_date=date.fromisoformat(row["date"]),
                ticker=ticker,
                company_name=row["name"].strip(),
                earnings_time=row.get("time") or None,
                exchange=row.get("exchange") or None,
                source_calendar_url=source_url,
            )
        )
    return events


def fetch_nasdaq_earnings_for_day(day: date, session: requests.Session) -> list[EarningsEvent]:
    url = build_nasdaq_calendar_url(day)
    response = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    return parse_nasdaq_calendar_payload(response.json(), url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/sources/test_nasdaq_calendar.py::test_parse_nasdaq_calendar_payload_returns_normalized_events -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/earnings_export/sources/__init__.py src/earnings_export/sources/nasdaq_calendar.py tests/sources/test_nasdaq_calendar.py tests/fixtures/nasdaq_calendar/sample_day.json
git commit -m "feat: add nasdaq earnings calendar adapter"
```

### Task 6: Implement the Finviz market-cap adapter and parsing

**Files:**
- Create: `src/earnings_export/sources/finviz_market_cap.py`
- Create: `tests/sources/test_finviz_market_cap.py`
- Create: `tests/fixtures/finviz_market_cap/aapl.html`

**Interfaces:**
- Consumes:
  - `requests.Session`
- Produces:
  - `normalize_symbol_for_finviz(symbol: str) -> str`
  - `parse_market_cap_text(raw_value: str) -> int | None`
  - `extract_market_cap_from_html(html: str) -> int | None`
  - `fetch_market_caps(symbols: list[str], session: requests.Session) -> dict[str, int]`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from earnings_export.sources.finviz_market_cap import extract_market_cap_from_html, parse_market_cap_text


def test_parse_market_cap_text_handles_b_t_and_m():
    assert parse_market_cap_text("50B") == 50_000_000_000
    assert parse_market_cap_text("1.25T") == 1_250_000_000_000
    assert parse_market_cap_text("950M") == 950_000_000


def test_extract_market_cap_from_html_reads_market_cap_field():
    html = Path("tests/fixtures/finviz_market_cap/aapl.html").read_text()
    assert extract_market_cap_from_html(html) == 3_200_000_000_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sources/test_finviz_market_cap.py -v`
Expected: FAIL with missing Finviz adapter

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import re

import requests


def normalize_symbol_for_finviz(symbol: str) -> str:
    return symbol.replace(".", "-").upper()


def parse_market_cap_text(raw_value: str) -> int | None:
    match = re.fullmatch(r"([0-9]+(?:\\.[0-9]+)?)([TMB])", raw_value.strip())
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"T": 1_000_000_000_000, "B": 1_000_000_000, "M": 1_000_000}[match.group(2)]
    return int(number * multiplier)


def extract_market_cap_from_html(html: str) -> int | None:
    match = re.search(r">Market Cap</td><td[^>]*>([^<]+)<", html)
    if not match:
        return None
    return parse_market_cap_text(match.group(1))


def fetch_market_caps(symbols: list[str], session: requests.Session) -> dict[str, int]:
    market_caps: dict[str, int] = {}
    for symbol in symbols:
        normalized = normalize_symbol_for_finviz(symbol)
        url = f"https://finviz.com/quote.ashx?t={normalized}"
        response = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        market_cap = extract_market_cap_from_html(response.text)
        if market_cap is not None:
            market_caps[symbol] = market_cap
    return market_caps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/sources/test_finviz_market_cap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/earnings_export/sources/finviz_market_cap.py tests/sources/test_finviz_market_cap.py tests/fixtures/finviz_market_cap/aapl.html
git commit -m "feat: add finviz market cap adapter"
```

### Task 7: Wire the end-to-end pipeline into the CLI

**Files:**
- Modify: `src/earnings_export/cli.py`
- Modify: `src/earnings_export/pipeline.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes:
  - `get_next_week_window(today: date) -> tuple[date, date]`
  - `iter_weekdays(start_date: date, end_date: date) -> list[date]`
  - `fetch_nasdaq_earnings_for_day(day: date, session: requests.Session) -> list[EarningsEvent]`
  - `fetch_market_caps(symbols: list[str], session: requests.Session) -> dict[str, int]`
  - `filter_and_sort_events(events: list[EarningsEvent], market_caps: dict[str, int], exported_at: str, min_market_cap: int) -> list[ExportRow]`
  - `write_export_csv(rows: list[ExportRow], output_dir: Path, start_date: date, end_date: date) -> Path`
- Produces:
  - `run_export_next_week(today: date | None = None, output_dir: Path | None = None, min_market_cap: int = 50_000_000_000) -> Path`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date
from pathlib import Path

from earnings_export.cli import run_export_next_week


def test_run_export_next_week_orchestrates_pipeline(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("earnings_export.cli.get_next_week_window", lambda today: (date(2026, 8, 3), date(2026, 8, 7)))
    monkeypatch.setattr("earnings_export.cli.collect_events_for_week", lambda start_date, end_date, session: ["event"])
    monkeypatch.setattr("earnings_export.cli.lookup_market_caps_for_events", lambda events, session: {"AAPL": 50_000_000_000})
    monkeypatch.setattr("earnings_export.cli.build_export_rows", lambda events, market_caps, exported_at, min_market_cap: ["row"])
    monkeypatch.setattr("earnings_export.cli.write_export_csv", lambda rows, output_dir, start_date, end_date: tmp_path / "out.csv")

    output_path = run_export_next_week(today=date(2026, 7, 31), output_dir=tmp_path)

    assert output_path == tmp_path / "out.csv"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_run_export_next_week_orchestrates_pipeline -v`
Expected: FAIL with missing orchestration helpers

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import requests

from earnings_export.date_window import get_next_week_window
from earnings_export.export.csv_writer import write_export_csv
from earnings_export.pipeline import build_export_rows, collect_events_for_week, lookup_market_caps_for_events


def run_export_next_week(today: date | None = None, output_dir: Path | None = None, min_market_cap: int = 50_000_000_000):
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
```

```python
from __future__ import annotations

from earnings_export.date_window import iter_weekdays
from earnings_export.sources.finviz_market_cap import fetch_market_caps
from earnings_export.sources.nasdaq_calendar import fetch_nasdaq_earnings_for_day


def collect_events_for_week(start_date, end_date, session):
    events = []
    seen = set()
    for day in iter_weekdays(start_date, end_date):
        for event in fetch_nasdaq_earnings_for_day(day, session):
            key = (event.earnings_date, event.ticker)
            if key not in seen:
                seen.add(key)
                events.append(event)
    return events


def lookup_market_caps_for_events(events, session):
    symbols = sorted({event.ticker for event in events})
    return fetch_market_caps(symbols, session)


def build_export_rows(events, market_caps, exported_at, min_market_cap):
    return filter_and_sort_events(events, market_caps, exported_at, min_market_cap)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_run_export_next_week_orchestrates_pipeline -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/earnings_export/cli.py src/earnings_export/pipeline.py tests/test_cli.py
git commit -m "feat: wire weekly earnings export pipeline"
```

### Task 8: Add failure-path tests and final verification command set

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `tests/test_models_and_pipeline.py`
- Modify: `tests/sources/test_nasdaq_calendar.py`
- Modify: `tests/sources/test_finviz_market_cap.py`

**Interfaces:**
- Consumes:
  - all prior task interfaces
- Produces:
  - regression coverage for empty results, partial market-cap failures, and malformed source payloads

- [ ] **Step 1: Write the failing test**

```python
from datetime import date
from pathlib import Path

import pytest

from earnings_export.cli import run_export_next_week


def test_run_export_next_week_raises_when_no_rows_survive_filter(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("earnings_export.cli.get_next_week_window", lambda today: (date(2026, 8, 3), date(2026, 8, 7)))
    monkeypatch.setattr("earnings_export.cli.collect_events_for_week", lambda start_date, end_date, session: ["event"])
    monkeypatch.setattr("earnings_export.cli.lookup_market_caps_for_events", lambda events, session: {})
    monkeypatch.setattr("earnings_export.cli.build_export_rows", lambda events, market_caps, exported_at, min_market_cap: [])

    with pytest.raises(RuntimeError, match="No filtered output could be produced."):
        run_export_next_week(today=date(2026, 7, 31), output_dir=tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_run_export_next_week_raises_when_no_rows_survive_filter -v`
Expected: FAIL because the current orchestration does not yet raise that exact error or missing path coverage

- [ ] **Step 3: Write minimal implementation**

```python
def parse_nasdaq_calendar_payload(payload: dict, source_url: str) -> list[EarningsEvent]:
    rows = payload.get("data", {}).get("rows")
    if not isinstance(rows, list):
        raise ValueError("NASDAQ payload missing data.rows")
    ...
```

```python
def extract_market_cap_from_html(html: str) -> int | None:
    match = re.search(r">Market Cap</td><td[^>]*>([^<]+)<", html)
    if not match:
        return None
    return parse_market_cap_text(match.group(1).strip())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py tests/test_models_and_pipeline.py tests/sources/test_nasdaq_calendar.py tests/sources/test_finviz_market_cap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py tests/test_models_and_pipeline.py tests/sources/test_nasdaq_calendar.py tests/sources/test_finviz_market_cap.py src/earnings_export/sources/nasdaq_calendar.py src/earnings_export/sources/finviz_market_cap.py
git commit -m "test: cover failure paths for public source adapters"
```

## Self-Review

### Spec coverage

- CLI entrypoint: covered by Tasks 1 and 7
- Next-week Monday-through-Friday logic: covered by Task 2
- Dedicated export folder and deterministic CSV output: covered by Task 4
- NASDAQ public earnings source: covered by Task 5
- Finviz market-cap enrichment and `>= 50B` threshold: covered by Tasks 3 and 6
- Public-source failure handling and zero-signup behavior: covered by Task 8

No spec gaps remain.

### Placeholder scan

- Removed generic placeholders like "add tests later" and "handle edge cases".
- Each task includes concrete files, interfaces, commands, and code targets.

### Type consistency

- `EarningsEvent` and `ExportRow` are introduced in Task 3 and reused consistently later.
- `run_export_next_week`, `collect_events_for_week`, `lookup_market_caps_for_events`, and `build_export_rows` are named consistently across Tasks 1, 7, and 8.
- Source adapter names match between their producing and consuming tasks.
