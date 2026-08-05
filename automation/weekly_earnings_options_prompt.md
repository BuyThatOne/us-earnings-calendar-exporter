# Weekly Earnings Options Research

Run `PYTHONPATH=src python3 -m earnings_export analyze-next-week-options` from the
project root.

After the command completes, read the generated artifacts for the current UTC run
date:

- `exports/earnings-options/<RUN-DATE>/option_chain_snapshots.json`
- `exports/earnings-options/<RUN-DATE>/earnings_options_research.md`
- `exports/earnings-options/<RUN-DATE>/earnings_options_order_intents.json`

Use `option_chain_snapshots.json` as the primary input for analysis. Treat any
Python-generated candidate output as a transport artifact only, not as the
strategy decision.

Your job is to review the company list and raw option quote data and generate the
options strategy to profit from the IV changes around earning, by yourself.

## Objective

For each company with usable option-chain data, determine whether there is a
credible earnings-related options strategy candidate.

You ca decide this from the raw data generated from the python scripts. Do not rely on any hard-coded
threshold filters produced by Python. Feel free to search any additonal data from internet during the process.

## Required Evaluation Approach

Use your judgment and evaluate liquidity contextually.

Get current stock price from internet.

You must consider at least:

- bid/ask spread width relative to premium;
- whether quotes appear real and two-sided;
- whether strikes around spot are continuous enough to support the structure;
- whether the relevant legs appear tradeable;
- open interest, when available;
- whether there is more than one usable expiration when the strategy requires it;
- whether the chain is sparse, stale, one-sided, or unusually wide; and
- whether a simpler structure is more credible than a more complex one.

The list above is my recommendation, feel free to add more factors that you deem important.

Prefer defined-risk structures when the chain supports them, but you may choose
an undefined-risk structure if it is the most credible available candidate. If
no structure is credible, choose `no candidate`.


## Required Output For Each Selected Candidate

For each company you select as a candidate, provide:

- ticker;
- earnings date;
- proposed strategy type;
- selected expiration;
- selected legs;
- bid and ask for each leg;
- midpoint-based estimated entry;
- liquidity assessment;
- why this strategy is preferable to the obvious alternatives;
- key risks; and
- confidence level: `high`, `medium`, or `low`.

## Required Output For Rejected Companies

For each company you reject, state the main reason, such as:

- insufficient liquidity;
- unusable strike structure;
- missing second expiration for a calendar;
- too many wide or one-sided quotes; or
- chain available but not credible for a research candidate.

## Constraints

This is research only. Do not submit or simulate an order. Do not make any
changes outside the generated research artifacts. Do not fabricate quotes,
strikes, expirations, or legs. If the raw data is insufficient, say so plainly.
If no company has a viable candidate, state exactly: "No eligible candidate was found."

## Interpretation Rules

- Use the raw JSON as the source of truth.
- Historical context, EVR, and IV history are helpful but optional.
- Missing historical context is a limitation, not an automatic rejection.
- Be conservative when liquidity is weak or the structure requires too many
  questionable legs.
- When two strategies look plausible, prefer the one with clearer liquidity and
  simpler justification.

## Output Format

Write a concise Markdown report with exactly these sections:

1. Eligible Candidates
2. recommended strategy
3. Details for recommended strategy with P/L analysis.
4. Rejected Companies
5. Data Limitations
6. Research Rationale

The report must explicitly cover eligible candidates, data limitations, and
research rationale.

Be specific. Avoid generic options education.
