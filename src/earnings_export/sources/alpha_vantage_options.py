from __future__ import annotations

from datetime import date, datetime, time, timezone
from math import isfinite
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
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _int_or_none(value: object) -> int | None:
    if value in (None, "", "None"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if isfinite(parsed) else None


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_quote_timestamp(value: object) -> datetime | None:
    quote_date = _parse_date(value)
    if quote_date is None:
        return None
    return datetime.combine(quote_date, time.min, tzinfo=timezone.utc)


def _parse_contract(record: dict) -> OptionContract | None:
    option_symbol = str(record.get("contractID") or record.get("contract_id") or "")
    option_type = str(record.get("type") or "").lower()
    expiration = _parse_date(record.get("expiration"))
    strike = _float_or_none(record.get("strike"))
    if not option_symbol or option_type not in {"call", "put"} or expiration is None or not strike or strike < 0:
        return None

    raw_bid = record.get("bid")
    raw_ask = record.get("ask")
    bid = _float_or_none(raw_bid)
    ask = _float_or_none(raw_ask)
    if raw_bid not in (None, "", "None") and bid is None:
        return None
    if raw_ask not in (None, "", "None") and ask is None:
        return None
    bid = bid or 0.0
    ask = ask or 0.0
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
        option_symbol=option_symbol,
        option_type=option_type,
        expiration=expiration,
        strike=strike,
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
    note = str(payload.get("Note") or "").lower()
    if any(phrase in note for phrase in ("frequency", "rate limit", "requests per", "calls per")):
        return ProviderResult.unavailable("alpha_vantage", "rate_limited", "Alpha Vantage rate limit reached")
    return ProviderResult.unavailable(
        "alpha_vantage", "entitlement_unavailable", "Alpha Vantage entitlement is unavailable",
    )


def parse_alpha_vantage_options(payload: object, symbol: str, collected_at: datetime) -> ProviderResult:
    if not isinstance(payload, dict):
        return ProviderResult.unavailable("alpha_vantage", "invalid_response")

    if "Information" in payload or "Note" in payload:
        return parse_alpha_vantage_error(payload, symbol, collected_at)

    records = payload.get("data")
    if not isinstance(records, list):
        return ProviderResult.unavailable("alpha_vantage", "invalid_response")

    contracts = []
    invalid_records = 0
    for record in records:
        if not isinstance(record, dict):
            invalid_records += 1
            continue
        contract = _parse_contract(record)
        if contract is None:
            invalid_records += 1
            continue
        contracts.append(contract)
    if not contracts:
        return ProviderResult.unavailable("alpha_vantage", "invalid_response")

    capability = ProviderCapability(
        provider="alpha_vantage",
        available=True,
        code="partial_data" if invalid_records else "available",
        supported_fields=SUPPORTED_FIELDS,
    )
    snapshot = OptionChainSnapshot(
        symbol=symbol,
        collected_at=collected_at,
        provider="alpha_vantage",
        provider_capabilities=(capability,),
        contracts=tuple(contracts),
        data_quality_flags=("partial_contract_data",) if invalid_records else (),
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

    def fetch_current_chain(
        self,
        symbol: str,
        expiration: date | None = None,
    ) -> ProviderResult:
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
        try:
            response = self._session.get(ALPHA_VANTAGE_URL, params=params, timeout=30)
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = error.response.status_code if error.response is not None else None
            code = "rate_limited" if status_code == 429 else "entitlement_unavailable" if status_code in {401, 403} else "http_error"
            message = f"Alpha Vantage HTTP request failed ({status_code})" if status_code else "Alpha Vantage HTTP request failed"
            return ProviderResult.unavailable(self.name, code, message)
        except requests.RequestException:
            return ProviderResult.unavailable(self.name, "network_error", "Alpha Vantage request failed")

        try:
            payload = response.json()
        except ValueError:
            return ProviderResult.unavailable(self.name, "invalid_response")
        return parse_alpha_vantage_options(payload, symbol, self._clock())
