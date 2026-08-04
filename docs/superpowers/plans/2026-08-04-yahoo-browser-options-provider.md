# Yahoo Browser Options Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone Playwright Chromium fallback that reads Yahoo Finance's public options page into the existing current option-chain models.

**Architecture:** A browser provider separates Playwright navigation and rendered-page extraction from a pure parser. The pipeline runs it after Alpha Vantage and the Yahoo JSON API, and the CLI closes its browser resources in `finally`.

**Tech Stack:** Python 3.10, Playwright sync API, requests, pytest.

## Global Constraints

- Use only `https://ca.finance.yahoo.com/quote/<symbol>/options/` public rendered content.
- Do not use a persistent browser profile, login, Chrome cookies, CAPTCHA solving, or access-control bypasses.
- Historical requests return `unsupported`; expected failures return one of `browser_rate_limited`, `browser_page_unavailable`, `browser_parse_failed`, or `browser_unavailable`.
- Tests are offline, deterministic, and must not start Playwright or make live Yahoo requests.
- The workflow remains research-only and cannot submit or simulate orders.

---

### Task 1: Browser Page Parser

**Files:**
- Create: `src/earnings_export/sources/yahoo_browser_options.py`
- Create: `tests/options/test_yahoo_browser_options.py`

**Interfaces:**
- Produces `YahooBrowserOptionRow(option_type: str, cells: tuple[str, ...])` and `YahooBrowserPageData(body_text: str, underlying_price: str | None, rows: tuple[YahooBrowserOptionRow, ...])`.
- Produces `parse_yahoo_browser_page(page_data: YahooBrowserPageData, symbol: str, collected_at: datetime) -> ProviderResult`.
- Produces `YahooBrowserOptionsProvider(reader: YahooBrowserPageReader, clock: Callable[[], datetime])`.

- [ ] **Step 1: Write failing parser tests**

```python
def test_browser_page_normalizes_visible_quote_calls_and_puts():
    result = parse_yahoo_browser_page(_page_data(), "AAPL", FIXED_TIME)
    assert result.snapshot.underlying_price == 210.50
    assert [(item.option_type, item.strike) for item in result.snapshot.contracts] == [("call", 200.0), ("put", 200.0)]

def test_browser_page_skips_placeholder_or_malformed_rows_as_partial_data():
    result = parse_yahoo_browser_page(_page_data_with_bad_row(), "AAPL", FIXED_TIME)
    assert result.capability.code == "partial_data"
    assert len(result.snapshot.contracts) == 2

def test_browser_page_classifies_rate_limit_and_missing_contracts():
    assert parse_yahoo_browser_page(_rate_limited_page(), "AAPL", FIXED_TIME).capability.code == "browser_rate_limited"
    assert parse_yahoo_browser_page(_empty_page(), "AAPL", FIXED_TIME).capability.code == "browser_parse_failed"
```

- [ ] **Step 2: Run `pytest tests/options/test_yahoo_browser_options.py -v` and confirm it fails because the module is absent.**
- [ ] **Step 3: Implement the pure parser and reader-backed provider.** Parse currency, commas, percent signs, and `-`; reject non-finite values. Parse expiration from Yahoo contract symbols matching `<root>YYMMDD[C|P]########`. Skip invalid rows and return `partial_data` if valid rows remain. Require a positive underlying price and at least one valid contract.
- [ ] **Step 4: Run `pytest tests/options/test_yahoo_browser_options.py -v` and confirm it passes.**
- [ ] **Step 5: Commit with `git commit -m "feat: parse yahoo browser option pages"`.**

### Task 2: Playwright Reader And Settings

**Files:**
- Modify: `src/earnings_export/sources/yahoo_browser_options.py`
- Modify: `src/earnings_export/options_config.py`
- Modify: `pyproject.toml`
- Modify: `docs/automation/weekly-earnings-options.md`
- Modify: `tests/options/test_yahoo_browser_options.py`
- Modify: `tests/options/test_options_config.py`

**Interfaces:**
- Produces `PlaywrightYahooPageReader(timeout_seconds: float, delay_seconds: float)` with `read_current_page(symbol: str) -> YahooBrowserPageData` and `close() -> None`.
- Extends `AnalysisSettings` with `browser_timeout_seconds: float` and `browser_delay_seconds: float`.

- [ ] **Step 1: Write failing tests for timeout-to-`browser_page_unavailable`, initialization-to-`browser_unavailable`, settings values `25.0` and `1.5`, and lifecycle `close()`.**
- [ ] **Step 2: Run `pytest tests/options/test_yahoo_browser_options.py tests/options/test_options_config.py -v` and confirm the fields and failure mapping are absent.**
- [ ] **Step 3: Implement a lazy standalone sync Playwright Chromium reader.** Start Playwright only at first use; call `chromium.launch()` without any user data directory; create a non-persistent context; open and close one page per ticker; navigate to the exact public URL; gather rendered quote/table text; delay between pages; close context, browser, then Playwright even after partial startup. Add `playwright>=1.62`; default order `("alpha_vantage", "yahoo", "yahoo_browser")`, timeout `20.0`, delay `1.0`; reject non-positive timeout and negative delay. Document `python -m playwright install chromium` and the two environment variables.
- [ ] **Step 4: Run `pytest tests/options/test_yahoo_browser_options.py tests/options/test_options_config.py -v` and confirm it passes with no browser launch.**
- [ ] **Step 5: Commit with `git commit -m "feat: add standalone yahoo browser reader"`.**

### Task 3: Pipeline And CLI Fallback

**Files:**
- Modify: `src/earnings_export/options_pipeline.py`
- Modify: `src/earnings_export/cli.py`
- Modify: `tests/options/test_options_pipeline.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces `close_options_providers(providers: Sequence[OptionsDataProvider]) -> None`.
- Keeps `analyze_events(...) -> AnalysisRunResult` and makes `yahoo_browser` a final current-chain and spot-enrichment fallback.

- [ ] **Step 1: Write failing tests that Alpha Vantage then Yahoo JSON failure invokes `yahoo_browser`, that browser snapshots preserve `provider == "yahoo_browser"`, that current-only Yahoo providers are skipped for history, and that CLI cleanup executes if analysis raises.**
- [ ] **Step 2: Run `pytest tests/options/test_options_pipeline.py tests/test_cli.py -v` and confirm fallback and cleanup are absent.**
- [ ] **Step 3: Implement ordered fallback and cleanup.** Build the browser reader/provider in `run_analyze_next_week_options`; make both Yahoo providers current-only in historical loops; make browser eligible for spot enrichment after JSON fails or lacks a valid price; wrap analysis and artifact writing in `try/finally` using the generic close helper.
- [ ] **Step 4: Run `pytest tests/options/test_options_pipeline.py tests/test_cli.py -v && pytest -q` and confirm all tests pass.**
- [ ] **Step 5: Commit with `git commit -m "feat: use yahoo browser fallback in weekly analysis"`.**

## Final Verification

- [ ] Run `pytest -q`.
- [ ] Run `PYTHONPATH=src python3 -m earnings_export analyze-next-week-options` only when Chromium is installed; otherwise report the one-time `python -m playwright install chromium` requirement.
- [ ] Inspect browser provenance only; never submit or simulate an order.
