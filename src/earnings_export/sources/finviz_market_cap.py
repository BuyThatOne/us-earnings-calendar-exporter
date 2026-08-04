from __future__ import annotations

import re

import requests


def normalize_symbol_for_finviz(symbol: str) -> str:
    return symbol.replace(".", "-").upper()


def parse_market_cap_text(raw_value: str) -> int | None:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([TMB])", raw_value.strip())
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"T": 1_000_000_000_000, "B": 1_000_000_000, "M": 1_000_000}[match.group(2)]
    return int(number * multiplier)


def extract_market_cap_from_html(html: str) -> int | None:
    match = re.search(
        r'<div class="snapshot-td-label">Market Cap</div></td><td[^>]*>.*?<div class="snapshot-td-content"><b>([^<]+)</b>',
        html,
        re.S,
    )
    if not match:
        return None
    return parse_market_cap_text(match.group(1))


def fetch_market_caps(symbols: list[str], session: requests.Session) -> dict[str, int]:
    market_caps: dict[str, int] = {}
    for symbol in symbols:
        normalized = normalize_symbol_for_finviz(symbol)
        url = f"https://finviz.com/quote.ashx?t={normalized}"
        response = session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finviz.com/"},
            timeout=30,
        )
        if response.status_code == requests.codes.too_many_requests:
            break
        response.raise_for_status()
        market_cap = extract_market_cap_from_html(response.text)
        if market_cap is not None:
            market_caps[symbol] = market_cap
    return market_caps
