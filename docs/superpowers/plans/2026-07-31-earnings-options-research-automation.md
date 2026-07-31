# Earnings Options Research Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 10:00 ET weekly Codex-orchestrated CLI that analyzes next week's large-cap US earnings events and writes research-only options recommendations as Markdown and JSON.

**Architecture:** Keep data acquisition deterministic inside Python and let the Codex cron prompt only invoke the CLI and summarize its artifacts. Add provider interfaces for Alpha Vantage, Yahoo fallback, and public OptionSlam EVR enrichment; normalize all inputs before historical-event analysis, liquidity filtering, strategy ranking, and artifact writing.

**Tech Stack:** Python 3.10+, `requests`, `pytest`, standard-library `dataclasses`, `json`, `pathlib`, and the existing NASDAQ/Finviz earnings-universe pipeline.

## Global Constraints

- Preserve `python -m earnings_export export-next-week` behavior and its existing CSV output.
- The analysis command is `python -m earnings_export analyze-next-week-options`.
- Run the Codex project cron at 10:00 `America/New_York` every Friday; do not schedule 09:30 and sleep.
- Use `ALPHAVANTAGE_API_KEY` only from the local environment; never serialize, log, prompt, or commit its value.
- Alpha Vantage capability loss is a partial-data result, not a fatal parser error.
- Yahoo is a current-chain-only fallback and must not be used for historical option data.
- Read OptionSlam EVR only from publicly accessible, unauthenticated pages. Never register, authenticate, or bypass access controls.
- Selected contracts qualify only when `bid > 0`, `ask > 0`, and `(ask - bid) / ((ask + bid) / 2) <= 0.10`.
- Omit every non-qualifying symbol from candidate lists; successful zero-candidate runs still write Markdown and JSON artifacts.
- Rank defined-risk neutral structures ahead of otherwise comparable undefined-risk structures. Every result uses `execution_status: "research_only"`.
- Normal test runs use recorded fixtures and never perform live provider calls.

---

## File Structure

| Path | Responsibility |
|---|---|
| `src/earnings_export/options_models.py` | Immutable normalized option, history, strategy, capability, and run-result models. |
| `src/earnings_export/options_config.py` | Environment-backed analysis settings and provider ordering. |
| `src/earnings_export/sources/options_provider.py` | Provider protocol plus aggregate source result types. |
| `src/earnings_export/sources/alpha_vantage_options.py` | Alpha Vantage HTTP transport and payload normalization. |
| `src/earnings_export/sources/yahoo_options.py` | Current-chain-only Yahoo fallback adapter. |
| `src/earnings_export/sources/optionslam_evr.py` | Public-page EVR URL building and parser. |
| `src/earnings_export/options_history.py` | Historical post-earnings move and IV comparison calculations. |
| `src/earnings_export/options_strategy.py` | Spread gate, implied move, strategy construction, and ranking. |
| `src/earnings_export/options_pipeline.py` | Provider capability resolution and end-to-end symbol analysis. |
| `src/earnings_export/export/options_report.py` | Dated Markdown, JSON, and snapshot artifact writing. |
| `src/earnings_export/cli.py` | New command and dependency-injectable `run_analyze_next_week_options`. |
| `automation/weekly_earnings_options_prompt.md` | Versioned Codex prompt that invokes the CLI and summarizes artifacts. |
| `docs/automation/weekly-earnings-options.md` | Exact Codex cron configuration and operational runbook. |
| `tests/options/` | Fixtures and unit tests for the new isolated units. |
| `tests/test_cli.py` | Backward-compatible command parsing and new CLI orchestration tests. |

## Task 1: Define Options Models And Configuration

**Files:**
- Create: `src/earnings_export/options_models.py`
- Create: `src/earnings_export/options_config.py`
- Create: `tests/options/test_models_and_config.py`

**Interfaces:**
- Consumes: standard-library `date`, `datetime`, `dataclass`, `Path`, and `os.environ`.
- Produces: `OptionContract`, `OptionChainSnapshot`, `EarningsMoveHistory`, `StrategyCandidate`, `ProviderCapability`, `AnalysisSettings`, and `load_analysis_settings(environ: Mapping[str, str], cwd: Path) -> AnalysisSettings`.

- [ ] **Step 1: Write failing model and configuration tests**

