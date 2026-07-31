# US Earnings Next-Week Export CLI Design

## Summary

Build a local Python CLI that exports the next US business week's earnings calendar to CSV, filtered to companies with market capitalization greater than or equal to 50 billion USD.

The solution must require zero signup and no API keys. It will run manually as a local script, not as a scheduled job.

As of Friday, July 31, 2026, the default "next week" window is Monday, August 3, 2026 through Friday, August 7, 2026. In general, "next week" means the next Monday-through-Friday window after the current local date.

## Goals

- Export next week's US earnings calendar into a dedicated folder inside the project.
- Output CSV only.
- Include only companies with market cap greater than or equal to 50 billion USD.
- Use public data sources with no signup requirement.
- Keep the implementation small, reviewable, and runnable from the command line.

## Non-Goals

- No scheduler, cron integration, or hosted automation.
- No database or long-term storage beyond CSV exports.
- No web UI.
- No support for non-US markets in the initial version.
- No historical backfill workflow beyond manually specifying a date range if we choose to expose that later.

## Recommended Approach

Use two public data sources:

1. NASDAQ public earnings calendar data for the list of US earnings events by date.
2. Finviz-based scraping or library access for current market capitalization by ticker.

This is preferred over a single-source scrape because:

- NASDAQ calendar data is directly aligned with US earnings events.
- Finviz is well known for public equity screening and exposes market-cap-related data without signup.
- The failure modes are isolated. If one source changes, the other source remains unaffected.
- Existing open-source projects suggest both sources are viable in Python.

## User Experience

The project exposes a single CLI entrypoint for the main workflow:

```bash
python -m earnings_export export-next-week
```

Expected behavior:

- Compute the next Monday-through-Friday window from the current local date.
- Fetch all US earnings events in that window.
- Normalize the event rows into a consistent internal format.
- Enrich rows with market cap data by ticker.
- Filter out rows with market cap below 50 billion USD.
- Write a CSV file into a dedicated export directory.
- Print the output path and a short summary to stdout.

Optional future flags may include:

- `--week-of YYYY-MM-DD`
- `--output PATH`
- `--min-market-cap 50000000000`

These flags are not required for v1, but the design should not block them.

## Project Layout

The initial project layout should be:

```text
docs/
  superpowers/
    specs/
src/
  earnings_export/
    __init__.py
    __main__.py
    cli.py
    date_window.py
    models.py
    sources/
      __init__.py
      nasdaq_calendar.py
      finviz_market_cap.py
    export/
      __init__.py
      csv_writer.py
tests/
exports/
  earnings-calendar/
```

`exports/earnings-calendar/` is the dedicated folder for generated CSV files.

## Data Sources

### Earnings Calendar Source

Primary source: NASDAQ public earnings calendar data.

Responsibilities:

- Fetch earnings events for a given trading date.
- Return only rows representing listed companies with earnings announcements on that date.
- Expose enough fields to preserve ticker, company name, event date, and timing if available.

Why this source:

- It is already used by open-source Python wrappers.
- It is focused on US-listed equities, which matches the requested scope.
- It avoids scraping arbitrary HTML calendar pages when structured responses are available.

### Market Cap Source

Primary source: Finviz company data for each ticker, accessed through a lightweight Python library if stable, otherwise through a direct scraper we own.

Responsibilities:

- Resolve current market capitalization for a ticker.
- Normalize textual market cap values such as `2.31T`, `78.4B`, or `950M` into integer USD values.
- Return `None` for unavailable or ambiguous values.

Why this source:

- No signup.
- Widely used for public screening data.
- Existing open-source packages reduce custom parsing risk.

## Data Model

Internal normalized earnings row:

```text
EarningsEvent
- earnings_date: date
- ticker: str
- company_name: str
- earnings_time: str | None
- exchange: str | None
- source_calendar_url: str
```

Enriched export row:

```text
ExportRow
- earnings_date: YYYY-MM-DD
- ticker: str
- company_name: str
- exchange: str | None
- market_cap: int
- earnings_time: str | None
- source_calendar_url: str
- source_market_cap_url: str
- exported_at: ISO-8601 timestamp
```

CSV columns will appear in this order:

