# Yahoo Playwright Integration CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make real Yahoo Playwright option-page validation part of every GitHub Actions test run.

**Architecture:** A default pytest integration test uses the production reader/provider and closes it reliably. A single GitHub Actions job provisions Chromium and invokes the existing full suite; source changes are limited to defects reproduced by the live test.

**Tech Stack:** Python 3.10+, pytest, Playwright Chromium, GitHub Actions.

## Global Constraints

- Navigate only to the public AAPL Yahoo options URL using a standalone browser.
- Include the integration test in default `pytest -q` and fail CI on all source failures.
- No retries, profile reuse, cookies, credentials, CAPTCHA handling, skips, or order behavior.
- Add deterministic regression coverage before any source fix.

---

### Task 1: Real Browser Integration Test

**Files:**
- Create: `tests/integration/test_yahoo_browser_live.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing live test.**

```python
@pytest.mark.integration
def test_live_yahoo_options_page_returns_normalized_call_and_put():
    reader = PlaywrightYahooPageReader(timeout_seconds=30.0, delay_seconds=0.0)
    provider = YahooBrowserOptionsProvider(reader, clock=lambda: datetime.now(timezone.utc))
    try:
        result = provider.fetch_current_chain("AAPL")
    finally:
        provider.close()
    assert result.capability.available, result.capability
    assert result.snapshot is not None
    assert result.snapshot.underlying_price and result.snapshot.underlying_price > 0
    assert {contract.option_type for contract in result.snapshot.contracts} == {"call", "put"}
```

- [ ] **Step 2: Run `pytest tests/integration/test_yahoo_browser_live.py -v` and record the real outcome.**
- [ ] **Step 3: Register the `integration` pytest marker without excluding it from default collection.**
- [ ] **Step 4: If the live run exposes a code defect, add a deterministic failing unit test, fix the smallest relevant reader/parser/provider code, and rerun the live test.**
- [ ] **Step 5: Run `pytest tests/options/test_yahoo_browser_options.py tests/integration/test_yahoo_browser_live.py -v`.**
- [ ] **Step 6: Commit with `git commit -m "test: add live yahoo browser integration coverage"`.**

### Task 2: GitHub Actions Browser CI

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Write the workflow that runs for `push` and `pull_request`.**

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: "3.12"
  - run: python -m pip install --upgrade pip
  - run: python -m pip install ".[test]"
  - run: python -m playwright install --with-deps chromium
  - run: pytest -q
```

- [ ] **Step 2: Validate workflow YAML syntax and verify the complete local suite with `pytest -q`.**
- [ ] **Step 3: Commit with `git commit -m "ci: run yahoo browser integration test"`.**

## Final Verification

- [ ] Run the live test once without mocks.
- [ ] Run `pytest -q` and report the exact result.
- [ ] Confirm the workflow neither supplies secrets nor skips integration coverage.
