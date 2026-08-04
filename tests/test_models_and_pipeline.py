from datetime import date
from pathlib import Path

import requests

from earnings_export.models import EarningsEvent
from earnings_export.pipeline import filter_and_sort_events, lookup_market_caps_for_events


FIXTURES = Path("tests/fixtures/finviz_market_cap")


class FixtureSession:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, **_kwargs) -> requests.Response:
        self.urls.append(url)
        response = requests.Response()
        response.status_code = 429
        response.url = url
        response._content = (FIXTURES / "cepf_429.html").read_bytes()
        return response


def test_filter_and_sort_events_keeps_threshold_and_sorts():
    events = [
        EarningsEvent(date(2026, 8, 4), "MSFT", "Microsoft", "AMC", "NASDAQ", "https://calendar/a"),
        EarningsEvent(
            date(2026, 8, 3),
            "AAPL",
            "Apple",
            "BMO",
            "NASDAQ",
            "https://calendar/b",
            50_000_000_000,
            "https://calendar/b",
        ),
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
    assert rows[0].source_market_cap_url == "https://calendar/b"


def test_lookup_market_caps_for_events_uses_nasdaq_values_before_finviz(monkeypatch):
    events = [
        EarningsEvent(
            date(2026, 8, 3),
            "AAPL",
            "Apple",
            "BMO",
            "NASDAQ",
            "https://calendar/a",
            4_486_620_000_000,
            "https://calendar/a",
        ),
        EarningsEvent(
            date(2026, 8, 3),
            "MSFT",
            "Microsoft",
            "AMC",
            "NASDAQ",
            "https://calendar/b",
        ),
    ]

    calls = []

    def fake_fetch_market_caps(symbols, session):
        calls.append(symbols)
        return {"MSFT": 3_900_000_000_000}

    monkeypatch.setattr("earnings_export.pipeline.fetch_market_caps", fake_fetch_market_caps)

    market_caps = lookup_market_caps_for_events(events, session=object())

    assert market_caps == {
        "AAPL": 4_486_620_000_000,
        "MSFT": 3_900_000_000_000,
    }
    assert calls == [["MSFT"]]


def test_lookup_market_caps_for_events_keeps_nasdaq_caps_when_finviz_rate_limits():
    events = [
        EarningsEvent(
            date(2026, 8, 3),
            "AAPL",
            "Apple",
            "BMO",
            "NASDAQ",
            "https://calendar/a",
            4_486_620_000_000,
            "https://calendar/a",
        ),
        EarningsEvent(date(2026, 8, 3), "CEPF", "Cantor", "AMC", "NASDAQ", "https://calendar/b"),
        EarningsEvent(date(2026, 8, 3), "MSFT", "Microsoft", "AMC", "NASDAQ", "https://calendar/c"),
    ]
    session = FixtureSession()

    market_caps = lookup_market_caps_for_events(events, session)

    assert market_caps == {"AAPL": 4_486_620_000_000}
    assert session.urls == ["https://finviz.com/quote.ashx?t=CEPF"]