1. `earnings_date`
2. `ticker`
3. `company_name`
4. `exchange`
5. `market_cap`
6. `earnings_time`
7. `source_calendar_url`
8. `source_market_cap_url`
9. `exported_at`

## Data Flow

1. Determine the next business-week window.
2. For each weekday in the window, fetch NASDAQ earnings events.
3. Merge daily results into a single list.
4. Remove duplicate tickers for the same earnings date if the source repeats rows.
5. Normalize ticker symbols to the representation needed by the market-cap source.
6. Fetch market cap per ticker.
7. Drop rows where market cap is missing, unparsable, or below the threshold.
8. Sort rows by `earnings_date`, then `ticker`.
9. Write the CSV to `exports/earnings-calendar/`.

## Output Naming

CSV filename format:

```text
us_earnings_next_week_YYYY-MM-DD_to_YYYY-MM-DD.csv
```

Example for the current default window:

```text
us_earnings_next_week_2026-08-03_to_2026-08-07.csv
```

## Error Handling

The CLI should fail clearly and early when a source cannot be used.

Cases:

- NASDAQ fetch fails:
  - Exit non-zero.
  - Print which date failed and the upstream error.
- Finviz fetch fails for some tickers:
  - Continue if failures are partial.
  - Exclude unresolved tickers from the final CSV.
  - Print a warning with the count of dropped tickers.
- All market-cap lookups fail:
  - Exit non-zero.
  - Print that no filtered output could be produced.
- Output directory missing:
  - Create it automatically.
- Existing output file already exists:
  - Overwrite by default for deterministic reruns.

## Rate Limiting and Politeness

Because the solution depends on public endpoints, it should be conservative:

- Reuse a single HTTP session.
- Set an explicit user agent.
- Add small delays between market-cap lookups if requests are per ticker.
- Prefer batched retrieval if the selected Finviz library supports it.
- Keep request logic isolated so throttling can be tuned without touching CLI code.

## Testing Strategy

The implementation should follow test-first development.

Minimum test coverage for v1:

- Date-window calculation for "next week".
- Market-cap string parsing:
  - `50B` -> `50000000000`
  - `1.25T` -> `1250000000000`
  - `950M` -> `950000000`
- Filtering logic at the exact threshold:
  - `50000000000` is included.
  - `49999999999` is excluded.
- CSV writer:
  - creates the expected directory
  - writes the expected header order
  - writes deterministic filenames
- Source adapters:
  - parse fixture responses into normalized rows
  - handle malformed or empty responses cleanly

Tests that hit live public sources should not be required for normal local verification. Source parsing should be protected with recorded fixtures so markup or payload changes are visible as explicit failures.

## Dependencies

Expected minimal dependencies:

- `requests`
- `pytest`
- `python-dateutil` only if needed
- one Finviz helper library only if it materially reduces parsing risk

Do not add heavy frameworks.

## Open Source Reuse Policy

We may borrow implementation ideas from existing open-source projects, but the CLI should remain our own small wrapper with explicit source boundaries. Avoid deep dependency on abandoned projects when a small owned adapter is straightforward.

## Risks

### Source Stability

Public finance pages and unofficial endpoints change. This is the main risk in a zero-signup design.

Mitigation:

- Keep each source adapter small and separately testable.
- Use fixtures for parsing tests.
- Fail with precise diagnostics.

### Symbol Mismatches

Tickers may differ between NASDAQ and Finviz formatting.

Mitigation:

- Centralize symbol normalization rules.
- Add tests for dotted and dashed tickers if encountered.

### Market Cap Freshness

Market cap is current at lookup time, not historical for the earnings date.

Mitigation:

- Treat the filter as "current market cap at export time."
- Record `exported_at` in the CSV so the snapshot time is explicit.

## Acceptance Criteria

The design is complete when the implementation can:

- run locally as a Python CLI with no API keys
- compute the next Monday-through-Friday window
- fetch next week's US earnings events from a public source
- enrich with market cap from a public source
- keep only companies with market cap greater than or equal to 50 billion USD
- write a CSV to `exports/earnings-calendar/`
- print the generated file path and row count

## Implementation Notes

The implementation phase should validate the current public endpoints before locking source adapters. If the NASDAQ wrapper path proves unstable, the fallback is to scrape Yahoo Finance earnings dates or another public calendar source, while preserving the same CLI contract and CSV format.
