# OptionSlam Authenticated Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend OptionSlam EVR retrieval so the weekly options workflow uses public access first and falls back to one authenticated session loaded from the existing local credentials file when membership gating blocks EVR.

**Architecture:** Keep the existing `OptionSlamEvrProvider` as the only EVR provider entrypoint and add authenticated fallback inside it. Reuse the owner-only local credentials file for `OPTIONSLAM_USERNAME` and `OPTIONSLAM_PASSWORD`, add a small generic credential-reader helper instead of duplicating parsing logic, and add a durable NTES investigation helper or fixture so the August 5, 2026 mismatch remains reproducible and reviewable.

**Tech Stack:** Python 3.10+, requests, standard library, pytest.

## Global Constraints

- Reuse `~/.config/earnings-options-research/credentials.env`; do not create a second credential store.
- Never write, print, log, commit, or include OptionSlam credential values, cookies, or private page content in artifacts or tests.
- Public OptionSlam EVR remains the first attempt for every symbol.
- Authenticated OptionSlam access is fallback-only and is attempted only after a membership-gated public response.
- EVR remains supplemental context; any OptionSlam failure stays nonfatal for the weekly options analysis.
- The repository must contain a durable investigation mechanism for the August 5, 2026 `NTES` failure mode.
- Tests are offline and deterministic; normal test runs must not call live OptionSlam.

---

### Task 1: Extend Local Credentials Loading For OptionSlam

**Files:**
- Modify: `src/earnings_export/credentials.py`
- Modify: `src/earnings_export/options_config.py`
- Modify: `tests/test_credentials.py`
- Modify: `tests/options/test_models_and_config.py`

**Interfaces:**
- Produces: `load_named_credential(environ: Mapping[str, str], credential_name: str, credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> str | None`
- Produces: `load_alpha_vantage_api_key(environ: Mapping[str, str], credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> str | None`
- Produces: `load_optionslam_credentials(environ: Mapping[str, str], credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> tuple[str | None, str | None]`
- Extends: `AnalysisSettings` with `optionslam_username: str | None` and `optionslam_password: str | None`
- Consumes: `load_analysis_settings(environ: Mapping[str, str], cwd: Path) -> AnalysisSettings`

- [ ] **Step 1: Write the failing credential tests**

```python
def test_load_named_credential_reads_requested_key_only(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text(
        "# local settings\n"
        "ALPHAVANTAGE_API_KEY=test-key\n"
        "OPTIONSLAM_USERNAME=proto-user\n"
        "OPTIONSLAM_PASSWORD=proto-pass\n"
    )
    credentials.chmod(0o600)

    assert load_named_credential({}, "OPTIONSLAM_USERNAME", credentials) == "proto-user"
    assert load_named_credential({}, "OPTIONSLAM_PASSWORD", credentials) == "proto-pass"


def test_optionslam_environment_values_take_precedence_over_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text(
        "OPTIONSLAM_USERNAME=file-user\n"
        "OPTIONSLAM_PASSWORD=file-pass\n"
    )
    credentials.chmod(0o600)

    assert load_optionslam_credentials(
        {
            "OPTIONSLAM_USERNAME": "env-user",
            "OPTIONSLAM_PASSWORD": "env-pass",
        },
        credentials,
    ) == ("env-user", "env-pass")


def test_load_analysis_settings_reads_local_optionslam_credentials(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.env"
    credentials.write_text(
        "ALPHAVANTAGE_API_KEY=file-key\n"
        "OPTIONSLAM_USERNAME=proto-user\n"
        "OPTIONSLAM_PASSWORD=proto-pass\n"
    )
    credentials.chmod(0o600)
    monkeypatch.setattr(options_config, "DEFAULT_CREDENTIALS_PATH", credentials)

    settings = load_analysis_settings({}, tmp_path)

    assert settings.alpha_vantage_api_key == "file-key"
    assert settings.optionslam_username == "proto-user"
    assert settings.optionslam_password == "proto-pass"
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `pytest tests/test_credentials.py tests/options/test_models_and_config.py -v`

Expected: FAIL because `load_named_credential`, `load_optionslam_credentials`, and the new `AnalysisSettings` fields do not exist.

- [ ] **Step 3: Implement generic credential loading and settings wiring**

```python
def load_named_credential(
    environ: Mapping[str, str],
    credential_name: str,
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
) -> str | None:
    if environ.get(credential_name):
        return environ[credential_name]
    descriptor = _open_credentials_file(credentials_path)
    if descriptor is None:
        return None
    with os.fdopen(descriptor, encoding="utf-8") as credentials_file:
        for line in credentials_file:
            if line.startswith(f"{credential_name}="):
                return line.partition("=")[2].strip() or None
    return None


def load_optionslam_credentials(
    environ: Mapping[str, str],
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
) -> tuple[str | None, str | None]:
    return (
        load_named_credential(environ, "OPTIONSLAM_USERNAME", credentials_path),
        load_named_credential(environ, "OPTIONSLAM_PASSWORD", credentials_path),
    )
