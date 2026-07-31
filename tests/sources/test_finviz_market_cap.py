from pathlib import Path

from earnings_export.sources.finviz_market_cap import (
    extract_market_cap_from_html,
    parse_market_cap_text,
)


def test_parse_market_cap_text_handles_b_t_and_m():
    assert parse_market_cap_text("50B") == 50_000_000_000
    assert parse_market_cap_text("1.25T") == 1_250_000_000_000
    assert parse_market_cap_text("950M") == 950_000_000


def test_extract_market_cap_from_html_reads_market_cap_field():
    html = Path("tests/fixtures/finviz_market_cap/aapl.html").read_text()
    assert extract_market_cap_from_html(html) == 4_486_620_000_000
