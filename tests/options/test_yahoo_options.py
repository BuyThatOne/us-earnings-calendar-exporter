import json
from copy import deepcopy
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
    assert result.snapshot.contracts[0].expiration == date(2026, 8, 21)
    assert result.capability.available is True


def test_yahoo_malformed_expiration_skips_option_set_and_marks_partial_data():
    payload = json.loads(Path("tests/fixtures/yahoo_options/malformed_expiration_chain.json").read_text())

    result = parse_yahoo_options(payload, symbol="AAPL", collected_at=FIXED_TIME)

    assert len(result.snapshot.contracts) == 1
    assert result.snapshot.contracts[0].option_symbol == "AAPL260821P00200000"
    assert result.snapshot.contracts[0].expiration == date(2026, 8, 21)
    assert result.capability.code == "partial_data"


def test_yahoo_malformed_last_trade_date_skips_contract_and_keeps_valid_contract():
    payload = json.loads(Path("tests/fixtures/yahoo_options/current_chain.json").read_text())
    calls = payload["optionChain"]["result"][0]["options"][0]["calls"]
    malformed_contract = deepcopy(calls[0])
    malformed_contract["contractSymbol"] = "AAPL260821C00210000"
    malformed_contract["lastTradeDate"] = "not-a-timestamp"
    calls.append(malformed_contract)

    result = parse_yahoo_options(payload, symbol="AAPL", collected_at=FIXED_TIME)

    assert [contract.option_symbol for contract in result.snapshot.contracts] == [
        "AAPL260821C00200000"
    ]
    assert result.capability.code == "partial_data"


def test_yahoo_nonfinite_quote_is_skipped_and_marks_partial_data():
    payload = json.loads(Path("tests/fixtures/yahoo_options/current_chain.json").read_text())
    calls = payload["optionChain"]["result"][0]["options"][0]["calls"]
    nonfinite_contract = deepcopy(calls[0])
    nonfinite_contract["contractSymbol"] = "AAPL260821C00210000"
    nonfinite_contract["bid"] = float("nan")
    calls.append(nonfinite_contract)

    result = parse_yahoo_options(payload, symbol="AAPL", collected_at=FIXED_TIME)

    assert [contract.option_symbol for contract in result.snapshot.contracts] == [
        "AAPL260821C00200000"
    ]
    assert result.capability.code == "partial_data"


def test_yahoo_adapter_rejects_historical_requests():
    provider = YahooOptionsProvider(session=object())

    result = provider.fetch_historical_chain("AAPL", date(2026, 7, 30))

    assert result.capability.code == "unsupported"
