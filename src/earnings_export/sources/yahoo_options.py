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
    if value is None:
        return None
    return float(value)


def _parse_expiration(value: object) -> date | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(timestamp) or timestamp <= 0:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def _parse_contract(record: dict, option_type: str, expiration: date | None) -> OptionContract:
    bid = _float_or_none(record.get("bid")) or 0.0
    ask = _float_or_none(record.get("ask")) or 0.0
    midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 else None
    spread_pct = (ask - bid) / midpoint if midpoint else None
    timestamp = record.get("lastTradeDate")
    return OptionContract(
        option_symbol=str(record.get("contractSymbol") or ""),
        option_type=option_type,
        expiration=expiration,
        strike=_float_or_none(record.get("strike")) or 0.0,
        bid=bid,
        ask=ask,
        midpoint=midpoint,
        bid_ask_spread_pct=spread_pct,
        implied_volatility=_float_or_none(record.get("impliedVolatility")),
        open_interest=record.get("openInterest"),
        quote_timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else None,
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
                contracts.extend(
                    _parse_contract(record, option_type, expiration) for record in records if isinstance(record, dict)
                )

    if not contracts:
        return ProviderResult.unavailable("yahoo", "invalid_response")

    capability = ProviderCapability(
        provider="yahoo",
        available=True,
        code="partial_data" if invalid_option_sets else "available",
        supported_fields=SUPPORTED_FIELDS,
    )
    snapshot = OptionChainSnapshot(
        symbol=symbol,
        collected_at=collected_at,
        provider="yahoo",
        provider_capabilities=(capability,),
        underlying_price=_float_or_none(chain.get("quote", {}).get("regularMarketPrice")),
        contracts=tuple(contracts),
        data_quality_flags=("partial_option_set_data",) if invalid_option_sets else (),
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
