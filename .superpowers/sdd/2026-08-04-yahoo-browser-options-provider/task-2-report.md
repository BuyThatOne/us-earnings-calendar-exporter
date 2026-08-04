# Task 2 Report: Playwright Reader And Settings

## Status

Implemented the standalone, lazy sync Playwright reader and browser fallback
settings. `PlaywrightYahooPageReader` keeps the existing
`YahooBrowserPageReader.read_current_page(symbol)` contract, starts Playwright
only when first used, launches standalone Chromium without a user data directory,
creates a non-persistent context, and closes page, context, browser, and
Playwright resources in that order. It navigates only to the public Yahoo
options URL and reads rendered body, quote, and option-table content.

Expected browser startup and navigation errors map to `browser_unavailable` and
`browser_page_unavailable` at the existing provider boundary. The implementation
does not make a live Yahoo request in tests.

`AnalysisSettings` now supplies a final `yahoo_browser` fallback and exposes
browser timeout and delay values. The documented environment variables are
`EARNINGS_OPTIONS_BROWSER_TIMEOUT_SECONDS` and
`EARNINGS_OPTIONS_BROWSER_DELAY_SECONDS`; defaults are 20.0 and 1.0 seconds.

## Changed Files

- `src/earnings_export/sources/yahoo_browser_options.py`
- `src/earnings_export/options_config.py`
- `pyproject.toml`
- `docs/automation/weekly-earnings-options.md`
- `tests/options/test_yahoo_browser_options.py`
- `tests/options/test_options_config.py`

## Test Commands And Results

1. `pytest tests/options/test_yahoo_browser_options.py tests/options/test_options_config.py -v`
   - RED: collection failed with `ImportError` because
     `PlaywrightYahooPageReader` did not exist.
2. `pytest tests/options/test_yahoo_browser_options.py tests/options/test_options_config.py -v`
   - GREEN: `14 passed in 0.03s`.
   - All Playwright interactions were injected runtime fakes; no browser process
     was launched and no Yahoo request was made.
3. `pytest -q`
   - `111 passed, 1 failed in 0.15s`.
   - The only failure is the pre-existing assertion in
     `tests/options/test_models_and_config.py:30`, which expects the old provider
     order `("alpha_vantage", "yahoo")`. Task 2 intentionally changes that order
     to include `"yahoo_browser"`; this file is outside the task's stated scope.
4. `git diff --check`
   - Completed with no output and exit code 0.

## Commit

`feat: add standalone yahoo browser reader`

## Concerns

- Chromium installation is intentionally not attempted here. Operators must run
  `python -m playwright install chromium` before a live CLI execution.

## Review Fix Round 1

### Status

Updated the stale default-provider-order assertion to include the Task 2
`"yahoo_browser"` fallback. This correction changes only test expectation data;
it does not alter product behavior.

### Test Commands And Results

1. `pytest tests/options/test_models_and_config.py::test_load_analysis_settings_uses_safe_defaults -v`
   - RED: `1 failed in 0.02s` because the test expected only
     `("alpha_vantage", "yahoo")`.
2. `pytest tests/options/test_models_and_config.py::test_load_analysis_settings_uses_safe_defaults -v`
   - GREEN: `1 passed in 0.02s`.
3. `pytest -q`
   - `112 passed in 0.12s`.

### Commit

`test: align yahoo browser default provider test`
