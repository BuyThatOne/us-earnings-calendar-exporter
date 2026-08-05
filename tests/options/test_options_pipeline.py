from dataclasses import replace
from datetime import date, datetime, timezone

from earnings_export.models import EarningsEvent
from earnings_export.options_config import AnalysisSettings
from earnings_export.options_models import (
    OptionChainSnapshot,
    OptionContract,
    ProviderCapability,
)
from earnings_export.options_pipeline import analyze_events
from earnings_export.sources.options_provider import ProviderResult
from earnings_export.sources.optionslam_evr import EvrResult


FIXED_TIME = datetime(2026, 7, 31, 14, 30, tzinfo=timezone.utc)
EARNINGS_DATE = date(2026, 8, 6)


def _event(ticker: str = "AAPL") -> EarningsEvent:
    return EarningsEvent(
        earnings_date=EARNINGS_DATE,
        ticker=ticker,
        company_name="Apple",
        earnings_time="AMC",
        exchange="NASDAQ",
        source_calendar_url="https://calendar.test/aapl",
    )


def _current_result(provider: str) -> ProviderResult:
    capability = ProviderCapability(provider, True, "available")
    expiration = date(2026, 8, 7)
    contracts = (
        OptionContract(
            option_symbol=f"{provider}-call",
            option_type="call",
            expiration=expiration,
            strike=100.0,
            bid=3.8,
            ask=4.2,
        ),
        OptionContract(
            option_symbol=f"{provider}-put",
            option_type="put",
            expiration=expiration,
            strike=100.0,
            bid=3.8,
            ask=4.2,
        ),
    )
    return ProviderResult(
        snapshot=OptionChainSnapshot(
            symbol="AAPL",
            collected_at=FIXED_TIME,
            provider=provider,
            provider_capabilities=(capability,),
            underlying_price=100.0,
            contracts=contracts,
        ),
        capability=capability,
    )


class RecordingProvider:
    def __init__(self, name: str, current_result: ProviderResult) -> None:
        self.name = name
        self.current_result = current_result
        self.current_calls: list[str] = []
        self.historical_calls: list[tuple[str, date]] = []

    def fetch_current_chain(self, symbol: str) -> ProviderResult:
        self.current_calls.append(symbol)
        return self.current_result

    def fetch_historical_chain(self, symbol: str, as_of: date) -> ProviderResult:
        self.historical_calls.append((symbol, as_of))
        return ProviderResult.unavailable(self.name, "entitlement_unavailable")