```python
from datetime import date
from pathlib import Path

from earnings_export.options_config import load_analysis_settings
from earnings_export.options_models import OptionContract, StrategyCandidate


def test_load_analysis_settings_uses_safe_defaults(tmp_path):
    settings = load_analysis_settings({}, tmp_path)

    assert settings.output_dir == tmp_path / "exports/earnings-options"
    assert settings.spread_limit == 0.10
    assert settings.provider_order == ("alpha_vantage", "yahoo")


def test_strategy_candidate_is_always_research_only():
    candidate = StrategyCandidate(
        ticker="AAPL", earnings_date=date(2026, 8, 6), strategy_type="iron_condor",
        defined_risk=True, legs=(), entry_limit=1.25, maximum_loss=375.0,
        implied_move_pct=0.05, historical_median_move_pct=0.04,
        historical_iv_change_pct=None, warnings=(), rationale="fixture",
    )

    assert candidate.execution_status == "research_only"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/options/test_models_and_config.py -v`

Expected: FAIL during collection because `earnings_export.options_config` and `earnings_export.options_models` do not exist.

- [ ] **Step 3: Add immutable models and environment parsing**

```python
@dataclass(frozen=True)
class AnalysisSettings:
    output_dir: Path
    spread_limit: float
    provider_order: tuple[str, ...]
    alpha_vantage_api_key: str | None


def load_analysis_settings(environ: Mapping[str, str], cwd: Path) -> AnalysisSettings:
    return AnalysisSettings(
        output_dir=cwd / environ.get("EARNINGS_OPTIONS_OUTPUT_DIR", "exports/earnings-options"),
        spread_limit=float(environ.get("EARNINGS_OPTIONS_MAX_SPREAD_PCT", "0.10")),
        provider_order=("alpha_vantage", "yahoo"),
        alpha_vantage_api_key=environ.get("ALPHAVANTAGE_API_KEY") or None,
    )


@dataclass(frozen=True)
class StrategyCandidate:
    ticker: str
    earnings_date: date
    strategy_type: str
    defined_risk: bool
    legs: tuple[OptionContract, ...]
    entry_limit: float
    maximum_loss: float | None
    implied_move_pct: float
    historical_median_move_pct: float | None
    historical_iv_change_pct: float | None
    warnings: tuple[str, ...]
    rationale: str
    execution_status: str = "research_only"
```

Validate `0 < spread_limit <= 1`; raise `ValueError` for invalid values. Model provider capabilities and data-quality flags as explicit fields rather than untyped dictionaries.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/options/test_models_and_config.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the isolated foundation**

```bash
git add src/earnings_export/options_models.py src/earnings_export/options_config.py tests/options/test_models_and_config.py
git commit -m "feat: add options analysis models and configuration"
```

## Task 2: Add Provider Protocol, Alpha Vantage, And Yahoo Fallback

**Files:**
- Create: `src/earnings_export/sources/options_provider.py`
- Create: `src/earnings_export/sources/alpha_vantage_options.py`
- Create: `src/earnings_export/sources/yahoo_options.py`
- Create: `tests/fixtures/alpha_vantage/current_options.json`
- Create: `tests/fixtures/alpha_vantage/historical_options.json`
- Create: `tests/fixtures/yahoo_options/current_chain.json`
- Create: `tests/options/test_alpha_vantage_options.py`
- Create: `tests/options/test_yahoo_options.py`

**Interfaces:**
- Consumes: `AnalysisSettings`, `OptionChainSnapshot`, `ProviderCapability`, and a `requests.Session`.
- Produces: `OptionsDataProvider.fetch_current_chain(symbol: str) -> ProviderResult`, `OptionsDataProvider.fetch_historical_chain(symbol: str, as_of: date) -> ProviderResult`, and `ProviderResult(snapshot: OptionChainSnapshot | None, capability: ProviderCapability)`.

- [ ] **Step 1: Write failing parser and fallback tests from fixtures**

```python
def test_alpha_current_chain_normalizes_bid_ask_iv_and_greeks(load_fixture):
    result = parse_alpha_vantage_options(
        load_fixture("alpha_vantage/current_options.json"), symbol="AAPL", collected_at=FIXED_TIME,
    )

    assert result.snapshot.contracts[0].bid == 4.20
    assert result.snapshot.contracts[0].ask == 4.60
    assert result.snapshot.contracts[0].implied_volatility == 0.31
    assert result.capability.available is True


def test_alpha_entitlement_message_becomes_unavailable_capability():
    result = parse_alpha_vantage_error({"Information": "premium endpoint"}, "AAPL", FIXED_TIME)

    assert result.snapshot is None
    assert result.capability.code == "entitlement_unavailable"


def test_yahoo_adapter_rejects_historical_requests():
    provider = YahooOptionsProvider(session=object())

    result = provider.fetch_historical_chain("AAPL", date(2026, 7, 30))

    assert result.capability.code == "unsupported"
```

