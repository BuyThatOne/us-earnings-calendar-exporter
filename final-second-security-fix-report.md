# Final Second Security Fix Report

## Scope

Addressed only the two latest scoped-review credential-path security findings.
No credential file or credential value was added.

## Changes

- Removed `lstat`-then-`open` validation from credential loading and
  initialization. POSIX paths now use `O_NOFOLLOW` in the atomic open and
  validate the opened descriptor with `fstat`.
- POSIX access now feature-detects `O_NOFOLLOW` and fails with a clear
  credentials security error before creating or opening a credentials path
  when the flag is unavailable.
- On non-POSIX systems, the loader refuses every existing credentials path and
  the initializer refuses an existing path after exclusive creation reports it
  already exists. An initializer can still create a genuinely absent file via
  `O_CREAT | O_EXCL`.
- Documented that non-POSIX local-file credentials cannot subsequently be
  loaded safely; callers on those platforms must use a non-empty environment
  value instead.

## Regression Coverage

- Simulated a missing POSIX `O_NOFOLLOW` for both loader and initializer.
- Simulated non-POSIX behavior for an existing loader path and an existing
  initializer path, including preservation of the existing file contents.
- Kept non-POSIX exclusive creation coverage for a genuinely absent path.

## Verification

- Red: `pytest tests/test_credentials.py tests/test_cli.py tests/test_automation_docs.py -q`
  initially reported `5 failed, 22 passed`: the old code accepted existing
  non-POSIX paths, raised `AttributeError` when `O_NOFOLLOW` was removed, and
  lacked the platform-restriction documentation.
- Green: `pytest tests/test_credentials.py tests/test_cli.py tests/test_automation_docs.py -q && git diff --check`
  reported `27 passed` with a clean diff check.
- Final: `pytest -q && git diff --check` reported `98 passed` with a clean diff
  check.
