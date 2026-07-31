from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EarningsEvent:
    earnings_date: date
    ticker: str
    company_name: str
    earnings_time: str | None
    exchange: str | None
    source_calendar_url: str
    market_cap: int | None = None
    market_cap_source_url: str | None = None


@dataclass(frozen=True)
class ExportRow:
    earnings_date: str
    ticker: str
    company_name: str
    exchange: str | None
    market_cap: int
    earnings_time: str | None
    source_calendar_url: str
    source_market_cap_url: str
    exported_at: str
