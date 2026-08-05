# Yahoo Playwright Integration CI Design

## Goal

Run a real standalone Playwright Chromium test against Yahoo Finance's public
AAPL options page on every GitHub Actions CI run, and fix browser-provider
defects that the test proves.

## Scope

The integration test uses `PlaywrightYahooPageReader` and
`YahooBrowserOptionsProvider` without mocks. It navigates only to
`https://ca.finance.yahoo.com/quote/AAPL/options/` and asserts a normalized
available snapshot with a positive underlying price, at least one call, at
least one put, valid contract symbols, and finite non-negative bid/ask values.
The test always closes the provider in a `finally` block.

The test is marked `integration` but is included in the default pytest suite.
It is strict: Yahoo page, rate-limit, browser-installation, navigation, markup,
or data failures fail CI. There are no retries, credentials, persistent browser
profiles, cookie reuse, CAPTCHA handling, skips, or soft-failure reporting.

## CI Environment

Add one GitHub Actions workflow for pushes and pull requests. It checks out the
repository, installs a supported Python version, installs the project with test
dependencies, runs `python -m playwright install --with-deps chromium`, and
runs `pytest -q`. The job needs no secrets and no browser-profile configuration.

## Defect Handling

The first local integration run is the source of truth for live behavior. If it
fails, capture the failure capability or assertion, trace it through reader,
parser, and provider boundaries, add a deterministic regression test when a
code defect is found, implement the smallest fix, and rerun the live test plus
the full suite. External unavailability remains a failing CI result rather than
being hidden.

## Acceptance Criteria

- A real browser test is part of `pytest -q` and does not mock Playwright.
- GitHub Actions provisions Chromium and executes that test for every push and
  pull request.
- The test stays public-page-only and research-only.
- Any provider defect exposed by the first live run has a deterministic test
  and a verified fix.
- The final local full suite passes, subject to Yahoo's live availability.