```

Update `load_alpha_vantage_api_key` to delegate to `load_named_credential`, and update `AnalysisSettings` plus `load_analysis_settings` to carry the two new OptionSlam values.

- [ ] **Step 4: Run focused and broader tests**

Run: `pytest tests/test_credentials.py tests/options/test_models_and_config.py tests/options/test_options_config.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/earnings_export/credentials.py src/earnings_export/options_config.py tests/test_credentials.py tests/options/test_models_and_config.py && git commit -m "feat: load local optionslam credentials"`

### Task 2: Add Authenticated Fallback To OptionSlam EVR Provider

**Files:**
- Modify: `src/earnings_export/sources/optionslam_evr.py`
- Modify: `tests/options/test_optionslam_evr.py`
- Modify: `tests/options/test_options_pipeline.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Extends: `OptionSlamEvrProvider.__init__(session: requests.Session, clock: Callable[[], datetime] = ..., username: str | None = None, password: str | None = None) -> None`
- Keeps: `OptionSlamEvrProvider.fetch_public_evr(symbol: str) -> EvrResult`
- Produces: `_login() -> bool` or equivalent internal helper that establishes one reusable authenticated session
- Produces: optional `status` values `login_failed` and `authentication_required`
- Consumes: `AnalysisSettings.optionslam_username`, `AnalysisSettings.optionslam_password`

- [ ] **Step 1: Write the failing provider tests**

```python
def test_fetch_public_evr_uses_authenticated_fallback_after_membership_gate():
    session = LoginThenSymbolSession(
        public_html=load_fixture("optionslam_evr/login_page.html"),
        authenticated_html=load_fixture("optionslam_evr/authenticated_page.html"),
    )
    provider = OptionSlamEvrProvider(
        session=session,
        clock=lambda: FIXED_TIME,
        username="proto-user",
        password="proto-pass",
    )

    result = provider.fetch_public_evr("AAPL")

    assert result.value == 6.5
    assert result.status == "available"
    assert session.login_calls == 1
    assert session.symbol_get_calls == 2


def test_fetch_public_evr_does_not_login_when_public_page_is_available():
    session = RecordingSession()
    provider = OptionSlamEvrProvider(
        session=session,
        clock=lambda: FIXED_TIME,
        username="proto-user",
        password="proto-pass",
    )

    result = provider.fetch_public_evr("AAPL")

    assert result.status == "available"
    assert session.post_calls == 0


def test_fetch_public_evr_reports_login_failed_without_retry_loop(load_fixture):
    session = FailedLoginSession(load_fixture("optionslam_evr/login_page.html"))
    provider = OptionSlamEvrProvider(
        session=session,
        clock=lambda: FIXED_TIME,
        username="proto-user",
        password="wrong-pass",
    )

    result = provider.fetch_public_evr("AAPL")

    assert result.value is None
    assert result.status == "login_failed"
    assert session.login_calls == 1
    assert session.symbol_get_calls == 1
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `pytest tests/options/test_optionslam_evr.py tests/options/test_options_pipeline.py -v`

Expected: FAIL because the provider has no credential-aware constructor or authenticated fallback.

- [ ] **Step 3: Implement the smallest authenticated fallback**

```python
class OptionSlamEvrProvider:
    def __init__(self, session, clock=..., username=None, password=None):
        self._session = session
        self._clock = clock
        self._username = username
        self._password = password
        self._authenticated = False

    def fetch_public_evr(self, symbol: str) -> EvrResult:
        public_result = self._fetch_symbol(symbol)
        if public_result.status == "available":
            return public_result
        if public_result.status != "authentication_required":
            return public_result
        if not self._username or not self._password:
            return public_result
        if not self._login():
            return EvrResult(None, public_result.source_url, "login_failed", public_result.collected_at)
        return self._fetch_symbol(symbol)
```

Keep the login contract focused: fetch any required login page first if CSRF is needed, submit credentials once with the existing `requests.Session`, and reuse the authenticated session across later symbols. Do not add broad retries, browser automation, or alternate scraping paths.

- [ ] **Step 4: Run provider and pipeline tests**

Run: `pytest tests/options/test_optionslam_evr.py tests/options/test_options_pipeline.py tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/earnings_export/sources/optionslam_evr.py tests/options/test_optionslam_evr.py tests/options/test_options_pipeline.py tests/test_cli.py && git commit -m "feat: add optionslam authenticated EVR fallback"`

### Task 3: Wire OptionSlam Credentials Through CLI Execution

**Files:**
- Modify: `src/earnings_export/cli.py`
- Modify: `tests/test_options_e2e.py`
- Modify: `docs/automation/local-credentials.md`
- Modify: `docs/automation/weekly-earnings-options.md`

**Interfaces:**
- Consumes: `AnalysisSettings.optionslam_username`, `AnalysisSettings.optionslam_password`
- Modifies: `run_analyze_next_week_options(today: date | None = None, cwd: Path | None = None) -> OptionsArtifactPaths`
- Produces: documentation that names `OPTIONSLAM_USERNAME` and `OPTIONSLAM_PASSWORD`

- [ ] **Step 1: Write the failing wiring tests**

```python
def test_run_analyze_next_week_options_passes_local_optionslam_credentials(monkeypatch, tmp_path):
    observed = {}

    class RecordingEvrProvider:
        def __init__(self, session, clock=lambda: FIXED_TIME, username=None, password=None):
            observed["username"] = username
            observed["password"] = password

    monkeypatch.setattr("earnings_export.cli.OptionSlamEvrProvider", RecordingEvrProvider)
    monkeypatch.setenv("OPTIONSLAM_USERNAME", "env-user")
    monkeypatch.setenv("OPTIONSLAM_PASSWORD", "env-pass")

    _run_options_command(monkeypatch, tmp_path, "alpha_liquid_call_put.json")

    assert observed == {"username": "env-user", "password": "env-pass"}
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `pytest tests/test_options_e2e.py::test_run_analyze_next_week_options_passes_local_optionslam_credentials -v`

