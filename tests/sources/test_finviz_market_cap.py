from pathlib import Path

import pytest
import requests

from earnings_export.sources.finviz_market_cap import (
    extract_market_cap_from_html,
    fetch_market_caps,
    parse_market_cap_text,
)


FIXTURES = Path("tests/fixtures/finviz_market_cap")


class FixtureSession:
    def __init__(self, responses: list[requests.Response]) -> None:
        self.responses = iter(responses)
        self.urls: list[str] = []

    def get(self, url: str, **_kwargs) -> requests.Response:
        self.urls.append(url)
        return next(self.responses)


def _response(status_code: int, fixture_name: str) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.url = "https://finviz.com/quote.ashx"
    response._content = (FIXTURES / fixture_name).read_bytes()
    return response


def test_parse_market_cap_text_handles_b_t_and_m():
    assert parse_market_cap_text("50B") == 50_000_000_000
    assert parse_market_cap_text("1.25T") == 1_250_000_000_000
    assert parse_market_cap_text("950M") == 950_000_000


def test_extract_market_cap_from_html_reads_market_cap_field():
    html = (FIXTURES / "aapl.html").read_text()
    assert extract_market_cap_from_html(html) == 4_486_620_000_000


def test_fetch_market_caps_returns_collected_caps_and_stops_after_finviz_rate_limit():
    session = FixtureSession(
        [
            _response(200, "aapl.html"),
            _response(429, "cepf_429.html"),
        ]
    )

    market_caps = fetch_market_caps(["AAPL", "CEPF", "MSFT"], session)

    assert market_caps == {"AAPL": 4_486_620_000_000}
    assert session.urls == [
        "https://finviz.com/quote.ashx?t=AAPL",
        "https://finviz.com/quote.ashx?t=CEPF",
    ]


def test_fetch_market_caps_raises_for_unexpected_http_failure():
    session = FixtureSession([_response(500, "cepf_429.html")])

    with pytest.raises(requests.HTTPError):
        fetch_market_caps(["CEPF"], session)