- [ ] **Step 2: Run source tests to verify they fail**

Run: `pytest tests/options/test_alpha_vantage_options.py tests/options/test_yahoo_options.py -v`

Expected: FAIL because the provider protocol and parser modules do not exist.

- [ ] **Step 3: Implement transport-free parsers, then thin HTTP adapters**

```python
class OptionsDataProvider(Protocol):
    name: str

    def fetch_current_chain(self, symbol: str) -> ProviderResult:
        raise NotImplementedError

    def fetch_historical_chain(self, symbol: str, as_of: date) -> ProviderResult:
        raise NotImplementedError


def parse_alpha_vantage_options(payload: dict, symbol: str, collected_at: datetime) -> ProviderResult:
    if "Information" in payload or "Note" in payload:
        return ProviderResult.unavailable("alpha_vantage", "entitlement_unavailable")
    # Normalize documented contract records into OptionContract instances.


class YahooOptionsProvider:
    name = "yahoo"

    def fetch_historical_chain(self, symbol: str, as_of: date) -> ProviderResult:
        return ProviderResult.unavailable(self.name, "unsupported")
```

Use `session.get(url, params=params, timeout=30)` and inject the session/clock into constructors. Do not call either provider at import time. Alpha requests include the API key only as an HTTP parameter; error objects and URLs written to artifacts must redact it.

- [ ] **Step 4: Run source tests to verify they pass**

Run: `pytest tests/options/test_alpha_vantage_options.py tests/options/test_yahoo_options.py -v`

Expected: PASS with no network traffic.

- [ ] **Step 5: Commit provider adapters**

```bash
git add src/earnings_export/sources tests/fixtures/alpha_vantage tests/fixtures/yahoo_options tests/options/test_alpha_vantage_options.py tests/options/test_yahoo_options.py
git commit -m "feat: add options data provider adapters"
```

## Task 3: Add Public OptionSlam EVR Enrichment

**Files:**
- Create: `src/earnings_export/sources/optionslam_evr.py`
- Create: `tests/fixtures/optionslam_evr/public_page.html`
- Create: `tests/fixtures/optionslam_evr/login_page.html`
- Create: `tests/options/test_optionslam_evr.py`

**Interfaces:**
- Consumes: a ticker, an injected `requests.Session`, and public HTML fixtures.
- Produces: `EvrResult(value: float | None, source_url: str, status: str, collected_at: datetime)` and `fetch_public_evr(symbol: str) -> EvrResult`.

- [ ] **Step 1: Write failing access-boundary and parsing tests**

```python
def test_parse_public_evr_returns_value_and_public_status(load_fixture):
    result = parse_optionslam_evr(
        load_fixture("optionslam_evr/public_page.html"), "AAPL", "https://www.optionslam.com/aapl/", FIXED_TIME,
    )

    assert result.value == 6.5
    assert result.status == "available"


def test_parse_login_page_never_attempts_authentication(load_fixture):
    result = parse_optionslam_evr(
        load_fixture("optionslam_evr/login_page.html"), "AAPL", "https://www.optionslam.com/aapl/", FIXED_TIME,
    )

    assert result.value is None
    assert result.status == "authentication_required"
```

- [ ] **Step 2: Run the EVR test to verify it fails**

Run: `pytest tests/options/test_optionslam_evr.py -v`

Expected: FAIL because `optionslam_evr` does not exist.

- [ ] **Step 3: Implement a single-request public parser**

```python
def parse_optionslam_evr(html: str, symbol: str, source_url: str, collected_at: datetime) -> EvrResult:
    if "sign in" in html.lower() or "membership" in html.lower():
        return EvrResult(None, source_url, "authentication_required", collected_at)
    match = re.search(r"EVR[^0-9]*([0-9]+(?:\.[0-9]+)?)", html, re.I)
    return EvrResult(float(match.group(1)), source_url, "available", collected_at) if match else EvrResult(None, source_url, "not_found", collected_at)
```

`fetch_public_evr` performs exactly one unauthenticated GET with a normal user agent and `timeout=30`; it returns `request_failed` on transport failure. It must not follow a workflow that creates an account, posts a form, or retries a login page.

