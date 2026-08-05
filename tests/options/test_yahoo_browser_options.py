import json
from datetime import date, datetime, timezone
from pathlib import Path

import earnings_export.sources.yahoo_browser_options as yahoo_browser_options
from earnings_export.sources.yahoo_browser_options import (
    PlaywrightYahooPageReader,
    YahooBrowserOptionRow,
    YahooBrowserOptionsProvider,
    YahooBrowserPageData,
    parse_yahoo_browser_page,
)


FIXED_TIME = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "yahoo_browser_options"


class _FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.ok = status < 400


class _FakeCells:
    def __init__(self, texts: tuple[str, ...]) -> None:
        self._texts = texts

    def all_inner_texts(self) -> list[str]:
        return list(self._texts)


class _FakeRow:
    def __init__(self, cells: tuple[str, ...]) -> None:
        self._cells = cells

    def locator(self, selector: str) -> _FakeCells:
        assert selector == "td"
        return _FakeCells(self._cells)


class _FakeRows:
    def __init__(self, rows: tuple[_FakeRow, ...], waits: list[tuple[str, float]]) -> None:
        self._rows = rows
        self._waits = waits

    @property
    def first(self) -> "_FakeRows":
        return self

    def wait_for(self, *, state: str, timeout: float) -> None:
        self._waits.append((state, timeout))

    def count(self) -> int:
        return len(self._rows)

    def nth(self, index: int) -> _FakeRow:
        return self._rows[index]


class _FakeTable:
    def __init__(self, rows: tuple[_FakeRow, ...], waits: list[tuple[str, float]]) -> None:
        self._rows = rows
        self._waits = waits

    def locator(self, selector: str) -> _FakeRows:
        assert selector == "tbody tr"
        return _FakeRows(self._rows, self._waits)


class _FakeTables:
    def __init__(self, tables: tuple[_FakeTable, ...]) -> None:
        self._tables = tables

    def count(self) -> int:
        return len(self._tables)

    def nth(self, index: int) -> _FakeTable:
        return self._tables[index]


class _FakeText:
    def __init__(self, texts: tuple[str, ...]) -> None:
        self._texts = texts

    def all_inner_texts(self) -> list[str]:
        return list(self._texts)


class _FakeRoleItem:
    def __init__(self, page: "_FakePage", role: str, text: str) -> None:
        self._page = page
        self._role = role
        self._text = text

    def inner_text(self) -> str:
        return self._text

    def get_attribute(self, name: str) -> str | None:
        if name == "aria-label" and self._role == "button":
            return self._text
        return None

    def click(self) -> None:
        if self._role == "button":
            self._page.expiration_menu_open = True


class _FakeRoleLocator:
    def __init__(self, page: "_FakePage", role: str, texts: tuple[str, ...]) -> None:
        self._page = page
        self._role = role
        self._texts = texts

    def count(self) -> int:
        return len(self._texts)

    def nth(self, index: int) -> _FakeRoleItem:
        return _FakeRoleItem(self._page, self._role, self._texts[index])

    def all_inner_texts(self) -> list[str]:
        return list(self._texts)

    def wait_for(self, *, state: str, timeout: float) -> None:
        assert state == "visible"
        assert timeout == 20_000.0
        if self._role == "listbox":
            assert self._page.expiration_menu_open is True


class _FakePage:
    def __init__(
        self,
        events: list[str],
        navigation_error: Exception | None = None,
        response_status: int = 200,
    ) -> None:
        self._events = events
        self._navigation_error = navigation_error
        self._response_status = response_status
        self._fixture = json.loads((FIXTURES / "current_page.json").read_text())
        self.row_waits: list[tuple[str, float]] = []
        self.table_queries: list[str] = []
        self.url: str | None = None
        self.expiration_menu_open = False

    def goto(self, url: str, *, wait_until: str, timeout: float) -> _FakeResponse:
        self.url = url
        self._events.append("page.goto")
        assert wait_until == "domcontentloaded"
        assert timeout == 20_000
        if self._navigation_error is not None:
            raise self._navigation_error
        return _FakeResponse(self._response_status)

    def locator(self, selector: str):
        if selector == "body":
            return _FakeText((self._fixture["body_text"],))
        if selector == '[data-testid="qsp-price"]':
            return _FakeText((self._fixture["quote"]["qsp_price"],))
        if selector in {
            '#quote-header-info fin-streamer[data-field="regularMarketPrice"]',
            '[data-testid="quote-header"] fin-streamer[data-field="regularMarketPrice"]',
        }:
            return _FakeText((self._fixture["quote"]["header_market_price"],))
        if "regularMarketPrice" in selector:
            return _FakeText((self._fixture["quote"]["sidebar_market_price"],))
        if selector == "table":
            self.table_queries.append(selector)
            tables = tuple(
                _FakeTable(
                    tuple(_FakeRow(tuple(cells)) for cells in table["rows"]),
                    self.row_waits,
                )
                for table in self._fixture["tables"]
            )
            return _FakeTables(tables)
        return _FakeRows((), self.row_waits)

    def get_by_role(self, role: str, name: str | None = None) -> _FakeRoleLocator:
        if role == "button":
            texts = (self._fixture["current_expiration"],)
        elif role == "listbox":
            texts = (" ".join(self._fixture["expiration_options"]),) if self.expiration_menu_open else ()
        elif role == "option":
            texts = tuple(self._fixture["expiration_options"]) if self.expiration_menu_open else ()
        else:
            texts = ()
        if name is not None:
            texts = tuple(text for text in texts if text == name)
        return _FakeRoleLocator(self, role, texts)

    def close(self) -> None:
        self._events.append("page.close")


