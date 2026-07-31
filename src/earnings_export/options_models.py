from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class OptionGreeks:
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None


@dataclass(frozen=True)
class OptionContract:
    option_symbol: str = ""
    option_type: str = ""
    expiration: date | None = None
    strike: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    midpoint: float | None = None
    bid_ask_spread_pct: float | None = None
    implied_volatility: float | None = None
    greeks: OptionGreeks | None = None
    open_interest: int | None = None
    quote_timestamp: datetime | None = None


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    available: bool
    code: str
    supported_fields: tuple[str, ...] = ()
    message: str | None = None


@dataclass(frozen=True)
class OptionChainSnapshot:
    symbol: str
    collected_at: datetime
    provider: str
    provider_capabilities: tuple[ProviderCapability, ...] = ()
    underlying_price: float | None = None
    contracts: tuple[OptionContract, ...] = ()
    data_quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class EarningsMoveHistory:
    historical_earnings_events: tuple[date, ...] = ()
    one_day_post_earnings_moves: tuple[float, ...] = ()
    absolute_move_mean: float | None = None
    absolute_move_median: float | None = None
    absolute_move_max: float | None = None
    historical_iv_observations: tuple[float, ...] | None = None
    optionslam_evr: float | None = None
    source_provenance: tuple[str, ...] = ()
    data_quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrategyCandidate:
    ticker: str
    earnings_date: date
    strategy_type: str
    defined_risk: bool
    legs: tuple[OptionContract, ...]
    entry_limit: float
    maximum_loss: float | None
    implied_move_pct: float
    historical_median_move_pct: float | None
    historical_iv_change_pct: float | None
    warnings: tuple[str, ...]
    rationale: str
    execution_status: str = "research_only"
