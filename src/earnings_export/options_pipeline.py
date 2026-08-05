from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import date, datetime
from math import isfinite
from typing import Protocol, Sequence

import requests

from earnings_export.export.options_report import AnalysisRunResult
from earnings_export.models import EarningsEvent
from earnings_export.options_config import AnalysisSettings
from earnings_export.options_history import build_earnings_move_history
from earnings_export.options_models import OptionChainSnapshot, ProviderCapability
from earnings_export.options_strategy import build_ranked_candidates
from earnings_export.sources.options_provider import OptionsDataProvider, ProviderResult
from earnings_export.sources.optionslam_evr import EvrResult, OPTIONSLAM_URL


class EvrDataProvider(Protocol):
    def fetch_public_evr(self, symbol: str) -> EvrResult:
        raise NotImplementedError


def _ordered_providers(
    providers: Sequence[OptionsDataProvider], settings: AnalysisSettings,
) -> tuple[OptionsDataProvider, ...]:
    by_name = {provider.name: provider for provider in providers}
    return tuple(by_name[name] for name in settings.provider_order if name in by_name)


def close_options_providers(providers: Sequence[OptionsDataProvider]) -> None:
    """Release resources held by providers that expose a close method."""
    for provider in providers:
        close = getattr(provider, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


def _request_failed(provider: OptionsDataProvider) -> ProviderResult:
    return ProviderResult.unavailable(provider.name, "request_failed")


def _fetch_current_chain(provider: OptionsDataProvider, symbol: str) -> ProviderResult:
    try:
        return provider.fetch_current_chain(symbol)
    except requests.RequestException:
        return _request_failed(provider)
    except ValueError:
        return ProviderResult.unavailable(provider.name, "invalid_response")


def _fetch_historical_chain(
    provider: OptionsDataProvider, symbol: str, as_of: date,
) -> ProviderResult:
    try:
        return provider.fetch_historical_chain(symbol, as_of)
    except requests.RequestException:
        return _request_failed(provider)
    except ValueError:
        return ProviderResult.unavailable(provider.name, "invalid_response")


def _valid_underlying_price(snapshot: OptionChainSnapshot) -> bool:
    price = snapshot.underlying_price
    return price is not None and isfinite(price) and price > 0


def _add_yahoo_spot(
    snapshot: OptionChainSnapshot,
    providers: Sequence[OptionsDataProvider],
    symbol: str,
) -> tuple[OptionChainSnapshot, tuple[ProviderCapability, ...]]:
    if snapshot.provider == "yahoo_browser" or _valid_underlying_price(snapshot):
        return snapshot, ()

    capabilities = []
    providers_by_name = {provider.name: provider for provider in providers}
    for provider_name in ("yahoo", "yahoo_browser"):
        provider = providers_by_name.get(provider_name)
        if provider is None or provider.name == snapshot.provider:
            continue
        result = _fetch_current_chain(provider, symbol)
        provider_snapshot = result.snapshot
        if (
            not result.capability.available
            or provider_snapshot is None
            or not _valid_underlying_price(provider_snapshot)
        ):
            capabilities.append(result.capability)
            continue

        spot_capability = replace(
            result.capability,
            supported_fields=("underlying_price",),
        )
        capabilities.append(spot_capability)
        return (
            replace(
                snapshot,
                underlying_price=provider_snapshot.underlying_price,
                provider_capabilities=snapshot.provider_capabilities + (spot_capability,),
                data_quality_flags=(
                    snapshot.data_quality_flags
                    + (f"underlying_price_from_{provider.name}",)
                ),
            ),
            tuple(capabilities),
        )

    return snapshot, tuple(capabilities)


def _missing_evr(symbol: str, run_at: datetime) -> EvrResult:
    return EvrResult(
        value=None,
        source_url=OPTIONSLAM_URL.format(symbol=symbol.strip().lower()),
        status="unavailable",
        collected_at=run_at,
    )


def _fetch_evr(
    provider: EvrDataProvider | None, symbol: str, run_at: datetime,
) -> EvrResult:
    if provider is None:
        return _missing_evr(symbol, run_at)
    try:
        return provider.fetch_public_evr(symbol)
    except requests.RequestException:
        missing = _missing_evr(symbol, run_at)
        return EvrResult(
            value=None,
            source_url=missing.source_url,
            status="request_failed",
            collected_at=run_at,
        )
    except ValueError:
        missing = _missing_evr(symbol, run_at)
        return EvrResult(
            value=None,
            source_url=missing.source_url,
            status="invalid_response",
            collected_at=run_at,
        )


def analyze_events(
    events: Sequence[EarningsEvent],
    providers: Sequence[OptionsDataProvider],
    settings: AnalysisSettings,
    run_at: datetime,
    evr_provider: EvrDataProvider | None = None,
) -> AnalysisRunResult:
    ordered_providers = _ordered_providers(providers, settings)
    candidates = []
    capabilities = []
    snapshots = []
    exclusions: Counter[str] = Counter()

    for event in sorted(events, key=lambda item: (item.earnings_date, item.ticker)):
        current_snapshot = None
        for provider in ordered_providers:
            current_result = _fetch_current_chain(provider, event.ticker)
            capabilities.append(current_result.capability)
            if current_result.capability.available and current_result.snapshot is not None:
                current_snapshot = current_result.snapshot
                break

        if current_snapshot is not None:
            current_snapshot, spot_capabilities = _add_yahoo_spot(
                current_snapshot, ordered_providers, event.ticker,
            )
            capabilities.extend(spot_capabilities)
            snapshots.append(current_snapshot)

        for provider in ordered_providers:
            if provider.name in {"yahoo", "yahoo_browser"}:
                continue
            historical_result = _fetch_historical_chain(
                provider, event.ticker, run_at.date(),
            )
            capabilities.append(historical_result.capability)
            if historical_result.snapshot is not None:
                snapshots.append(historical_result.snapshot)

        if current_snapshot is None:
            exclusions["missing_current_chain"] += 1
            continue

        evr = _fetch_evr(evr_provider, event.ticker, run_at)
        capabilities.append(
            ProviderCapability(
                provider="optionslam",
                available=evr.status == "available",
                code=evr.status,
                supported_fields=("evr",),
            )
        )
        history = build_earnings_move_history(
            events=(event,),
            closes={},
            iv_changes=(),
            evr=evr,
        )
        event_candidates = build_ranked_candidates(
            event.ticker,
            event.earnings_date,
            current_snapshot,
            history,
            settings.spread_limit,
            event.earnings_time,
        )
        if not event_candidates:
            exclusions["missing_liquid_chain"] += 1
            continue
        candidates.extend(event_candidates)

    return AnalysisRunResult(
        run_at=run_at,
        candidates=tuple(candidates),
        exclusions=dict(sorted(exclusions.items())),
        capabilities=tuple(capabilities),
        snapshots=tuple(snapshots),
    )
