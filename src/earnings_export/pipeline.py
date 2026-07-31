from __future__ import annotations

from earnings_export.date_window import iter_weekdays
from earnings_export.models import ExportRow
from earnings_export.sources.finviz_market_cap import fetch_market_caps
from earnings_export.sources.nasdaq_calendar import fetch_nasdaq_earnings_for_day


def filter_and_sort_events(events, market_caps, exported_at, min_market_cap):
    rows = []
    for event in events:
        market_cap = market_caps.get(event.ticker)
        if market_cap is None or market_cap < min_market_cap:
            continue
        source_market_cap_url = (
            event.market_cap_source_url
            if event.market_cap is not None
            and event.market_cap == market_cap
            and event.market_cap_source_url
            else f"https://finviz.com/quote.ashx?t={event.ticker}"
        )
        rows.append(
            ExportRow(
                earnings_date=event.earnings_date.isoformat(),
                ticker=event.ticker,
                company_name=event.company_name,
                exchange=event.exchange,
                market_cap=market_cap,
                earnings_time=event.earnings_time,
                source_calendar_url=event.source_calendar_url,
                source_market_cap_url=source_market_cap_url,
                exported_at=exported_at,
            )
        )
    return sorted(rows, key=lambda row: (row.earnings_date, row.ticker))


def collect_events_for_week(start_date, end_date, session):
    events = []
    seen = set()
    for day in iter_weekdays(start_date, end_date):
        for event in fetch_nasdaq_earnings_for_day(day, session):
            key = (event.earnings_date, event.ticker)
            if key in seen:
                continue
            seen.add(key)
            events.append(event)
    return events


def lookup_market_caps_for_events(events, session):
    market_caps = {
        event.ticker: event.market_cap
        for event in events
        if event.market_cap is not None
    }
    missing_symbols = sorted({event.ticker for event in events if event.ticker not in market_caps})
    if missing_symbols:
        market_caps.update(fetch_market_caps(missing_symbols, session))
    return market_caps


def build_export_rows(events, market_caps, exported_at, min_market_cap):
    return filter_and_sort_events(events, market_caps, exported_at, min_market_cap)
