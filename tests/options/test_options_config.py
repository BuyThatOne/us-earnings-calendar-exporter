import pytest

import earnings_export.options_config as options_config
from earnings_export.options_config import load_analysis_settings


@pytest.fixture(autouse=True)
def isolate_local_credentials_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        options_config,
        "DEFAULT_CREDENTIALS_PATH",
        tmp_path / "missing-credentials.env",
    )


def test_load_analysis_settings_adds_browser_fallback_and_environment_overrides(tmp_path):
    settings = load_analysis_settings(
        {
            "EARNINGS_OPTIONS_BROWSER_TIMEOUT_SECONDS": "25.0",
            "EARNINGS_OPTIONS_BROWSER_DELAY_SECONDS": "1.5",
        },
        tmp_path,
    )

    assert settings.provider_order == ("alpha_vantage", "yahoo", "yahoo_browser")
    assert settings.browser_timeout_seconds == 25.0
    assert settings.browser_delay_seconds == 1.5


@pytest.mark.parametrize(
    ("name", "value", "message"),
    (
        ("EARNINGS_OPTIONS_BROWSER_TIMEOUT_SECONDS", "0", "browser_timeout_seconds"),
        ("EARNINGS_OPTIONS_BROWSER_TIMEOUT_SECONDS", "nan", "browser_timeout_seconds"),
        ("EARNINGS_OPTIONS_BROWSER_DELAY_SECONDS", "-0.1", "browser_delay_seconds"),
        ("EARNINGS_OPTIONS_BROWSER_DELAY_SECONDS", "inf", "browser_delay_seconds"),
    ),
)
def test_load_analysis_settings_rejects_invalid_browser_timing(name, value, message, tmp_path):
    with pytest.raises(ValueError, match=message):
        load_analysis_settings({name: value}, tmp_path)
