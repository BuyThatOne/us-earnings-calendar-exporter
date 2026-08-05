# Task 3 Report: Wire OptionSlam Credentials Through CLI Execution

## Outcome

Task 2 had already landed the runtime wiring on `HEAD=465a56c`: `cli.py`
constructs `OptionSlamEvrProvider` with
`settings.optionslam_username` and `settings.optionslam_password`. I did not
modify `src/earnings_export/cli.py` because the new end-to-end regression test
confirmed that behavior is already present.

The remaining Task 3 deliverables are complete:

- Added `test_run_analyze_next_week_options_passes_local_optionslam_credentials`
  to `tests/test_options_e2e.py`. It executes the CLI command through the
  fixture-backed pipeline and records the credentials received by the EVR
  provider.
- Extended `tests/test_automation_docs.py` to enforce the OptionSlam variable
  names and credential-handling policy in both automation documents.
- Updated `docs/automation/local-credentials.md` and
  `docs/automation/weekly-earnings-options.md` to document
  `OPTIONSLAM_USERNAME` and `OPTIONSLAM_PASSWORD`, storage in the same
  owner-only credentials file, environment precedence, and the requirement
  never to commit credentials.

## TDD Evidence

The new tests were added before the documentation edits. The first focused run
produced the expected red result: the e2e credential test passed against the
existing Task 2 wiring, while both documentation contract tests failed because
the new OptionSlam documentation was absent. After updating the documents, the
focused tests passed.

## Verification

Commands run from `/Users/yongningzhang/Documents/earnings`:

```text
pytest tests/test_options_e2e.py::test_run_analyze_next_week_options_passes_local_optionslam_credentials tests/test_automation_docs.py -q
4 passed

pytest tests/test_options_e2e.py tests/test_credentials.py tests/options/test_optionslam_evr.py -q
21 passed

pytest -q
126 passed

git diff --check
passed
```

No credential values were added to either automation document. The test-only
fixture values are local assertions for environment pass-through and are not
written to generated artifacts.
