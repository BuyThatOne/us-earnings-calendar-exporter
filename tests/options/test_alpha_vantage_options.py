import json
from datetime import datetime, timezone
from pathlib import Path

import requests

import pytest

from earnings_export.sources.alpha_vantage_options import (
    AlphaVantageOptionsProvider,
    parse_alpha_vantage_error,
    parse_alpha_vantage_options,
)
from earnings_export.options_config import AnalysisSettings


FIXED_TIME = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)


@pytest.fixture
def load_fixture():
    def load(relative_path: str) -> dict:
        return json.loads((Path("tests/fixtures") / relative_path).read_text())

    return load


def test_alpha_current_chain_normalizes_bid_ask_iv_and_greeks(load_fixture):
    result = parse_alpha_vantage_options(
        load_fixture("alpha_vantage/current_options.json"), symbol="AAPL", collected_at=FIXED_TIME,
    )

    assert result.snapshot.contracts[0].bid == 4.20
    assert result.snapshot.contracts[0].ask == 4.60
    assert result.snapshot.contracts[0].implied_volatility == 0.31
    assert result.snapshot.contracts[0].greeks.delta == 0.52
    assert result.capability.available is True


def test_alpha_entitlement_message_becomes_unavailable_capability():
    result = parse_alpha_vantage_error({"Information": "premium endpoint"}, "AAPL", FIXED_TIME)

    assert result.snapshot is None
    assert result.capability.code == "entitlement_unavailable"


def test_alpha_error_message_redacts_api_key():
    result = parse_alpha_vantage_error(
        {"Information": "apikey=super-secret-key is not entitled"}, "AAPL", FIXED_TIME,
    )

    assert result.capability.message is not None
    assert "super-secret-key" not in result.capability.message


def test_alpha_rate_limit_note_becomes_rate_limited_capability(load_fixture):
    result = parse_alpha_vantage_options(
        load_fixture("alpha_vantage/rate_limit_options.json"), "AAPL", FIXED_TIME,
    )

    assert result.snapshot is None
    assert result.capability.code == "rate_limited"


def test_alpha_partial_payload_keeps_valid_contract_and_marks_partial_data(load_fixture):
    result = parse_alpha_vantage_options(
        load_fixture("alpha_vantage/partial_options.json"), "AAPL", FIXED_TIME,
    )

    assert len(result.snapshot.contracts) == 1
    assert result.snapshot.contracts[0].option_symbol == "AAPL260821C00200000"
    assert result.capability.code == "partial_data"


def test_alpha_nan_numeric_record_is_excluded_as_partial_data(load_fixture):
    result = parse_alpha_vantage_options(
        load_fixture("alpha_vantage/nan_options.json"), "AAPL", FIXED_TIME,
    )

    assert len(result.snapshot.contracts) == 1
    assert result.snapshot.contracts[0].strike == 200.00
    assert result.capability.code == "partial_data"


def test_alpha_empty_payload_is_unavailable():
    result = parse_alpha_vantage_options({"data": []}, "AAPL", FIXED_TIME)

    assert result.snapshot is None
    assert result.capability.code == "invalid_response"


class FailingResponse:
    def __init__(self, status_code: int) -> None:
        self._status_code = status_code

    def raise_for_status(self) -> None:
        error = requests.HTTPError(
            f"{self._status_code} Client Error for url: https://example.test/?apikey=super-secret-key"
        )
        error.response = type("Response", (), {"status_code": self._status_code})()
        raise error


class FailingSession:
    def __init__(self, status_code: int) -> None:
        self._status_code = status_code

    def get(self, url, params, timeout):
        return FailingResponse(self._status_code)


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [(429, "rate_limited"), (403, "entitlement_unavailable")],
)
def test_alpha_http_failures_become_unavailable_capabilities_without_key_in_message(
    tmp_path, status_code, expected_code,
):
    provider = AlphaVantageOptionsProvider(
        AnalysisSettings(tmp_path, 0.10, ("alpha_vantage", "yahoo"), "super-secret-key"),
        FailingSession(status_code),
        clock=lambda: FIXED_TIME,
    )

    result = provider.fetch_current_chain("AAPL")

    assert result.snapshot is None
    assert result.capability.available is False
    assert result.capability.code == expected_code
    assert result.capability.message is not None
    assert "super-secret-key" not in result.capability.message
