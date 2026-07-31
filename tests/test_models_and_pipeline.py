from datetime import date

from earnings_export.models import EarningsEvent
from earnings_export.pipeline import filter_and_sort_events


def test_filter_and_sort_events_keeps_threshold_and_sorts():
    events = [
        EarningsEvent(date(2026, 8, 4), "MSFT", "Microsoft", "AMC", "NASDAQ", "https://calendar/a"),
        EarningsEvent(date(2026, 8, 3), "AAPL", "Apple", "BMO", "NASDAQ", "https://calendar/b"),
        EarningsEvent(date(2026, 8, 3), "XYZ", "Small Cap", "AMC", "NYSE", "https://calendar/c"),
    ]
    market_caps = {
        "AAPL": 50_000_000_000,
        "MSFT": 3_000_000_000_000,
        "XYZ": 49_999_999_999,
    }

    rows = filter_and_sort_events(
        events,
        market_caps=market_caps,
        exported_at="2026-07-31T12:00:00Z",
        min_market_cap=50_000_000_000,
    )

    assert [row.ticker for row in rows] == ["AAPL", "MSFT"]
    assert rows[0].market_cap == 50_000_000_000