class _FakeContext:
    def __init__(self, page: _FakePage, events: list[str]) -> None:
        self._page = page
        self._events = events

    def new_page(self) -> _FakePage:
        self._events.append("context.new_page")
        return self._page

    def close(self) -> None:
        self._events.append("context.close")


class _FakeBrowser:
    def __init__(self, context: _FakeContext, events: list[str]) -> None:
        self._context = context
        self._events = events

    def new_context(self) -> _FakeContext:
        self._events.append("browser.new_context")
        return self._context

    def close(self) -> None:
        self._events.append("browser.close")


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser, events: list[str]) -> None:
        self._browser = browser
        self._events = events

    def launch(self) -> _FakeBrowser:
        self._events.append("chromium.launch")
        return self._browser


class _FakePlaywright:
    def __init__(self, chromium: _FakeChromium, events: list[str]) -> None:
        self.chromium = chromium
        self._events = events

    def stop(self) -> None:
        self._events.append("playwright.stop")


class _FakePlaywrightManager:
    def __init__(self, playwright: _FakePlaywright | None, start_error: Exception | None = None) -> None:
        self._playwright = playwright
        self._start_error = start_error

    def start(self) -> _FakePlaywright:
        if self._start_error is not None:
            raise self._start_error
        assert self._playwright is not None
        return self._playwright


def _playwright_runtime(
    *, navigation_error: Exception | None = None, response_status: int = 200,
) -> tuple[_FakePlaywrightManager, _FakePage, list[str]]:
    events: list[str] = []
    page = _FakePage(events, navigation_error, response_status)
    context = _FakeContext(page, events)
    browser = _FakeBrowser(context, events)
    chromium = _FakeChromium(browser, events)
    return _FakePlaywrightManager(_FakePlaywright(chromium, events)), page, events


def test_playwright_reader_maps_navigation_timeout_to_page_unavailable(monkeypatch):
    runtime, _, _ = _playwright_runtime(navigation_error=TimeoutError("timed out"))
    monkeypatch.setattr(yahoo_browser_options, "_sync_playwright", lambda: runtime)
    reader = PlaywrightYahooPageReader(timeout_seconds=20.0, delay_seconds=0.0)

    result = YahooBrowserOptionsProvider(reader, clock=lambda: FIXED_TIME).fetch_current_chain("AAPL")

    assert result.snapshot is None
    assert result.capability.code == "browser_page_unavailable"


def test_playwright_reader_maps_http_429_to_browser_rate_limited(monkeypatch):
    runtime, _, _ = _playwright_runtime(response_status=429)
    monkeypatch.setattr(yahoo_browser_options, "_sync_playwright", lambda: runtime)
    reader = PlaywrightYahooPageReader(timeout_seconds=20.0, delay_seconds=0.0)

    result = YahooBrowserOptionsProvider(reader, clock=lambda: FIXED_TIME).fetch_current_chain("AAPL")

    assert result.snapshot is None
    assert result.capability.code == "browser_rate_limited"


def test_playwright_reader_maps_startup_failure_to_browser_unavailable(monkeypatch):
    runtime = _FakePlaywrightManager(None, start_error=RuntimeError("Chromium is unavailable"))
    monkeypatch.setattr(yahoo_browser_options, "_sync_playwright", lambda: runtime)
    reader = PlaywrightYahooPageReader(timeout_seconds=20.0, delay_seconds=0.0)

    result = YahooBrowserOptionsProvider(reader, clock=lambda: FIXED_TIME).fetch_current_chain("AAPL")

    assert result.snapshot is None
    assert result.capability.code == "browser_unavailable"


