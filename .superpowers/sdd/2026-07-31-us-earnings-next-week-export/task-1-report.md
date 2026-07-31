# Task 1 Report

## Status

DONE

## Changes

- Added `pyproject.toml` with src-layout packaging, runtime/test dependencies, pytest configuration, and the `earnings-export` console entry point.
- Added the `earnings_export` package marker, module entry point, and minimal CLI implementation.
- Added `tests/conftest.py` to expose the `src` directory during tests.
- Added the required CLI test from the brief.

## Test-First Evidence

1. RED: `pytest tests/test_cli.py::test_main_returns_zero_for_stubbed_export_command -v`
   - Failed during collection with `ModuleNotFoundError: No module named 'earnings_export'`.
2. GREEN: The same command passed with `1 passed` after implementation.

## Verification

- `pytest tests/test_cli.py::test_main_returns_zero_for_stubbed_export_command -v`: `1 passed`
- `pytest -q`: `1 passed`
- `git diff --check`: passed
- Post-commit worktree: clean

## Commit

`c6d707f chore: scaffold earnings export package`

## Concerns

The brief's file list omits `tests/test_cli.py`, but its required test and exact commit command include it. It was added to satisfy those explicit requirements.

## Fix Round 1

### Finding

`main(argv=None)` ignored the process command-line arguments and defaulted to `['export-next-week']`, causing invalid commands invoked through the module or console entry point to run the stubbed workflow.

### Changes

- Updated `src/earnings_export/cli.py` to use `sys.argv[1:]` when `argv` is `None`.
- Added a regression test asserting an invalid process argument raises the usage error.

### Verification

- `pytest tests/test_cli.py::test_main_reads_process_arguments_when_argv_is_none -v`: `1 passed`
- `pytest -q`: `2 passed`
- `git diff --check`: passed
