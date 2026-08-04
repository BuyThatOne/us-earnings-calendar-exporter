from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from typing import Callable

import requests

from earnings_export.options_models import OptionChainSnapshot, OptionContract, ProviderCapability
from earnings_export.sources.options_provider import ProviderResult


YAHOO_OPTIONS_URL = "https://query2.finance.yahoo.com/v7/finance/options/{symbol}"
SUPPORTED_FIELDS = ("bid", "ask", "implied_volatility", "open_interest")


def _float_or_none(value: object) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def _int_or_none(value: object) -> int | None:
    parsed = _float_or_none(value)
    return int(parsed) if parsed is not None else None


def _parse_expiration(value: object) -> date | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(timestamp) or timestamp <= 0:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def _parse_quote_timestamp(value: object) -> datetime | None:
    timestamp = _float_or_none(value)
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_contract(record: dict, option_type: str, expiration: date | None) -> OptionContract | None:
    raw_bid = record.get("bid")
    raw_ask = record.get("ask")
    raw_strike = record.get("strike")
    raw_timestamp = record.get("lastTradeDate")
    bid = _float_or_none(raw_bid)
    ask = _float_or_none(raw_ask)
    strike = _float_or_none(raw_strike)
    quote_timestamp = _parse_quote_timestamp(raw_timestamp)
    if (
        (raw_bid not in (None, "", "None") and bid is None)
        or (raw_ask not in (None, "", "None") and ask is None)
        or (raw_strike not in (None, "", "None") and strike is None)
        or (raw_timestamp is not None and quote_timestamp is None)
    ):
        return None

    bid = bid or 0.0
    ask = ask or 0.0
    midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 else None
    spread_pct = (ask - bid) / midpoint if midpoint else None
    return OptionContract(
        option_symbol=str(record.get("contractSymbol") or ""),
        option_type=option_type,
        expiration=expiration,
        strike=strike or 0.0,
        bid=bid,
        ask=ask,
        midpoint=midpoint,
        bid_ask_spread_pct=spread_pct,
        implied_volatility=_float_or_none(record.get("impliedVolatility")),
        open_interest=_int_or_none(record.get("openInterest")),
        quote_timestamp=quote_timestamp,
    )


def parse_yahoo_options(payload: dict, symbol: str, collected_at: datetime) -> ProviderResult:
    results = payload.get("optionChain", {}).get("result")
    if not isinstance(results, list) or not results:
        return ProviderResult.unavailable("yahoo", "invalid_response")

    chain = results[0]
    option_sets = chain.get("options")
    if not isinstance(option_sets, list):
        return ProviderResult.unavailable("yahoo", "invalid_response")
    contracts = []
    invalid_option_sets = 0
    invalid_contracts = 0
    for option_set in option_sets:
        if not isinstance(option_set, dict):
            invalid_option_sets += 1
            continue
        expiration = _parse_expiration(option_set.get("expirationDate"))
        if expiration is None:
            invalid_option_sets += 1
            continue
        for option_type, field in (("call", "calls"), ("put", "puts")):
            records = option_set.get(field, [])
            if isinstance(records, list):
                for record in records:
                    if not isinstance(record, dict):
                        invalid_contracts += 1
                        continue
                    contract = _parse_contract(record, option_type, expiration)
                    if contract is None:
                        invalid_contracts += 1
                        continue
                    contracts.append(contract)

    if not contracts:
        return ProviderResult.unavailable("yahoo", "invalid_response")

    capability = ProviderCapability(
        provider="yahoo",
        available=True,
        code="partial_data" if invalid_option_sets or invalid_contracts else "available",
        supported_fields=SUPPORTED_FIELDS,
    )
    snapshot = OptionChainSnapshot(
        symbol=symbol,
        collected_at=collected_at,
        provider="yahoo",
        provider_capabilities=(capability,),
        underlying_price=_float_or_none(chain.get("quote", {}).get("regularMarketPrice")),
        contracts=tuple(contracts),
        data_quality_flags=(
            *(("partial_option_set_data",) if invalid_option_sets else ()),
            *(("partial_contract_data",) if invalid_contracts else ()),
        ),
    )
    return ProviderResult(snapshot=snapshot, capability=capability)


class YahooOptionsProvider:
    name = "yahoo"

    def __init__(
        self,
        session: requests.Session,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._session = session
        self._clock = clock

    def fetch_current_chain(self, symbol: str) -> ProviderResult:
        response = self._session.get(YAHOO_OPTIONS_URL.format(symbol=symbol), params={}, timeout=30)
        response.raise_for_status()
        return parse_yahoo_options(response.json(), symbol, self._clock())

    def fetch_historical_chain(self, symbol: str, as_of: date) -> ProviderResult:
        return ProviderResult.unavailable(self.name, "unsupported")
