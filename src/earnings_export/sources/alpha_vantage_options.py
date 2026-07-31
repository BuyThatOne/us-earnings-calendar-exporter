from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Callable

import requests

from earnings_export.options_config import AnalysisSettings
from earnings_export.options_models import (
    OptionChainSnapshot,
    OptionContract,
    OptionGreeks,
    ProviderCapability,
)
from earnings_export.sources.options_provider import ProviderResult


ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
SUPPORTED_FIELDS = (
    "bid",
    "ask",
    "implied_volatility",
    "greeks",
    "open_interest",
)


def _float_or_none(value: object) -> float | None:
    if value in (None, "", "None"):
        return None
    return float(value)


def _int_or_none(value: object) -> int | None:
    if value in (None, "", "None"):
        return None
    return int(float(value))


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value))


def _parse_quote_timestamp(value: object) -> datetime | None:
    quote_date = _parse_date(value)
    if quote_date is None:
        return None
    return datetime.combine(quote_date, time.min, tzinfo=timezone.utc)


def _parse_contract(record: dict) -> OptionContract:
    bid = _float_or_none(record.get("bid")) or 0.0
    ask = _float_or_none(record.get("ask")) or 0.0
    midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 else None
    spread_pct = (ask - bid) / midpoint if midpoint else None
    greeks = OptionGreeks(
        delta=_float_or_none(record.get("delta")),
        gamma=_float_or_none(record.get("gamma")),
        theta=_float_or_none(record.get("theta")),
        vega=_float_or_none(record.get("vega")),
        rho=_float_or_none(record.get("rho")),
    )
    return OptionContract(
        option_symbol=str(record.get("contractID") or record.get("contract_id") or ""),
        option_type=str(record.get("type") or "").lower(),
        expiration=_parse_date(record.get("expiration")),
        strike=_float_or_none(record.get("strike")) or 0.0,
        bid=bid,
        ask=ask,
        midpoint=midpoint,
        bid_ask_spread_pct=spread_pct,
        implied_volatility=_float_or_none(record.get("implied_volatility")),
        greeks=greeks,
        open_interest=_int_or_none(record.get("open_interest")),
        quote_timestamp=_parse_quote_timestamp(record.get("date")),
    )


def parse_alpha_vantage_error(payload: dict, symbol: str, collected_at: datetime) -> ProviderResult:
    message = str(payload.get("Information") or payload.get("Note") or "Alpha Vantage unavailable")
    return ProviderResult.unavailable("alpha_vantage", "entitlement_unavailable", message)


def parse_alpha_vantage_options(payload: dict, symbol: str, collected_at: datetime) -> ProviderResult:
    if "Information" in payload or "Note" in payload:
        return parse_alpha_vantage_error(payload, symbol, collected_at)

    records = payload.get("data")
    if not isinstance(records, list):
        return ProviderResult.unavailable("alpha_vantage", "invalid_response")

    capability = ProviderCapability(
        provider="alpha_vantage",
        available=True,
        code="available",
        supported_fields=SUPPORTED_FIELDS,
    )
    snapshot = OptionChainSnapshot(
        symbol=symbol,
        collected_at=collected_at,
        provider="alpha_vantage",
        provider_capabilities=(capability,),
        contracts=tuple(_parse_contract(record) for record in records if isinstance(record, dict)),
    )
    return ProviderResult(snapshot=snapshot, capability=capability)


class AlphaVantageOptionsProvider:
    name = "alpha_vantage"

    def __init__(
        self,
        settings: AnalysisSettings,
        session: requests.Session,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._settings = settings
        self._session = session
        self._clock = clock

    def fetch_current_chain(self, symbol: str) -> ProviderResult:
        return self._fetch(symbol, "REALTIME_OPTIONS")

    def fetch_historical_chain(self, symbol: str, as_of: date) -> ProviderResult:
        return self._fetch(symbol, "HISTORICAL_OPTIONS", {"date": as_of.isoformat()})

    def _fetch(self, symbol: str, function: str, extra_params: dict[str, str] | None = None) -> ProviderResult:
        if not self._settings.alpha_vantage_api_key:
            return ProviderResult.unavailable(self.name, "missing_api_key")

        params = {
            "function": function,
            "symbol": symbol,
            "apikey": self._settings.alpha_vantage_api_key,
        }
        if extra_params:
            params.update(extra_params)
        response = self._session.get(ALPHA_VANTAGE_URL, params=params, timeout=30)
        response.raise_for_status()
        return parse_alpha_vantage_options(response.json(), symbol, self._clock())
