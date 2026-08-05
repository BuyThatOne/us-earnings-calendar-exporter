# Task 4 Report: Durable NTES Investigation Harness

## Scope

- Added `diagnose_optionslam_response(...)` in `src/earnings_export/sources/optionslam_evr.py`.
- Added offline regression coverage in `tests/options/test_optionslam_investigation.py`.
- Added sanitized NTES fixture `tests/fixtures/optionslam_evr/ntes_failure_response.html`.
- Added sanitized harness script `scripts/optionslam_ntes_diagnose.py`.

## TDD Evidence

### Red

Command:

```bash
pytest tests/options/test_optionslam_investigation.py -v
```

Observed result:

- Exit code: `2`
- Failure mode: import-time error because `diagnose_optionslam_response` did not exist yet.
- Exact failing message:

```text
ImportError: cannot import name 'diagnose_optionslam_response' from 'earnings_export.sources.optionslam_evr'
```

### Green

Command:

```bash
pytest tests/options/test_optionslam_investigation.py -v
```

Observed result:

- Exit code: `0`
- `1 passed in 0.06s`

## Focused Verification

Command:

```bash
pytest tests/options/test_optionslam_investigation.py tests/options/test_optionslam_evr.py -q
```

Observed result:

- Exit code: `0`
- `10 passed in 0.07s`

## Final Verification

### Full test suite

Command:

```bash
pytest -q
```

Observed result:

- Exit code: `0`
- `127 passed in 11.84s`

### Compile check

First attempted command from the brief:

```bash
python -m compileall src tests scripts
```

Observed result:

- Exit code: `127`
- Environment issue: `/bin/bash: python: command not found`

Durable follow-up command used in this workspace:

```bash
python3 -m compileall src tests scripts
```

Observed result:

- Exit code: `0`
- Completed without syntax errors across `src`, `tests`, and `scripts`.

### Sanitized harness output

Command:

```bash
PYTHONPATH=src python3 scripts/optionslam_ntes_diagnose.py --fixture tests/fixtures/optionslam_evr/ntes_failure_response.html --symbol NTES
```

Observed result:

- Exit code: `0`
- Output:

```text
symbol=NTES mode=fixture http_status=403 final_url=https://www.optionslam.com/ntes/ result_status=authentication_required
```

Confirmed that the output contains only sanitized status information and does not print HTML, cookies, usernames, or passwords.

### Whitespace check

Command:

```bash
git diff --check
```

Observed result:

- Exit code: `0`
- No whitespace errors reported.

## Notes

- The harness is offline and deterministic by default through `--fixture`.
- Live mode is explicit via `--live` and still prints only sanitized metadata.
- Existing unrelated worktree changes were preserved.
- The optional live `analyze-next-week-options` verification was not run because the brief marks it optional.