def test_playwright_reader_extracts_unnamed_option_tables_and_closes_resources(monkeypatch):
    runtime, page, events = _playwright_runtime()
    monkeypatch.setattr(yahoo_browser_options, "_sync_playwright", lambda: runtime)
    reader = PlaywrightYahooPageReader(timeout_seconds=20.0, delay_seconds=0.0)

    page_data = reader.read_current_page("AAPL")
    reader.close()

    assert page.url == "https://ca.finance.yahoo.com/quote/AAPL/options/"
    assert page_data.underlying_price == "$210.50"
    assert page_data.rows == _page_data().rows
    assert page.table_queries == ["table"]
    assert page.row_waits == [("visible", 20_000.0), ("visible", 20_000.0)]
    assert events == [
        "chromium.launch",
        "browser.new_context",
        "context.new_page",
        "page.goto",
        "page.close",
        "context.close",
        "browser.close",
        "playwright.stop",
    ]


def test_playwright_reader_extracts_available_expirations_from_dropdown(monkeypatch):
    runtime, _, _ = _playwright_runtime()
    monkeypatch.setattr(yahoo_browser_options, "_sync_playwright", lambda: runtime)
    reader = PlaywrightYahooPageReader(timeout_seconds=20.0, delay_seconds=0.0)

    page_data = reader.read_current_page("AAPL")

    assert page_data.available_expirations == (
        date(2026, 8, 21),
        date(2026, 8, 28),
    )


def test_playwright_reader_requests_specific_expiration_page(monkeypatch):
    runtime, page, _ = _playwright_runtime()
    monkeypatch.setattr(yahoo_browser_options, "_sync_playwright", lambda: runtime)
    reader = PlaywrightYahooPageReader(timeout_seconds=20.0, delay_seconds=0.0)

    reader.read_current_page("AAPL", expiration=date(2026, 8, 21))

    assert page.url == "https://ca.finance.yahoo.com/quote/AAPL/options/?date=1787270400"


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
        def read_current_page(
            self,
            symbol: str,
            expiration: date | None = None,
        ) -> YahooBrowserPageData:
            assert symbol == "AAPL"
            assert expiration is None
            return page_data

    result = YahooBrowserOptionsProvider(Reader(), clock=lambda: FIXED_TIME).fetch_current_chain("AAPL")

    assert result.snapshot is not None
    assert result.snapshot.collected_at == FIXED_TIME


def test_browser_page_normalizes_currency_codes_and_markers():
    page_data = YahooBrowserPageData(
        body_text="AAPL Options",
        underlying_price="CAD 210.50",
        rows=(
            YahooBrowserOptionRow(
                "call",
                (
                    "AAPL260821C00200000",
                    "2026-07-31 10:00 AM EDT",
                    "C$200.00",
                    "C$12.50",
                    "CAD 11.90",
                    "12.10 CAD",
                    "+C$0.30",
                    "+2.46%",
                    "1,234",
                    "5,678",
                    "31.25%",
                ),
            ),
        ),
    )

    result = parse_yahoo_browser_page(page_data, "AAPL", FIXED_TIME)

    assert result.snapshot is not None
    assert result.snapshot.underlying_price == 210.50
    assert result.snapshot.contracts[0].strike == 200.0
    assert result.snapshot.contracts[0].bid == 11.90
    assert result.snapshot.contracts[0].ask == 12.10


def test_browser_page_rejects_malformed_currency_number_as_partial_data():
    valid_page = _page_data()
    malformed_row = YahooBrowserOptionRow(
        "call",
        (
            "AAPL260821C00210000",
            "2026-07-31 10:00 AM EDT",
            "CAD not-a-number",
            "CAD 12.50",
            "CAD 11.90",
            "CAD 12.10",
            "+CAD 0.30",
            "+2.46%",
            "1,234",
            "5,678",
            "31.25%",
        ),
    )
    page_data = YahooBrowserPageData(
        body_text=valid_page.body_text,
        underlying_price="C$210.50",
        rows=(*valid_page.rows, malformed_row),
    )

    result = parse_yahoo_browser_page(page_data, "AAPL", FIXED_TIME)

    assert result.snapshot is not None
    assert result.capability.code == "partial_data"
    assert len(result.snapshot.contracts) == 2
