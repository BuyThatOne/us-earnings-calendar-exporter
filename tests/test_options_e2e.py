from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import earnings_export.options_config as options_config
from earnings_export.cli import main
from earnings_export.sources.optionslam_evr import EvrResult
from earnings_export.sources.alpha_vantage_options import ALPHA_VANTAGE_URL
from earnings_export.sources.optionslam_evr import OPTIONSLAM_URL
from earnings_export.sources.yahoo_options import YAHOO_OPTIONS_URL


FIXTURES = Path(__file__).parent / "fixtures"
FIXED_RUN_AT = datetime(2026, 7, 31, 14, 30, tzinfo=timezone.utc)
RUN_DATE = FIXED_RUN_AT.date()
FIXTURE_API_KEY = "fixture-api-key"


def _json_fixture(name: str) -> dict:
    return json.loads((FIXTURES / "e2e" / name).read_text())


class FixtureResponse:
    def __init__(self, *, payload: dict | None = None, text: str | None = None) -> None:
        self._payload = payload
        self.text = text or ""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        assert self._payload is not None
        return self._payload


class FixtureSession:
    def __init__(self, alpha_current_fixture: str) -> None:
        self._alpha_current = _json_fixture(alpha_current_fixture)
        self._alpha_history = json.loads(
            (FIXTURES / "alpha_vantage" / "rate_limit_options.json").read_text()
        )
        self._nasdaq_upcoming = _json_fixture("nasdaq_aapl_upcoming.json")
        self._nasdaq_empty = _json_fixture("nasdaq_empty_day.json")
        self._yahoo_chain = json.loads(
            (FIXTURES / "yahoo_options" / "current_chain.json").read_text()
        )
        self._optionslam_membership = (
            FIXTURES / "optionslam_evr" / "membership_response.html"
        ).read_text()

    def get(self, url: str, params=None, **_kwargs) -> FixtureResponse:
        if url.startswith("https://api.nasdaq.com/api/calendar/earnings?"):
            payload = self._nasdaq_upcoming if url.endswith("date=2026-08-03") else self._nasdaq_empty
            return FixtureResponse(payload=payload)
        if url == ALPHA_VANTAGE_URL:
            if params["function"] == "REALTIME_OPTIONS":
                return FixtureResponse(payload=self._alpha_current)
            if params["function"] == "HISTORICAL_OPTIONS":
                return FixtureResponse(payload=self._alpha_history)
        if url == YAHOO_OPTIONS_URL.format(symbol="AAPL"):
            return FixtureResponse(payload=self._yahoo_chain)
        if url == OPTIONSLAM_URL.format(symbol="AAPL"):
            return FixtureResponse(text=self._optionslam_membership)
        raise AssertionError(f"Unexpected network request: {url}")


class FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return RUN_DATE


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None) -> datetime:
        return FIXED_RUN_AT if tz is not None else FIXED_RUN_AT.replace(tzinfo=None)


def _run_options_command(monkeypatch, tmp_path: Path, alpha_current_fixture: str) -> Path:
    monkeypatch.setattr(
        options_config,
        "DEFAULT_CREDENTIALS_PATH",
        tmp_path / "missing-credentials.env",
    )
    session = FixtureSession(alpha_current_fixture)
    output_dir = tmp_path / "exports" / "earnings-options"
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", FIXTURE_API_KEY)
    monkeypatch.setenv("EARNINGS_OPTIONS_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("EARNINGS_OPTIONS_MAX_SPREAD_PCT", "0.10")
    monkeypatch.setattr("earnings_export.cli.requests.Session", lambda: session)
    monkeypatch.setattr("earnings_export.cli.date", FixedDate)
    monkeypatch.setattr("earnings_export.cli.datetime", FixedDateTime)
    monkeypatch.chdir(tmp_path)

    assert main(["analyze-next-week-options"]) == 0

    return output_dir / RUN_DATE.isoformat()


def test_options_command_writes_fixture_backed_research_only_candidate_artifacts(
    monkeypatch, tmp_path,
):
    run_dir = _run_options_command(monkeypatch, tmp_path, "alpha_liquid_call_put.json")
    markdown_path = run_dir / "earnings_options_research.md"
    intents_path = run_dir / "earnings_options_order_intents.json"
    snapshots_path = run_dir / "option_chain_snapshots.json"

    assert markdown_path.is_file()
    assert intents_path.is_file()
    assert snapshots_path.is_file()

    markdown = markdown_path.read_text()
    intents = json.loads(intents_path.read_text())
    snapshots = json.loads(snapshots_path.read_text())
    artifact_text = "\n".join(path.read_text() for path in (markdown_path, intents_path, snapshots_path))

    assert "### AAPL straddle" in markdown
    assert "## Provider Capabilities" in markdown
    assert "alpha_vantage" in markdown
    assert intents["schema_version"] == 1
    assert intents["execution_status"] == "research_only"
    assert intents["candidates"]
    assert intents["candidates"][0]["execution_status"] == "research_only"
    assert {leg["option_type"] for leg in intents["candidates"][0]["legs"]} == {"call", "put"}
    assert any(capability["code"] == "rate_limited" for capability in intents["capabilities"])
    assert any(
        capability["provider"] == "optionslam"
        and capability["code"] == "authentication_required"
        for capability in intents["capabilities"]
    )
    assert any("historical_iv_unavailable" in warning for warning in intents["candidates"][0]["warnings"])
    assert any("optionslam_evr_authentication_required" in warning for warning in intents["candidates"][0]["warnings"])
    assert snapshots["schema_version"] == 1
    assert snapshots["snapshots"][0]["provider"] == "alpha_vantage"
    assert snapshots["snapshots"][0]["underlying_price"] == 210.5
    assert "underlying_price_from_yahoo" in snapshots["snapshots"][0]["data_quality_flags"]
    assert FIXTURE_API_KEY not in artifact_text


def test_run_analyze_next_week_options_passes_local_optionslam_credentials(monkeypatch, tmp_path):
    observed = {}

    class RecordingEvrProvider:
        def __init__(self, session, clock=lambda: FIXED_RUN_AT, username=None, password=None):
            observed["username"] = username
            observed["password"] = password

        def fetch_public_evr(self, symbol):
            return EvrResult(None, f"https://fixture/{symbol}", "unavailable", FIXED_RUN_AT)

    monkeypatch.setattr("earnings_export.cli.OptionSlamEvrProvider", RecordingEvrProvider)
    monkeypatch.setenv("OPTIONSLAM_USERNAME", "env-user")
    monkeypatch.setenv("OPTIONSLAM_PASSWORD", "env-pass")

    _run_options_command(monkeypatch, tmp_path, "alpha_liquid_call_put.json")

    assert observed == {"username": "env-user", "password": "env-pass"}


def test_options_command_writes_empty_artifacts_when_quotes_exceed_spread_limit(
    monkeypatch, tmp_path,
):
    run_dir = _run_options_command(monkeypatch, tmp_path, "alpha_wide_spread_call_put.json")
    markdown_path = run_dir / "earnings_options_research.md"
    intents_path = run_dir / "earnings_options_order_intents.json"
    snapshots_path = run_dir / "option_chain_snapshots.json"

    assert markdown_path.is_file()
    assert intents_path.is_file()
    assert snapshots_path.is_file()
    assert "No eligible candidate was found for this research run." in markdown_path.read_text()
    assert json.loads(intents_path.read_text())["candidates"] == []
    assert json.loads(intents_path.read_text())["exclusions"] == {"missing_liquid_chain": 1}
