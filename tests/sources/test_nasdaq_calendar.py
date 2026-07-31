import json
from datetime import date
from pathlib import Path

import pytest

from earnings_export.sources.nasdaq_calendar import (
    build_nasdaq_calendar_url,
    parse_nasdaq_calendar_payload,
)


def test_parse_nasdaq_calendar_payload_returns_normalized_events():
    fixture_path = Path("tests/fixtures/nasdaq_calendar/sample_day.json")
    payload = json.loads(fixture_path.read_text())
    source_url = build_nasdaq_calendar_url(date(2026, 8, 3))

    events = parse_nasdaq_calendar_payload(payload, date(2026, 8, 3), source_url)

    assert events[0].ticker == "AAPL"
    assert events[0].earnings_date == date(2026, 8, 3)
    assert events[0].source_calendar_url == source_url
    assert events[0].exchange is None
    assert events[0].market_cap == 4_119_121_560_000
    assert events[0].market_cap_source_url == source_url


def test_parse_nasdaq_calendar_payload_raises_for_missing_rows():
    with pytest.raises(ValueError, match="NASDAQ payload missing data.rows"):
        parse_nasdaq_calendar_payload({}, date(2026, 8, 3), "https://example.com")
