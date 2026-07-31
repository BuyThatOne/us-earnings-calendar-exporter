from __future__ import annotations

from earnings_export.models import ExportRow


def filter_and_sort_events(events, market_caps, exported_at, min_market_cap):
    rows = []
    for event in events:
        market_cap = market_caps.get(event.ticker)
        if market_cap is None or market_cap < min_market_cap:
            continue
        rows.append(
            ExportRow(
                earnings_date=event.earnings_date.isoformat(),
                ticker=event.ticker,
                company_name=event.company_name,
                exchange=event.exchange,
                market_cap=market_cap,
                earnings_time=event.earnings_time,
                source_calendar_url=event.source_calendar_url,
                source_market_cap_url=f"https://finviz.com/quote.ashx?t={event.ticker}",
                exported_at=exported_at,
            )
        )
    return sorted(rows, key=lambda row: (row.earnings_date, row.ticker))