Expected: FAIL because `OptionSlamEvrProvider` is currently created without credential arguments.

- [ ] **Step 3: Implement settings-to-provider wiring and docs**

```python
result = analyze_events(
    filtered_events,
    providers,
    settings,
    run_at,
    OptionSlamEvrProvider(
        session,
        username=settings.optionslam_username,
        password=settings.optionslam_password,
    ),
)
```

Update both automation docs to state that `OPTIONSLAM_USERNAME` and `OPTIONSLAM_PASSWORD` may be stored in the same local owner-only credentials file, still with environment precedence, and that they must never be committed.

- [ ] **Step 4: Run focused and full tests**

Run: `pytest tests/test_options_e2e.py tests/test_credentials.py tests/options/test_optionslam_evr.py -q && pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/earnings_export/cli.py tests/test_options_e2e.py docs/automation/local-credentials.md docs/automation/weekly-earnings-options.md && git commit -m "feat: wire local optionslam credentials into analysis"`

### Task 4: Add A Durable NTES Investigation Harness

**Files:**
- Create: `tests/options/test_optionslam_investigation.py`
- Create: `tests/fixtures/optionslam_evr/ntes_failure_response.html` or a sanitized helper fixture that reproduces the class of failure
- Create: `scripts/optionslam_ntes_diagnose.py`
- Modify: `src/earnings_export/sources/optionslam_evr.py`

**Interfaces:**
- Produces: `diagnose_optionslam_response(html: str, status_code: int, symbol: str, source_url: str, collected_at: datetime) -> EvrResult` or equivalent helper
- Produces: `scripts/optionslam_ntes_diagnose.py` that prints sanitized classification only
- Consumes: existing parser logic and result statuses

- [ ] **Step 1: Write the failing investigation test**

```python
def test_diagnose_membership_or_variant_response_classifies_ntes_failure(load_fixture):
    result = diagnose_optionslam_response(
        load_fixture("optionslam_evr/ntes_failure_response.html"),
        403,
        "NTES",
        "https://www.optionslam.com/ntes/",
        FIXED_TIME,
    )

    assert result.value is None
    assert result.status in {"authentication_required", "request_failed", "not_found"}
```

- [ ] **Step 2: Run the investigation test to verify it fails**

Run: `pytest tests/options/test_optionslam_investigation.py -v`

Expected: FAIL because the investigation helper and fixture do not exist.

- [ ] **Step 3: Implement a durable sanitized investigation path**

```python
def diagnose_optionslam_response(
    html: str,
    status_code: int,
    symbol: str,
    source_url: str,
    collected_at: datetime,
) -> EvrResult:
    parsed = parse_optionslam_evr(html, symbol, source_url, collected_at)
    if parsed.status == "authentication_required":
        return parsed
    if status_code >= 400:
        return EvrResult(None, source_url, "request_failed", collected_at)
    return parsed
```

Add a small script that reads a local HTML file path or fetches one symbol using current local credentials and prints only sanitized diagnostics such as symbol, HTTP status, final URL, and result status. Do not print HTML, cookies, usernames, or passwords.

- [ ] **Step 4: Run focused investigation tests**

Run: `pytest tests/options/test_optionslam_investigation.py tests/options/test_optionslam_evr.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add tests/options/test_optionslam_investigation.py tests/fixtures/optionslam_evr/ntes_failure_response.html scripts/optionslam_ntes_diagnose.py src/earnings_export/sources/optionslam_evr.py && git commit -m "test: add durable optionslam NTES investigation harness"`

## Final Verification

- [ ] Run `pytest -q`.
- [ ] Run `python -m compileall src tests scripts` and expect no syntax errors.
- [ ] Run `PYTHONPATH=src python3 scripts/optionslam_ntes_diagnose.py --fixture tests/fixtures/optionslam_evr/ntes_failure_response.html --symbol NTES` and verify the output contains only sanitized status information.
- [ ] Optionally run `PYTHONPATH=src python3 -m earnings_export analyze-next-week-options` with local credentials configured and verify the generated artifacts contain no credential values.
- [ ] Run `git diff --check` and confirm there are no whitespace errors.