- [ ] **Step 4: Run the EVR test to verify it passes**

Run: `pytest tests/options/test_optionslam_evr.py -v`

Expected: PASS.

- [ ] **Step 5: Commit public-only EVR enrichment**

```bash
git add src/earnings_export/sources/optionslam_evr.py tests/fixtures/optionslam_evr tests/options/test_optionslam_evr.py
git commit -m "feat: add public optionslam EVR enrichment"
```

## Task 4: Implement Historical Metrics, Liquidity Gate, And Strategy Ranking

**Files:**
- Create: `src/earnings_export/options_history.py`
- Create: `src/earnings_export/options_strategy.py`
- Create: `tests/options/test_options_history.py`
- Create: `tests/options/test_options_strategy.py`

**Interfaces:**
- Consumes: `EarningsEvent`, daily close data, `OptionChainSnapshot`, `EarningsMoveHistory`, and `AnalysisSettings.spread_limit`.
- Produces: `build_earnings_move_history(events: Sequence[EarningsEvent], closes: Mapping[date, float], iv_changes: Sequence[float], evr: EvrResult) -> EarningsMoveHistory`, `spread_pct(contract: OptionContract) -> float | None`, `build_ranked_candidates(ticker: str, earnings_date: date, snapshot: OptionChainSnapshot, history: EarningsMoveHistory, spread_limit: float) -> list[StrategyCandidate]`.

- [ ] **Step 1: Write failing deterministic metric and ranking tests**

```python
def test_spread_gate_accepts_ten_percent_and_rejects_wider_contracts():
    assert contract_is_liquid(OptionContract(bid=9.5, ask=10.5), 0.10) is True
    assert contract_is_liquid(OptionContract(bid=9.0, ask=11.0), 0.10) is False


def test_history_calculates_absolute_one_day_post_earnings_moves():
    history = build_earnings_move_history(
        events=[event(date(2026, 5, 1))],
        closes={date(2026, 5, 1): 100.0, date(2026, 5, 4): 106.0},
        iv_changes=[], evr=missing_evr(),
    )

    assert history.absolute_moves_pct == (0.06,)
    assert history.median_move_pct == 0.06


def test_defined_risk_candidate_ranks_before_undefined_risk_when_scores_match():
    candidates = build_ranked_candidates(equal_score_chain, equal_history, spread_limit=0.10)

    assert candidates[0].defined_risk is True
    assert candidates[0].strategy_type == "iron_condor"
```

- [ ] **Step 2: Run analysis tests to verify they fail**

Run: `pytest tests/options/test_options_history.py tests/options/test_options_strategy.py -v`

Expected: FAIL because the historical and strategy modules do not exist.

- [ ] **Step 3: Implement pure calculations and deterministic ranking**

```python
def spread_pct(contract: OptionContract) -> float | None:
    if contract.bid <= 0 or contract.ask <= 0:
        return None
    midpoint = (contract.bid + contract.ask) / 2
    return (contract.ask - contract.bid) / midpoint


def contract_is_liquid(contract: OptionContract, spread_limit: float) -> bool:
    spread = spread_pct(contract)
    return spread is not None and spread <= spread_limit


def rank_key(candidate: StrategyCandidate) -> tuple[float, int, str]:
    return (-candidate.score, 0 if candidate.defined_risk else 1, candidate.strategy_type)
```

Calculate an implied move from the selected near-the-money call and put midpoints divided by spot. Generate only strategies whose every leg passes `contract_is_liquid`. Include iron condor, iron butterfly, calendar, straddle, and strangle builders; append an undefined-risk warning to straddles and strangles. Use median, mean, and maximum historical moves as labeled evidence, not as a claim of expected profit.

- [ ] **Step 4: Run analysis tests to verify they pass**

Run: `pytest tests/options/test_options_history.py tests/options/test_options_strategy.py -v`

Expected: PASS.

- [ ] **Step 5: Commit analysis behavior**

```bash
git add src/earnings_export/options_history.py src/earnings_export/options_strategy.py tests/options/test_options_history.py tests/options/test_options_strategy.py
git commit -m "feat: add earnings options analysis and ranking"
```

## Task 5: Write Dated Markdown, JSON, And Snapshot Artifacts

**Files:**
- Create: `src/earnings_export/export/options_report.py`
- Create: `tests/options/test_options_report.py`

