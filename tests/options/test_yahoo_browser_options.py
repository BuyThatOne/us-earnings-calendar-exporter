from datetime import date, datetime, timezone

from earnings_export.sources.yahoo_browser_options import (
    YahooBrowserOptionRow,
    YahooBrowserOptionsProvider,
    YahooBrowserPageData,
    parse_yahoo_browser_page,
)


FIXED_TIME = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)


def _page_data() -> YahooBrowserPageData:
    return YahooBrowserPageData(
        body_text="AAPL Options",
        underlying_price="$210.50",
        rows=(
            YahooBrowserOptionRow(
                "call",
                (
                    "AAPL260821C00200000",
                    "2026-07-31 10:00 AM EDT",
                    "$200.00",
                    "$12.50",
                    "$11.90",
                    "$12.10",
                    "+$0.30",
                    "+2.46%",
                    "1,234",
                    "5,678",
                    "31.25%",
                ),
            ),
            YahooBrowserOptionRow(
                "put",
                (
                    "AAPL260821P00200000",
                    "2026-07-31 10:00 AM EDT",
                    "$200.00",
                    "$1.50",
                    "-",
                    "$1.65",
                    "-$0.10",
                    "-6.06%",
                    "-",
                    "2,345",
                    "42.00%",
                ),
            ),
        ),
    )


def _page_data_with_bad_row() -> YahooBrowserPageData:
    page_data = _page_data()
    return YahooBrowserPageData(
        body_text=page_data.body_text,
        underlying_price=page_data.underlying_price,
        rows=(*page_data.rows, YahooBrowserOptionRow("call", ("placeholder",))),
    )


def _rate_limited_page() -> YahooBrowserPageData:
    return YahooBrowserPageData(
        body_text="Yahoo Finance has encountered an error. Please try again later.",
        underlying_price=None,
        rows=(),
    )


def _empty_page() -> YahooBrowserPageData:
    return YahooBrowserPageData(body_text="AAPL Options", underlying_price="$210.50", rows=())


def test_browser_page_normalizes_visible_quote_calls_and_puts():
    result = parse_yahoo_browser_page(_page_data(), "AAPL", FIXED_TIME)

    assert result.snapshot is not None
    assert result.snapshot.underlying_price == 210.50
    assert [(item.option_type, item.strike) for item in result.snapshot.contracts] == [
        ("call", 200.0),
        ("put", 200.0),
    ]
    assert result.snapshot.contracts[0].bid == 11.90
    assert result.snapshot.contracts[0].ask == 12.10
    assert result.snapshot.contracts[0].implied_volatility == 0.3125
    assert result.snapshot.contracts[0].open_interest == 5678
    assert result.snapshot.contracts[1].bid == 0.0
    assert result.snapshot.contracts[1].expiration == date(2026, 8, 21)


def test_browser_page_skips_placeholder_or_malformed_rows_as_partial_data():
    result = parse_yahoo_browser_page(_page_data_with_bad_row(), "AAPL", FIXED_TIME)

    assert result.snapshot is not None
    assert result.capability.code == "partial_data"
    assert len(result.snapshot.contracts) == 2


def test_browser_page_classifies_rate_limit_and_missing_contracts():
    assert parse_yahoo_browser_page(_rate_limited_page(), "AAPL", FIXED_TIME).capability.code == (
        "browser_rate_limited"
    )
    assert parse_yahoo_browser_page(_empty_page(), "AAPL", FIXED_TIME).capability.code == (
        "browser_parse_failed"
    )


def test_browser_provider_reads_page_data_with_its_clock():
    page_data = _page_data()

    class Reader:
        def read(self, symbol: str) -> YahooBrowserPageData:
            assert symbol == "AAPL"
            return page_data

    result = YahooBrowserOptionsProvider(Reader(), clock=lambda: FIXED_TIME).fetch_current_chain("AAPL")

    assert result.snapshot is not None
    assert result.snapshot.collected_at == FIXED_TIME

