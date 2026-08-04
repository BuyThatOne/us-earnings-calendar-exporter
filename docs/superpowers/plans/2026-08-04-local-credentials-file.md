# Local Credentials File Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the options-research CLI load an Alpha Vantage key from an owner-only local credentials file without storing or exposing it in the repository.

**Architecture:** A focused credentials module reads one dotenv-style key from `~/.config/earnings-options-research/credentials.env` and validates POSIX permissions. `load_analysis_settings` uses the process environment first, then the file. A setup CLI command creates the private local file without accepting or printing a key.

**Tech Stack:** Python 3.10+, standard library, pytest.

## Global Constraints

- The credentials file is `~/.config/earnings-options-research/credentials.env`.
- Never write, print, log, commit, or include a credential value in test fixtures or artifacts.
- On POSIX systems, reject a credentials file readable by group or others.
- `ALPHAVANTAGE_API_KEY` in the process environment overrides the file value.
- Missing or invalid local credentials leave Alpha Vantage unavailable through existing nonfatal behavior.
- The setup command creates an owner-only empty file and never accepts a key argument.

---

### Task 1: Local Credential Loader

**Files:**
- Create: `src/earnings_export/credentials.py`
- Modify: `src/earnings_export/options_config.py`
- Modify: `tests/options/test_models_and_config.py`
- Create: `tests/test_credentials.py`

**Interfaces:**
- Produces: `DEFAULT_CREDENTIALS_PATH: Path`, `load_alpha_vantage_api_key(environ: Mapping[str, str], credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> str | None`.
- Consumes: `load_analysis_settings(environ: Mapping[str, str], cwd: Path) -> AnalysisSettings`.

- [ ] **Step 1: Write failing credential-loader tests**

```python
def test_loads_only_alpha_vantage_key_from_owner_only_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("# local settings\\nALPHAVANTAGE_API_KEY=test-key\\nOTHER=value\\n")
    credentials.chmod(0o600)
    assert load_alpha_vantage_api_key({}, credentials) == "test-key"


def test_environment_key_takes_precedence_over_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\\n")
    credentials.chmod(0o600)
    assert load_alpha_vantage_api_key({"ALPHAVANTAGE_API_KEY": "env-key"}, credentials) == "env-key"


def test_rejects_group_or_other_readable_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\\n")
    credentials.chmod(0o644)
    with pytest.raises(ValueError, match="owner-only"):
        load_alpha_vantage_api_key({}, credentials)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `pytest tests/test_credentials.py -v`

Expected: FAIL because `earnings_export.credentials` does not exist.

- [ ] **Step 3: Implement secure file parsing and settings integration**

```python
DEFAULT_CREDENTIALS_PATH = Path.home() / ".config" / "earnings-options-research" / "credentials.env"

def load_alpha_vantage_api_key(environ, credentials_path=DEFAULT_CREDENTIALS_PATH):
    if environ.get("ALPHAVANTAGE_API_KEY"):
        return environ["ALPHAVANTAGE_API_KEY"]
    if not credentials_path.exists():
        return None
    if credentials_path.stat().st_mode & 0o077:
        raise ValueError("credentials file must be owner-only")
    for line in credentials_path.read_text().splitlines():
        if line.startswith("ALPHAVANTAGE_API_KEY="):
            return line.partition("=")[2].strip() or None
    return None
```

Update `load_analysis_settings` to call this function. Treat invalid credentials permissions as a configuration error.

- [ ] **Step 4: Run focused and full tests**

Run: `pytest tests/test_credentials.py tests/options/test_models_and_config.py -q && pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/earnings_export/credentials.py src/earnings_export/options_config.py tests/test_credentials.py tests/options/test_models_and_config.py && git commit -m "feat: load local options credentials"`

### Task 2: Private File Setup Command And Documentation

**Files:**
- Modify: `src/earnings_export/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `docs/automation/weekly-earnings-options.md`
- Create: `docs/automation/local-credentials.md`

**Interfaces:**
- Consumes: `DEFAULT_CREDENTIALS_PATH` and `load_alpha_vantage_api_key` from `earnings_export.credentials`.
- Produces: `initialize_credentials_file(path: Path = DEFAULT_CREDENTIALS_PATH) -> Path` and the `init-local-credentials` CLI command.

- [ ] **Step 1: Write failing setup-command test**

```python
def test_init_local_credentials_creates_owner_only_file(monkeypatch, tmp_path, capsys):
    credentials = tmp_path / "config" / "credentials.env"
    monkeypatch.setattr("earnings_export.cli.DEFAULT_CREDENTIALS_PATH", credentials)
    assert main(["init-local-credentials"]) == 0
    assert credentials.exists()
    assert credentials.stat().st_mode & 0o077 == 0
    assert str(credentials) in capsys.readouterr().out
    assert credentials.read_text() == ""
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `pytest tests/test_cli.py::test_init_local_credentials_creates_owner_only_file -v`

Expected: FAIL because the CLI command does not exist.

- [ ] **Step 3: Implement the setup command and update usage text**

```python
def initialize_credentials_file(path=DEFAULT_CREDENTIALS_PATH):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    return path
```

Route `init-local-credentials` in `main`, print only the path, and do not accept extra arguments or key material.

- [ ] **Step 4: Document one-time setup and scheduled use**

Document the exact file path, owner-only mode, one-time command, manual key entry, environment precedence, and that the weekly local Codex task uses the same loader. Do not include a real key or a shell command that puts one in history.

- [ ] **Step 5: Run focused and full tests**

Run: `pytest tests/test_cli.py tests/test_credentials.py tests/options/test_models_and_config.py -q && pytest -q && git diff --check`

Expected: PASS and no whitespace errors.

- [ ] **Step 6: Commit**

Run: `git add src/earnings_export/cli.py tests/test_cli.py docs/automation/weekly-earnings-options.md docs/automation/local-credentials.md && git commit -m "feat: initialize local options credentials"`

## Final Verification

- [ ] Run `pytest -q`.
- [ ] Run `PYTHONPATH=src python3 -m earnings_export init-local-credentials` and verify only the file path is printed.
- [ ] Verify the file mode with `stat -f '%Lp' ~/.config/earnings-options-research/credentials.env` and expect `600`.
- [ ] Confirm `git status --short` contains no credentials file or credential value.
