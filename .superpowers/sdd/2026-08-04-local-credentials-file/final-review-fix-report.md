# Final Review Fix Report

## Scope

Addressed only the final whole-branch review findings for local credentials.
No credential values or files were added.

## Changes

- All `load_analysis_settings` tests now monkeypatch the local credentials path
  to a missing temporary file, preventing a developer's default credentials
  file from influencing assertions.
- Owner-only permission validation and `fchmod` run only on POSIX systems. On
  non-POSIX systems, loading accepts the file without interpreting Unix mode
  bits and initialization creates an empty regular file without calling
  `chmod`.
- The loader rejects symbolic links and non-regular paths before opening the
  file, then uses a descriptor with `O_NOFOLLOW` on POSIX systems.
- Initialization rejects symbolic links and non-regular paths. It opens or
  creates the file by descriptor and uses `fchmod` on that descriptor, so it
  does not use `touch` or `chmod` on a symlink path.
- Active setup, runbook, and automation-prompt commands use
  `PYTHONPATH=src python3 -m earnings_export ...`.

## Regression Evidence

- The new focused regression tests failed before implementation: 9 failures
  covered unconditional mode enforcement, accepted symbolic links and
  directories, and outdated runnable documentation commands.
- Regression coverage includes POSIX permission enforcement, non-POSIX mode
  behavior, symbolic-link rejection in both loader and initializer, regular
  file validation, and temporary-path isolation for settings tests.

## Verification

- `PYTHONPATH=src python3 -m pytest tests/test_credentials.py tests/test_cli.py tests/options/test_models_and_config.py tests/test_automation_docs.py -q`: `32 passed in 0.09s`.
- `PYTHONPATH=src python3 -m pytest -q`: `95 passed in 0.13s`.
- `git diff --check`: passed after this report was added.
