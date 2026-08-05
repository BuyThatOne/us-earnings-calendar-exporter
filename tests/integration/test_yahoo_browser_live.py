from datetime import datetime, timezone
from math import isfinite

import pytest

from earnings_export.sources.yahoo_browser_options import (
    PlaywrightYahooPageReader,
    YahooBrowserOptionsProvider,
)


@pytest.mark.integration
def test_live_yahoo_options_page_returns_normalized_call_and_put():
    reader = PlaywrightYahooPageReader(timeout_seconds=30.0, delay_seconds=0.0)
    provider = YahooBrowserOptionsProvider(reader, clock=lambda: datetime.now(timezone.utc))

    try:
        result = provider.fetch_current_chain("AAPL")
    finally:
        provider.close()

    assert result.capability.available, result.capability
    assert result.snapshot is not None
    assert result.snapshot.underlying_price is not None
    assert result.snapshot.underlying_price > 0

    option_types = {contract.option_type for contract in result.snapshot.contracts}
    assert option_types == {"call", "put"}
    assert all(contract.option_symbol for contract in result.snapshot.contracts)
    assert all(
        isfinite(value) and value >= 0
        for contract in result.snapshot.contracts
        for value in (contract.bid, contract.ask)
    )
