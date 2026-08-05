# Earnings Options Research Automation Design

## Summary

Add a research-only earnings-options workflow to the existing `earnings_export` Python project. A Codex project cron automation will run at 10:00 America/New_York every Friday and invoke a deterministic project CLI. The CLI will analyze the next US business week's existing earnings universe: US-listed companies with market capitalization of at least 50 billion USD.

The workflow will collect option-chain and underlying-price data, compare the current implied move and implied-volatility context with historical earnings reactions, and generate neutral-strategy research candidates. It will produce a human-readable Markdown report and a machine-readable JSON order-intent artifact. It must not place orders.

Alpha Vantage is the first configured options provider and is used only for capabilities available to the supplied key. The data layer remains provider-agnostic so that Yahoo public data, a broker API, or a different paid provider can be added later without changing analysis behavior.

## Goals

- Run the weekly research workflow through a Codex scheduled prompt at 10:00 ET every Friday.
- Reuse the existing next-week earnings calendar and 50 billion USD market-cap filter.
- Acquire current options bid/ask data, underlying price, IV, and Greeks when available.
- Use Alpha Vantage historical option-chain data and stock prices whenever its entitlement permits.
- Include public, unauthenticated OptionSlam EVR as optional historical context.
- Reject a candidate when any selected contract has a bid-ask spread greater than 15% of its midpoint by default.
- Rank neutral strategy candidates, preferring defined-risk structures while permitting explicit higher-risk alternatives.
- Write Markdown and JSON artifacts with source provenance and data-quality flags.
- Preserve a future, explicit broker-execution integration point without enabling order placement.

## Non-Goals

- No automatic order placement, broker authentication, position sizing, or account-risk controls in this phase.
- No requirement to manufacture historical IV data when Alpha Vantage does not provide it.
- No scraping of authenticated, membership-only, or access-controlled OptionSlam content.
- No guarantee of profitability or personalized investment advice.
- No change to the existing `export-next-week` CSV behavior.

## Schedule And Codex Prompt

The Codex project automation uses a cron schedule in `America/New_York` at 10:00 every Friday. It runs after the opening market has had time to establish more representative option spreads; the workflow must not start at 09:30 and sleep.

The versioned prompt instructs Codex to:

1. Run the analysis CLI.
2. Read the generated JSON and Markdown artifacts.
3. Research event-specific public context only when an eligible candidate exists.
4. Summarize the ranked candidates, source limitations, and warnings.
5. State plainly when no eligible candidate was found.

The prompt orchestrates and interprets artifacts. It does not fetch market data directly, calculate metrics, or create orders itself.

## CLI

Add a separate command without changing the existing exporter:

```bash
python -m earnings_export analyze-next-week-options
```

The command accepts configuration through environment variables and configuration files. At minimum, it supports a provider selection, report-output directory, and liquidity-spread threshold. Sensitive values such as `ALPHAVANTAGE_API_KEY` are read from the local environment only. They must never appear in the Codex prompt, Markdown report, JSON artifact, logs, or committed files.

The command exits successfully when no candidate qualifies. It writes a report that reports `no_candidates` and explains aggregate exclusion counts. It exits non-zero only for unrecoverable prerequisites, such as failure to obtain the earnings universe or inability to create artifacts.

## Architecture

```text
Codex weekly cron prompt (Friday 10:00 ET)
  -> analyze-next-week-options CLI
     -> existing earnings-calendar pipeline
     -> provider registry
        -> Alpha Vantage options and stock provider
        -> Yahoo public current-chain fallback
        -> OptionSlam public EVR enrichment
        -> future broker or licensed-provider adapter
     -> normalized snapshots and historical event study
     -> liquidity filter and neutral-strategy ranking
     -> Markdown report + JSON order intents
  -> Codex reads artifacts and publishes the weekly summary
```

The analysis core depends on provider interfaces rather than Alpha Vantage response formats. Each provider returns normalized models and a capability result. A provider can return partial data; the core records unavailable fields and continues only when the candidate still has the minimum data required for a valid analysis.

## Data Providers

### Alpha Vantage

Alpha Vantage is the preferred provider when `ALPHAVANTAGE_API_KEY` is configured. The adapter probes or handles access per endpoint and declares capabilities for:

- current/realtime option chain;
- current bid/ask, IV, and Greeks;
- point-in-time historical options chain;
- historical underlying prices.

An unavailable entitlement is a normal partial-data result, not a parser failure. Historical IV analysis is omitted rather than estimated from unrelated data when the historical-options endpoint is unavailable.

### Yahoo Fallback

Yahoo is a no-signup fallback only for current option-chain and underlying fields. It is not used as a source of historical option-chain data. Results are tagged with `source: yahoo` and the collection timestamp.

### OptionSlam EVR

The workflow attempts to collect EVR only from pages that are public and unauthenticated at run time. It stores:

- `optionslam_evr`;
- source URL;
- collection timestamp;
- availability or parsing-status flag.

It does not register accounts, send credentials, scrape behind a membership wall, or treat an unavailable EVR as a candidate failure. EVR is supplemental context, not an input that overrides the project's own historical-move calculations.

