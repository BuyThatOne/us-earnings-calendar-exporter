import json
from datetime import date, datetime, timezone
from pathlib import Path

from earnings_export.sources.yahoo_options import YahooOptionsProvider, parse_yahoo_options


FIXED_TIME = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)


def test_yahoo_current_chain_normalizes_quote_and_contracts():
    payload = json.loads(Path("tests/fixtures/yahoo_options/current_chain.json").read_text())

    result = parse_yahoo_options(payload, symbol="AAPL", collected_at=FIXED_TIME)

    assert result.snapshot.underlying_price == 210.50
    assert result.snapshot.contracts[0].option_type == "call"
    assert result.snapshot.contracts[0].bid == 4.20
    assert result.capability.available is True


def test_yahoo_adapter_rejects_historical_requests():
    provider = YahooOptionsProvider(session=object())

    result = provider.fetch_historical_chain("AAPL", date(2026, 7, 30))

    assert result.capability.code == "unsupported"
