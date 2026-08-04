from datetime import date, datetime

import pytest

import earnings_export.options_config as options_config
from earnings_export.options_config import load_analysis_settings
from earnings_export.options_models import (
    EarningsMoveHistory,
    OptionChainSnapshot,
    OptionContract,
    ProviderCapability,
    StrategyCandidate,
)


@pytest.fixture(autouse=True)
def isolate_local_credentials_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        options_config,
        "DEFAULT_CREDENTIALS_PATH",
        tmp_path / "missing-credentials.env",
    )


def test_load_analysis_settings_uses_safe_defaults(tmp_path):
    settings = load_analysis_settings({}, tmp_path)

    assert settings.output_dir == tmp_path / "exports/earnings-options"
    assert settings.spread_limit == 0.10
    assert settings.provider_order == ("alpha_vantage", "yahoo")
    assert settings.alpha_vantage_api_key is None


def test_load_analysis_settings_reads_environment_values(tmp_path):
    settings = load_analysis_settings(
        {
            "EARNINGS_OPTIONS_OUTPUT_DIR": "custom-output",
            "EARNINGS_OPTIONS_MAX_SPREAD_PCT": "0.25",
            "ALPHAVANTAGE_API_KEY": "secret",
        },
        tmp_path,
    )

    assert settings.output_dir == tmp_path / "custom-output"
    assert settings.spread_limit == 0.25
    assert settings.alpha_vantage_api_key == "secret"


def test_load_analysis_settings_reads_owner_only_credentials_file(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    credentials.chmod(0o600)
    monkeypatch.setattr(options_config, "DEFAULT_CREDENTIALS_PATH", credentials)

    settings = load_analysis_settings({}, tmp_path)

    assert settings.alpha_vantage_api_key == "file-key"


@pytest.mark.parametrize("value", ("0", "-0.1", "1.01"))
def test_load_analysis_settings_rejects_invalid_spread_limit(tmp_path, value):
    with pytest.raises(ValueError, match="spread_limit"):
        load_analysis_settings({"EARNINGS_OPTIONS_MAX_SPREAD_PCT": value}, tmp_path)


def test_strategy_candidate_is_always_research_only():
    candidate = StrategyCandidate(
        ticker="AAPL",
        earnings_date=date(2026, 8, 6),
        strategy_type="iron_condor",
        defined_risk=True,
        legs=(),
        entry_limit=1.25,
        maximum_loss=375.0,
        implied_move_pct=0.05,
        historical_median_move_pct=0.04,
        historical_iv_change_pct=None,
        warnings=(),
        rationale="fixture",
    )

    assert candidate.execution_status == "research_only"


def test_normalized_models_store_capabilities_and_quality_flags_explicitly():
    contract = OptionContract(
        option_symbol="AAPL260806C00200000",
        option_type="call",
        expiration=date(2026, 8, 6),
        strike=200.0,
        bid=4.2,
        ask=4.6,
        midpoint=4.4,
        bid_ask_spread_pct=0.090909,
    )
    capability = ProviderCapability(
        provider="alpha_vantage",
        available=True,
        code="available",
        supported_fields=("current_chain", "greeks"),
    )
    snapshot = OptionChainSnapshot(
        symbol="AAPL",
        collected_at=datetime(2026, 7, 31),
        provider="alpha_vantage",
        provider_capabilities=(capability,),
        underlying_price=198.0,
        contracts=(contract,),
        data_quality_flags=("quote_timestamp_missing",),
    )
    history = EarningsMoveHistory(
        historical_earnings_events=(date(2026, 5, 1),),
        one_day_post_earnings_moves=(0.04,),
        absolute_move_mean=0.04,
        absolute_move_median=0.04,
        absolute_move_max=0.04,
        historical_iv_observations=None,
        optionslam_evr=None,
        source_provenance=("alpha_vantage",),
        data_quality_flags=("historical_iv_unavailable",),
    )

    assert snapshot.provider_capabilities[0].supported_fields == ("current_chain", "greeks")
    assert snapshot.data_quality_flags == ("quote_timestamp_missing",)
    assert history.data_quality_flags == ("historical_iv_unavailable",)
