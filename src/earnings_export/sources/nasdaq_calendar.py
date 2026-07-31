from __future__ import annotations

import re
from datetime import date
from urllib.parse import quote

import requests

from earnings_export.models import EarningsEvent


def build_nasdaq_calendar_url(day: date) -> str:
    return f"https://api.nasdaq.com/api/calendar/earnings?date={quote(day.isoformat())}"


def parse_nasdaq_market_cap(raw_value: str | None) -> int | None:
    if not raw_value:
        return None
    digits = re.sub(r"[^0-9]", "", raw_value)
    if not digits:
        return None
    return int(digits)


def parse_nasdaq_calendar_payload(payload: dict, earnings_day: date, source_url: str) -> list[EarningsEvent]:
    rows = payload.get("data", {}).get("rows")
    if not isinstance(rows, list):
        raise ValueError("NASDAQ payload missing data.rows")
    events = []
    for row in rows:
        ticker = row["symbol"].strip().upper()
        events.append(
            EarningsEvent(
                earnings_date=earnings_day,
                ticker=ticker,
                company_name=row["name"].strip(),
                earnings_time=row.get("time") or None,
                exchange=row.get("exchange") or None,
                source_calendar_url=source_url,
                market_cap=parse_nasdaq_market_cap(row.get("marketCap")),
                market_cap_source_url=source_url if row.get("marketCap") else None,
            )
        )
    return events


def fetch_nasdaq_earnings_for_day(day: date, session: requests.Session) -> list[EarningsEvent]:
    url = build_nasdaq_calendar_url(day)
    response = session.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        },
        timeout=30,
    )
    response.raise_for_status()
    return parse_nasdaq_calendar_payload(response.json(), day, url)
