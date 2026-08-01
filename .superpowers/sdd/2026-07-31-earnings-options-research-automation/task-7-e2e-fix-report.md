# Task 7 E2E Fix Report

## Change

The shared E2E command helper now explicitly sets
`EARNINGS_OPTIONS_OUTPUT_DIR` to `tmp_path / "exports" / "earnings-options"`
and `EARNINGS_OPTIONS_MAX_SPREAD_PCT` to `0.10`. This prevents inherited
environment values from writing artifacts outside pytest temporary storage or
relaxing the wide-spread empty-candidate assertion.

The real `analyze-next-week-options` CLI, pipeline, and artifact writer remain
covered by both fixture-backed tests.

## Regression Evidence

Before the change, running with
`EARNINGS_OPTIONS_OUTPUT_DIR=/tmp/earnings-options-e2e-inherited-output` and
`EARNINGS_OPTIONS_MAX_SPREAD_PCT=0.50` caused both E2E tests to fail because
artifacts were written to the inherited output path instead of `tmp_path`.

After the change, the same conflicting inherited environment produced the
expected isolated behavior.

## Verification

- `EARNINGS_OPTIONS_OUTPUT_DIR=/tmp/earnings-options-e2e-inherited-output EARNINGS_OPTIONS_MAX_SPREAD_PCT=0.50 pytest -q tests/test_options_e2e.py`: `2 passed in 0.05s`.
- `pytest -q`: `70 passed in 0.08s`.
