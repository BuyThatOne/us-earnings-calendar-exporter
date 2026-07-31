import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from earnings_export.sources.alpha_vantage_options import (
    parse_alpha_vantage_error,
    parse_alpha_vantage_options,
)


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
