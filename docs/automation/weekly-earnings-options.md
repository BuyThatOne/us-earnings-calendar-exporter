# Weekly Earnings Options Research Automation

## Purpose

This workflow runs the deterministic, research-only options analysis for the
following week's earnings calendar. It produces research artifacts only; it must
never submit or simulate an order.

## Prerequisites

Run the workflow from the project working directory:

```text
/Users/yongningzhang/Documents/earnings
```

Complete the one-time local setup in
[`local-credentials.md`](local-credentials.md). The loader checks the
automation environment first, then the owner-only local credentials file. Do not
place the key value in this repository, the prompt, logs, or generated
artifacts.

## Manual Run

From the project root, run:

```bash
PYTHONPATH=src python3 -m earnings_export analyze-next-week-options
```

The command is deterministic with the configured providers and writes dated
research-only artifacts. It does not place or simulate trades.

## Output Locations

Each run writes the following files, where `<YYYY-MM-DD>` is the UTC run date:

```text
exports/earnings-options/<YYYY-MM-DD>/earnings_options_research.md
exports/earnings-options/<YYYY-MM-DD>/earnings_options_order_intents.json
exports/earnings-options/<YYYY-MM-DD>/option_chain_snapshots.json
```

Read the Markdown and JSON research artifacts to summarize eligible candidates,
data limitations, and research rationale. If the candidate array is empty, report:
"No eligible candidate was found." Do not submit or simulate an order.

## Schedule Configuration

Configure the project-level scheduler to use the versioned prompt at:

```text
automation/weekly_earnings_options_prompt.md
```

Use this cron schedule and timezone:

```text
kind: cron
expression: 0 10 * * 5
timezone: America/New_York
working_directory: /Users/yongningzhang/Documents/earnings
```

This runs every Friday at 10:00 in `America/New_York`. Configure the scheduler to
invoke the prompt from the project working directory. Through the scheduler's
environment configuration, `ALPHAVANTAGE_API_KEY` may be provided in its
environment; that value takes precedence over the local file. Otherwise the
local loader reads the configured credentials file.

## Failures And Disabling

If the command exits nonzero or an expected artifact is missing, report the failure
and its available diagnostic output. Do not retry by changing provider settings,
do not fabricate a summary, and do not submit or simulate an order.

To disable the workflow, disable or delete the project-level cron schedule. Leave
the versioned prompt and this runbook in place so the configuration remains
reviewable. Re-enable it only after restoring the same cron expression, timezone,
working directory, and credentials setup.
