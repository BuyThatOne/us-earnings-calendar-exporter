# Task 3 Report: Public OptionSlam EVR Enrichment

## Status

Implemented the public-only OptionSlam EVR adapter in the requested worktree. The adapter has no authentication, registration, form submission, credential handling, access-control bypass, or retry workflow.

## Changes

- Added `EvrResult` with `value`, `source_url`, `status`, and `collected_at` fields.
- Added fixture-safe `parse_optionslam_evr` parsing:
  - Public EVR content returns a float and `available`.
  - Sign-in or membership content returns `authentication_required` with no value.
  - Pages without EVR return `not_found`.
- Added `OptionSlamEvrProvider.fetch_public_evr(symbol)` using an injected `requests.Session`.
- The adapter performs one `GET` only, with `User-Agent: Mozilla/5.0`, `timeout=30`, and redirects disabled. It does not call `POST` or retry after a failed request.
- Transport failures return `request_failed`.
- Added public and login HTML fixtures and focused tests for parsing and the access boundary.

## TDD Evidence

1. Initial focused run failed during collection because `earnings_export.sources.optionslam_evr` did not exist.
2. After the initial implementation, focused tests passed: `5 passed`.
3. A stricter redirect-boundary assertion was added first; the focused suite then failed with the missing `allow_redirects=False` argument.
4. After adding that implementation detail, focused tests passed: `5 passed`.

## Verification

- `pytest tests/options/test_optionslam_evr.py -v`: `5 passed`.
- `pytest -q`: `39 passed`.
- `python3 -m compileall -q src tests`: passed.
- `git diff --check`: passed before staging.

The attempted `python -m compileall -q src tests` command could not run because this environment does not provide a `python` executable; the equivalent available `python3` command passed.

## Concerns

- OptionSlam HTML is external and may change; parser behavior is protected by recorded fixtures but not live-source tests.
- EVR is supplemental context only. This task does not integrate it into the analysis pipeline or report artifacts.
- A redirect response is classified through the response body/status path without following it; this preserves the one-request access boundary.

## Round 1 Fix Evidence: Non-2xx Membership Response

### Root Cause

`OptionSlamEvrProvider.fetch_public_evr` called `response.raise_for_status()` before parsing `response.text`. Therefore, a 401/403 response containing a login or membership page raised `requests.HTTPError` and was classified as `request_failed`, losing the required `authentication_required` classification.

### Fix

- Parse the response body immediately after the single public GET.
- Call `raise_for_status()` after parsing.
- If the status check raises and the parsed body is classified as `authentication_required`, return that parsed result.
- Preserve `request_failed` for transport/HTTP failures whose body is not a login or membership page.
- Keep redirects disabled and retain the existing no-authentication, no-POST, and no-retry boundary.

### Regression Coverage

- Added `tests/fixtures/optionslam_evr/membership_response.html`, representing a membership-gated response body.
- Added a response/session mock whose `raise_for_status()` raises `requests.HTTPError` while exposing that fixture as `response.text`.
- Added `test_fetch_public_evr_classifies_non_2xx_membership_response`, which verifies the result is `authentication_required` with no EVR value.
- Existing transport-failure coverage continues to verify a true non-login failure returns `request_failed` and performs only one GET.

### Fix Verification

- RED: `pytest tests/options/test_optionslam_evr.py -v` failed the new regression with `request_failed` instead of `authentication_required`.
- GREEN: `pytest tests/options/test_optionslam_evr.py -v` passed with `6 passed` after the fix.
- Full suite: `pytest -q` passed with `40 passed`.
- Syntax check: `python3 -m compileall -q src tests` passed.
- Diff check: `git diff --check` passed.