### Future Providers

Future data providers, including a broker, implement the same interfaces. A broker adapter may later supply market data and order placement, but order submission requires a separately configured execution feature and a distinct explicit user decision.

## Normalized Data Model

`OptionChainSnapshot` captures one provider response:

```text
- symbol
- collected_at
- provider
- provider_capabilities
- underlying_price
- contracts[]
  - option_symbol
  - option_type
  - expiration
  - strike
  - bid
  - ask
  - midpoint
  - bid_ask_spread_pct
  - implied_volatility | null
  - greeks | null
  - open_interest | null
  - quote_timestamp | null
```

`EarningsHistory` captures transparent historical analysis:

```text
- historical_earnings_events[]
- one_day_post_earnings_moves[]
- absolute_move_mean
- absolute_move_median
- absolute_move_max
- historical_iv_observations[] | unavailable reason
- optionslam_evr | null
- source_provenance[]
```

`StrategyCandidate` captures a research recommendation:

```text
- ticker
- event details
- selected expiration and legs
- strategy_type
- defined_risk: bool
- entry_limit
- maximum_loss | null
- implied_move
- historical-move comparison
- historical-IV comparison | null
- liquidity result
- ranked rationale
- warnings[]
- execution_status: research_only
```

## Analysis And Strategy Ranking

The CLI first selects expirations that cover the earnings event and then evaluates contracts required by a proposed strategy. Every selected contract must have a positive bid and ask and a bid-ask spread percentage no greater than 15% of midpoint by default. A candidate failing this check is omitted entirely.

For eligible symbols, the analysis calculates a market-implied move from a near-the-money straddle when valid call and put quotes exist. It compares that move with the mean, median, and maximum one-day post-earnings absolute moves from the historical event study. It adds available historical IV changes and OptionSlam EVR as labeled context.

The ranking engine may consider iron condors, iron butterflies, calendars, straddles, and strangles. Defined-risk strategies rank ahead of undefined-risk choices when the evidence is otherwise comparable. An undefined-risk strategy must include an explicit warning and may not be represented as safer or preferred merely because it has a higher premium.

No strategy is a trade instruction or profit promise. The report must state that the result is research and that missing or delayed source data weakens the confidence of a candidate.

## Artifacts

Artifacts are stored under a dedicated project directory:

```text
exports/earnings-options/
  YYYY-MM-DD/
    earnings_options_research.md
    earnings_options_order_intents.json
    option_chain_snapshots.json
```

The Markdown report contains the run timestamp, provider capability table, exclusion counts, eligible candidates, sources, warnings, and a no-candidate statement when applicable.

The JSON artifact is schema-versioned and includes all strategy candidates, evidence fields, source provenance, and `execution_status: "research_only"`. It contains no credentials and no broker-specific order submission payload. A future execution adapter can translate a validated order intent into a broker-specific request.

## Error Handling

- Earnings-universe failure: fail the CLI non-zero; no report is considered complete.
- Alpha Vantage entitlement, rate-limit, or partial response: record the capability failure and attempt eligible fallback sources.
- Yahoo fallback failure: retain an Alpha-derived candidate if sufficient data exists; otherwise omit that symbol with an exclusion reason.
- OptionSlam EVR unavailable or inaccessible: record the field as unavailable and continue.
- No eligible option contract or spread-filter failure: omit the symbol and count the reason.
- No candidates: write both artifacts with an empty candidate list and successful run status.
- Artifact write failure: fail non-zero and report the destination path and error.

## Testing Strategy

Implementation follows test-first development with recorded fixtures; normal tests do not call live providers.

Minimum coverage:

- Existing earnings-universe output is reused without behavioral regression.
- Provider capability resolution distinguishes available, denied, rate-limited, malformed, and unavailable responses.
- Alpha Vantage fixtures normalize current and historical chain responses.
- Yahoo fallback activates only for fields Alpha Vantage cannot provide.
- OptionSlam EVR parser accepts public fixture pages and rejects login/membership pages without retrying access.
- Midpoint and spread calculations cover zero, missing, and boundary values; exactly 15% qualifies and values above it do not when the default threshold is used.
- Historical earnings-move calculations are deterministic for before-market and after-market event dates.
- Strategy ranking prefers a defined-risk equivalent over an undefined-risk candidate.
- Empty candidate runs write valid Markdown and JSON artifacts and return success.
- JSON serialization includes source provenance and never includes credential values.

## Acceptance Criteria

- A Codex cron prompt can run the CLI at 10:00 ET each Friday.
- The CLI produces Markdown and JSON artifacts for the next week's existing filtered earnings universe.
- Alpha Vantage access is optional and partial entitlements degrade gracefully.
- Yahoo is used only as a current-data fallback.
- Publicly accessible OptionSlam EVR appears when obtainable and is otherwise explicitly unavailable.
- Candidates with any selected leg wider than 10% bid-ask spread are omitted.
- No submitted order is possible from the workflow.
- Existing CSV export tests continue to pass.