**Interfaces:**
- Consumes: `AnalysisRunResult(run_at: datetime, candidates: tuple[StrategyCandidate, ...], exclusions: Mapping[str, int], capabilities: Sequence[ProviderCapability], snapshots: Sequence[OptionChainSnapshot])`.
- Produces: `write_options_artifacts(result: AnalysisRunResult, output_dir: Path) -> OptionsArtifactPaths` with `markdown_path`, `json_path`, and `snapshots_path`.

- [ ] **Step 1: Write failing artifact and credential-redaction tests**

```python
def test_empty_run_writes_markdown_and_json_with_no_candidates(tmp_path):
    paths = write_options_artifacts(empty_run(FIXED_TIME), tmp_path)

    assert paths.markdown_path.read_text().find("No eligible candidate was found") >= 0
    assert json.loads(paths.json_path.read_text())["candidates"] == []


def test_artifacts_never_contain_api_key(tmp_path):
    paths = write_options_artifacts(run_with_provider_detail("key=secret-value"), tmp_path)

    assert "secret-value" not in paths.markdown_path.read_text()
    assert "secret-value" not in paths.json_path.read_text()
```

- [ ] **Step 2: Run artifact tests to verify they fail**

Run: `pytest tests/options/test_options_report.py -v`

Expected: FAIL because `options_report` does not exist.

- [ ] **Step 3: Implement schema-versioned atomic artifact writing**

```python
def build_run_dir(output_dir: Path, run_at: datetime) -> Path:
    return output_dir / run_at.date().isoformat()


def write_options_artifacts(result: AnalysisRunResult, output_dir: Path) -> OptionsArtifactPaths:
    run_dir = build_run_dir(output_dir, result.run_at)
    run_dir.mkdir(parents=True, exist_ok=True)
    # Serialize dataclasses through explicit dictionaries; redact query-string API keys.
    return OptionsArtifactPaths(markdown_path, json_path, snapshots_path)
```

Write `earnings_options_research.md`, `earnings_options_order_intents.json`, and `option_chain_snapshots.json` under the dated directory. JSON must include `schema_version`, `execution_status`, provider provenance, capability status, warnings, exclusions, and candidates. Markdown must contain a provider capability table and an explicit no-candidate sentence.

- [ ] **Step 4: Run artifact tests to verify they pass**

Run: `pytest tests/options/test_options_report.py -v`

Expected: PASS.

- [ ] **Step 5: Commit artifact generation**

```bash
git add src/earnings_export/export/options_report.py tests/options/test_options_report.py
git commit -m "feat: write earnings options research artifacts"
```

## Task 6: Wire The Options Pipeline And CLI Without Regressing CSV Export

**Files:**
- Create: `src/earnings_export/options_pipeline.py`
- Modify: `src/earnings_export/cli.py`
- Modify: `tests/test_cli.py`
- Create: `tests/options/test_options_pipeline.py`

**Interfaces:**
- Consumes: `collect_events_for_week`, `lookup_market_caps_for_events`, `get_next_week_window`, `AnalysisSettings`, providers, and `write_options_artifacts`.
- Produces: `analyze_events(events: Sequence[EarningsEvent], providers: Sequence[OptionsDataProvider], settings: AnalysisSettings, run_at: datetime) -> AnalysisRunResult` and `run_analyze_next_week_options(today: date | None = None, cwd: Path | None = None) -> OptionsArtifactPaths`.

- [ ] **Step 1: Write failing end-to-end orchestration and command tests**

```python
def test_main_dispatches_options_command(monkeypatch):
    monkeypatch.setattr("earnings_export.cli.run_analyze_next_week_options", lambda: "report-paths")

    assert main(["analyze-next-week-options"]) == 0


def test_options_run_succeeds_with_empty_candidate_result(monkeypatch, tmp_path):
    monkeypatch.setattr("earnings_export.cli.collect_events_for_week", lambda *args: [large_cap_event()])
    monkeypatch.setattr("earnings_export.cli.lookup_market_caps_for_events", lambda *args: {"AAPL": 1_000_000_000_000})
    monkeypatch.setattr("earnings_export.cli.analyze_events", lambda *args, **kwargs: empty_run(FIXED_TIME))

    paths = run_analyze_next_week_options(today=date(2026, 7, 31), cwd=tmp_path)

    assert paths.json_path.exists()


def test_existing_export_command_remains_supported(monkeypatch):
    monkeypatch.setattr("earnings_export.cli.run_export_next_week", lambda: "out.csv")

    assert main(["export-next-week"]) == 0
```

- [ ] **Step 2: Run pipeline and CLI tests to verify they fail**