class RecordingEvrProvider:
    name = "optionslam"

    def __init__(self, result: EvrResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def fetch_public_evr(self, symbol: str) -> EvrResult:
        self.calls.append(symbol)
        return self.result


class MalformedCurrentProvider(RecordingProvider):
    def fetch_current_chain(self, symbol: str) -> ProviderResult:
        self.current_calls.append(symbol)
        raise ValueError("malformed provider response")


def _settings(tmp_path) -> AnalysisSettings:
    return AnalysisSettings(
        output_dir=tmp_path,
        spread_limit=0.10,
        provider_order=("alpha_vantage", "yahoo"),
        alpha_vantage_api_key=None,
    )


def _settings_with_browser(tmp_path) -> AnalysisSettings:
    return replace(
        _settings(tmp_path),
        provider_order=("alpha_vantage", "yahoo", "yahoo_browser"),
    )


def test_analyze_events_uses_alpha_current_chain_without_calling_yahoo(tmp_path):
    alpha = RecordingProvider("alpha_vantage", _current_result("alpha_vantage"))
    yahoo = RecordingProvider("yahoo", _current_result("yahoo"))

    result = analyze_events([_event()], [yahoo, alpha], _settings(tmp_path), FIXED_TIME)

    assert alpha.current_calls == ["AAPL"]
    assert yahoo.current_calls == []
    assert alpha.historical_calls == [("AAPL", FIXED_TIME.date())]
    assert yahoo.historical_calls == []
    assert result.snapshots[0].provider == "alpha_vantage"
    assert result.candidates
    assert any("historical_iv_unavailable" in warning for warning in result.candidates[0].warnings)
    assert any("optionslam_evr_unavailable" in warning for warning in result.candidates[0].warnings)


def test_analyze_events_adds_yahoo_spot_without_replacing_alpha_chain(tmp_path):
    alpha_result = _current_result("alpha_vantage")
    alpha = RecordingProvider(
        "alpha_vantage",
        replace(alpha_result, snapshot=replace(alpha_result.snapshot, underlying_price=None)),
    )
    yahoo = RecordingProvider("yahoo", _current_result("yahoo"))

    result = analyze_events([_event()], [alpha, yahoo], _settings(tmp_path), FIXED_TIME)

    assert yahoo.current_calls == ["AAPL"]
    assert result.candidates
    assert all(leg.option_symbol.startswith("alpha_vantage-") for leg in result.candidates[0].legs)
    assert result.snapshots[0].provider == "alpha_vantage"
    assert result.snapshots[0].underlying_price == 100.0
    assert result.snapshots[0].provider_capabilities[-1].supported_fields == (
        "underlying_price",
    )
    assert "underlying_price_from_yahoo" in result.snapshots[0].data_quality_flags


def test_analyze_events_falls_back_to_yahoo_only_for_current_chain(tmp_path):
    alpha = RecordingProvider(
        "alpha_vantage",
        ProviderResult.unavailable("alpha_vantage", "missing_api_key"),
    )
    yahoo = RecordingProvider("yahoo", _current_result("yahoo"))

    result = analyze_events([_event()], [yahoo, alpha], _settings(tmp_path), FIXED_TIME)

    assert alpha.current_calls == ["AAPL"]
    assert yahoo.current_calls == ["AAPL"]
    assert alpha.historical_calls == [("AAPL", FIXED_TIME.date())]
    assert yahoo.historical_calls == []
    assert result.snapshots[0].provider == "yahoo"
    assert [capability.provider for capability in result.capabilities] == [
        "alpha_vantage",
        "yahoo",
        "alpha_vantage",
        "optionslam",
    ]


def test_analyze_events_falls_back_to_browser_after_alpha_and_yahoo_fail(tmp_path):
    alpha = RecordingProvider(
        "alpha_vantage",
        ProviderResult.unavailable("alpha_vantage", "missing_api_key"),
    )
    yahoo = RecordingProvider(
        "yahoo",
        ProviderResult.unavailable("yahoo", "request_failed"),
    )
    browser = RecordingProvider("yahoo_browser", _current_result("yahoo_browser"))

    result = analyze_events(
        [_event()], [browser, yahoo, alpha], _settings_with_browser(tmp_path), FIXED_TIME,
    )

    assert alpha.current_calls == ["AAPL"]
    assert yahoo.current_calls == ["AAPL"]
    assert browser.current_calls == ["AAPL"]
    assert alpha.historical_calls == [("AAPL", FIXED_TIME.date())]
    assert yahoo.historical_calls == []
    assert browser.historical_calls == []
    assert result.snapshots[0].provider == "yahoo_browser"
    assert [capability.provider for capability in result.capabilities] == [
        "alpha_vantage",
        "yahoo",
        "yahoo_browser",
        "alpha_vantage",
        "optionslam",
    ]


def test_analyze_events_uses_browser_spot_after_yahoo_fails(tmp_path):
    alpha_result = _current_result("alpha_vantage")
    alpha = RecordingProvider(
        "alpha_vantage",
        replace(alpha_result, snapshot=replace(alpha_result.snapshot, underlying_price=None)),
    )
    yahoo = RecordingProvider(
        "yahoo",
        ProviderResult.unavailable("yahoo", "request_failed"),
    )
    browser = RecordingProvider("yahoo_browser", _current_result("yahoo_browser"))

    result = analyze_events(
        [_event()], [alpha, yahoo, browser], _settings_with_browser(tmp_path), FIXED_TIME,
    )

    assert yahoo.current_calls == ["AAPL"]
    assert browser.current_calls == ["AAPL"]
    assert result.snapshots[0].provider == "alpha_vantage"
    assert result.snapshots[0].underlying_price == 100.0
    assert result.snapshots[0].provider_capabilities[-1].provider == "yahoo_browser"
    assert result.capabilities[1].provider == "yahoo"
    assert result.capabilities[1].code == "request_failed"


def test_analyze_events_uses_available_evr_as_optional_context(tmp_path):
    alpha = RecordingProvider("alpha_vantage", _current_result("alpha_vantage"))
    evr = RecordingEvrProvider(
        EvrResult(
            value=6.5,
            source_url="https://www.optionslam.com/aapl/",
            status="available",
            collected_at=FIXED_TIME,
        )
    )

    result = analyze_events(
        [_event()], [alpha], _settings(tmp_path), FIXED_TIME, evr_provider=evr,
    )

    assert evr.calls == ["AAPL"]
    assert result.candidates
    assert "OptionSlam EVR 6.5" in result.candidates[0].rationale
    assert result.capabilities[-1] == ProviderCapability(
        provider="optionslam",
        available=True,
        code="available",
        supported_fields=("evr",),
    )


def test_analyze_events_keeps_login_failed_evr_nonfatal(tmp_path):
    alpha = RecordingProvider("alpha_vantage", _current_result("alpha_vantage"))
    evr = RecordingEvrProvider(
        EvrResult(
            value=None,
            source_url="https://www.optionslam.com/aapl/",
            status="login_failed",
            collected_at=FIXED_TIME,
        )
    )

    result = analyze_events(
        [_event()], [alpha], _settings(tmp_path), FIXED_TIME, evr_provider=evr,
    )

    assert result.candidates
    assert any("optionslam_evr_login_failed" in warning for warning in result.candidates[0].warnings)
    assert result.capabilities[-1] == ProviderCapability(
        provider="optionslam",
        available=False,
        code="login_failed",
        supported_fields=("evr",),
    )


def test_analyze_events_falls_back_when_alpha_reports_capability_without_snapshot(tmp_path):
    alpha = RecordingProvider(
        "alpha_vantage",
        ProviderResult(
            snapshot=None,
            capability=ProviderCapability("alpha_vantage", True, "available"),
        ),
    )
    yahoo = RecordingProvider("yahoo", _current_result("yahoo"))

    result = analyze_events([_event()], [alpha, yahoo], _settings(tmp_path), FIXED_TIME)

    assert yahoo.current_calls == ["AAPL"]
    assert result.snapshots[0].provider == "yahoo"


def test_analyze_events_records_exclusion_when_no_current_chain_is_available(tmp_path):
    alpha = RecordingProvider(
        "alpha_vantage",
        ProviderResult.unavailable("alpha_vantage", "missing_api_key"),
    )
    yahoo = RecordingProvider(
        "yahoo",
        ProviderResult.unavailable("yahoo", "request_failed"),
    )

    result = analyze_events([_event()], [alpha, yahoo], _settings(tmp_path), FIXED_TIME)

    assert result.candidates == ()
    assert result.exclusions == {"missing_current_chain": 1}
    assert result.snapshots == ()


def test_analyze_events_treats_malformed_yahoo_response_as_nonfatal(tmp_path):
    alpha = RecordingProvider(
        "alpha_vantage",
        ProviderResult.unavailable("alpha_vantage", "missing_api_key"),
    )
    yahoo = MalformedCurrentProvider(
        "yahoo",
        ProviderResult.unavailable("yahoo", "invalid_response"),
    )

    result = analyze_events([_event()], [alpha, yahoo], _settings(tmp_path), FIXED_TIME)

    assert result.candidates == ()
    assert result.exclusions == {"missing_current_chain": 1}
    assert result.capabilities[1].provider == "yahoo"
    assert result.capabilities[1].code == "invalid_response"
