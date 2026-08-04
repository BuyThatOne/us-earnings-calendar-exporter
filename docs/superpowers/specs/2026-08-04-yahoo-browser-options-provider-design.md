# Yahoo Browser Options Provider Design

## Summary

Add a standalone Playwright Chromium provider that collects current option-chain
data from Yahoo Finance's public options page. The provider is a current-data
fallback for the weekly earnings-options research workflow; it does not collect
historical chains, place orders, use a user Chrome profile, or copy browser
cookies.

## Goals

- Make a public Yahoo Finance page available as a current-chain source when the
  existing Yahoo JSON endpoint is rate-limited or unavailable.
- Run unattended through the existing weekly CLI using a standalone Chromium
  session.
- Normalize underlying price and visible option-contract fields into the
  existing `OptionChainSnapshot` model.
- Preserve the existing research-only behavior, provider provenance, spread
  filter, and artifact formats.
- Report browser-specific failures distinctly in the generated research report.

## Non-Goals

- Browser profile reuse, login, cookie extraction, CAPTCHA solving, or attempts
  to bypass Yahoo access controls.
- Historical option-chain collection from Yahoo.
- Changes to strategy ranking, order-intent generation, scheduling, or the
  existing CSV export command.
- Guaranteed availability of Yahoo data.

## Architecture

The new `YahooBrowserOptionsProvider` implements the existing
`OptionsDataProvider` protocol. It is available only for
`fetch_current_chain(symbol)` and returns `unsupported` for historical-chain
requests.

The weekly CLI creates one standalone Playwright Chromium browser for an
analysis run. The browser provider opens one public page per ticker:

```text
https://ca.finance.yahoo.com/quote/<symbol>/options/
```

It reads only publicly rendered quote and options-table values. The provider
converts those values to existing normalized models:

- underlying price;
- contract symbol;
- option type;
- expiration;
- strike;
- bid and ask;
- implied volatility, when visibly supplied;
- open interest, when visibly supplied; and
- collection timestamp.

The existing provider order becomes Alpha Vantage, Yahoo JSON API, then Yahoo
browser. The first provider that returns an available current snapshot wins.
The browser provider is also eligible as the source for the underlying-price
enrichment path when a preceding provider lacks a valid spot price.

## Browser Collection Boundary

The browser provider launches Chromium without a persistent user-data directory
and does not access Chrome state. It applies a fixed page timeout and a fixed,
conservative delay between ticker navigations. It always closes its page and
browser context when the weekly run finishes, including on a provider failure.

The DOM extraction is intentionally isolated behind a page-reader interface.
Production code uses a Playwright implementation; tests use deterministic
captured page data and do not start a real browser or make live Yahoo requests.
This makes Yahoo markup changes detectable through focused parser tests.

## Failure Handling

The browser provider returns unavailable capability results instead of raising
for expected source failures:

- `browser_rate_limited` for a visible Yahoo rate-limit response or page text;
- `browser_page_unavailable` for navigation failures, non-success responses,
  unavailable content, or a timeout;
- `browser_parse_failed` when a loaded page lacks a valid underlying price or
  yields no valid option contracts; and
- `unsupported` for historical-chain requests.

Unexpected Playwright initialization failures are reported as
`browser_unavailable`. The analysis pipeline records these capability codes in
the existing Markdown and JSON artifacts, continues to other providers, and
omits a ticker only when no usable current snapshot is available.

## Configuration And Dependencies

Add Playwright as an explicit runtime dependency and document the one-time
browser installation command required by the CLI environment. Browser
collection is enabled by default as the final current-chain fallback. The page
timeout and inter-page delay are configuration values with safe defaults, so an
operator can tune them without code changes.

No Yahoo credentials or browser profile paths are accepted as configuration.

## Testing Strategy

Tests remain offline and deterministic. They cover:

- visible quote and call/put rows normalized into `OptionChainSnapshot`;
- numeric values containing currency symbols, commas, percentages, and Yahoo
  placeholders such as `-`;
- malformed rows skipped while valid rows produce `partial_data`;
- rate-limit page detection;
- missing quote/table data reported as `browser_parse_failed`;
- provider-order fallback from Alpha Vantage and Yahoo JSON to the browser
  provider; and
- browser lifecycle cleanup after a successful or failed weekly run.

The complete test suite must pass before integration. A live CLI run may be
used only as an optional verification and must remain research-only.

## Acceptance Criteria

- `analyze-next-week-options` can use a standalone Playwright Chromium session
  to obtain a current Yahoo page snapshot without a user Chrome profile.
- Browser-derived data uses the existing normalized models and is visible in
  provider provenance.
- The browser provider is attempted only after configured higher-priority
  current-chain providers fail or lack a usable spot price.
- Browser failures are distinguishable from the existing JSON API
  `request_failed` state in generated artifacts.
- The workflow cannot submit or simulate an order.
- Existing CSV export and options-analysis tests continue to pass.
