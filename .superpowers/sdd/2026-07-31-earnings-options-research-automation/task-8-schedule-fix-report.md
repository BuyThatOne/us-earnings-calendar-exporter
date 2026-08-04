# Task 8 Schedule Fix Report

## Change

Strengthened `tests/test_automation_docs.py` without changing the prompt or
runbook. The tests now enforce the versioned prompt path, exact project working
directory, environment-only `ALPHAVANTAGE_API_KEY` configuration with no
credential assignments, empty-result reporting, research-only/no-order language,
failure reporting, and a substantive disable/re-enable procedure. The exact
Friday 10:00 `America/New_York` schedule assertions remain in place.

## Verification

- `pytest -q tests/test_automation_docs.py`: `2 passed in 0.01s`.
- `pytest -q`: `72 passed in 0.08s`.
- `git diff --check`: passed.

No external automation was configured.