Run: `pytest tests/options/test_options_pipeline.py tests/test_cli.py -v`

Expected: FAIL because `analyze_events` and `run_analyze_next_week_options` do not exist, while existing export tests still pass.

- [ ] **Step 3: Implement provider selection and command dispatch**

```python
def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["export-next-week"]:
        print(run_export_next_week())
        return 0
    if argv == ["analyze-next-week-options"]:
        paths = run_analyze_next_week_options()
        print(paths.markdown_path)
        print(paths.json_path)
        return 0
    raise SystemExit("Usage: python -m earnings_export {export-next-week|analyze-next-week-options}")
```

The pipeline reuses the existing earnings collection and market-cap lookup, applies the same 50 billion USD filter before invoking options providers, tries Alpha Vantage before Yahoo for current chains, and calls Yahoo only when Alpha's current-chain capability is unavailable. It never treats unavailable historical IV or EVR as a fatal error. It delegates all artifact writing to `write_options_artifacts`.

- [ ] **Step 4: Run the full project test suite**

Run: `pytest -q`

Expected: PASS, including existing CSV-export tests and all new fixture-backed options tests.

- [ ] **Step 5: Commit integration**

```bash
git add src/earnings_export/options_pipeline.py src/earnings_export/cli.py tests/test_cli.py tests/options/test_options_pipeline.py
git commit -m "feat: add weekly options research CLI"
```

## Task 7: Version The Codex Prompt And Configure The Weekly Automation

**Files:**
- Create: `automation/weekly_earnings_options_prompt.md`
- Create: `docs/automation/weekly-earnings-options.md`
- Create: `tests/test_automation_docs.py`

**Interfaces:**
- Consumes: the installed project CLI and artifacts emitted by `run_analyze_next_week_options`.
- Produces: a prompt file and runbook specifying project cron `0 10 * * 5` with timezone `America/New_York`.

- [ ] **Step 1: Write failing documentation-contract tests**

```python
def test_weekly_prompt_invokes_the_options_cli_and_never_places_orders():
    prompt = Path("automation/weekly_earnings_options_prompt.md").read_text()

    assert "python -m earnings_export analyze-next-week-options" in prompt
    assert "Do not submit or simulate an order" in prompt


def test_runbook_uses_friday_ten_am_new_york_schedule():
    runbook = Path("docs/automation/weekly-earnings-options.md").read_text()

    assert "0 10 * * 5" in runbook
    assert "America/New_York" in runbook
```

- [ ] **Step 2: Run documentation tests to verify they fail**

Run: `pytest tests/test_automation_docs.py -v`

Expected: FAIL because the prompt and runbook do not exist.

- [ ] **Step 3: Add the prompt, runbook, and Codex automation**

```markdown
Run `python -m earnings_export analyze-next-week-options` from the project root.
Read the generated Markdown and JSON artifacts. Summarize only eligible candidates,
data limitations, and research rationale. Do not submit or simulate an order. If the
candidate list is empty, state that no eligible candidate was found.
```

The runbook must include the exact cron expression `0 10 * * 5`, timezone `America/New_York`, project working directory, required `ALPHAVANTAGE_API_KEY` setup, expected artifact paths, failure behavior, and how to disable the automation. Use the Codex automation tool after code and tests pass to create a project-level cron job with this prompt; verify the resulting schedule and project association through the tool response.

- [ ] **Step 4: Verify docs and the full suite**

Run: `pytest -q`

Expected: PASS.

Verify: inspect the Codex automation tool response and confirm `kind: cron`, expression `0 10 * * 5`, timezone `America/New_York`, and the intended project ID.

- [ ] **Step 5: Commit automation assets**

```bash
git add automation/weekly_earnings_options_prompt.md docs/automation/weekly-earnings-options.md tests/test_automation_docs.py
git commit -m "docs: add weekly Codex options automation"
```

## Final Verification

- [ ] Run `pytest -q` and record the exact passing count.
- [ ] Run `python -m earnings_export export-next-week` with fixture-mocked dependencies to confirm existing behavior is unchanged.
- [ ] Run `python -m earnings_export analyze-next-week-options` with fixture-mocked providers and inspect all three artifacts.
- [ ] Confirm JSON and Markdown contain no API key value, no `execution_status` other than `research_only`, and an explicit no-candidate response for an empty run.
- [ ] Confirm Codex cron is configured for 10:00 Friday in `America/New_York` and invokes the versioned prompt.
