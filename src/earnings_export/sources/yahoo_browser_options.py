from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
import re
import time
from typing import Callable, Protocol

from earnings_export.options_models import OptionChainSnapshot, OptionContract, ProviderCapability
from earnings_export.sources.options_provider import ProviderResult


SUPPORTED_FIELDS = ("bid", "ask", "implied_volatility", "open_interest")
_CONTRACT_SYMBOL = re.compile(r"(?P<root>.+?)(?P<expiration>\d{6})(?P<kind>[CP])\d{8}$")
_MISSING_VALUE = {"", "-", "none"}
_RATE_LIMIT_MARKERS = ("rate limit", "too many requests", "try again later")
_CURRENCY_PREFIX = re.compile(
    r"^(?P<sign>[+-]?)\s*(?:(?:[A-Z]{1,3})?[$€£¥₹₩₺₽₴₦₱]\s*|[A-Z]{3}\s+)",
    re.IGNORECASE,
)
_CURRENCY_SUFFIX = re.compile(
    r"\s*(?:(?:[A-Z]{1,3})?[$€£¥₹₩₺₽₴₦₱]|[A-Z]{3})$",
    re.IGNORECASE,
)


def _sync_playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright()


@dataclass(frozen=True)
class YahooBrowserOptionRow:
    option_type: str
    cells: tuple[str, ...]


@dataclass(frozen=True)
class YahooBrowserPageData:
    body_text: str
    underlying_price: str | None
    rows: tuple[YahooBrowserOptionRow, ...]


class YahooBrowserPageReader(Protocol):
    def read_current_page(self, symbol: str) -> YahooBrowserPageData:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class _BrowserPageUnavailableError(RuntimeError):
    pass


class _BrowserUnavailableError(RuntimeError):
    pass


class PlaywrightYahooPageReader:
    _QUOTE_SELECTORS = (
        'fin-streamer[data-field="regularMarketPrice"]',
        '[data-testid="qsp-price"]',
    )
    _ROW_SELECTORS = (
        ("call", "table.calls tbody tr"),
        ("put", "table.puts tbody tr"),
    )

    def __init__(self, timeout_seconds: float, delay_seconds: float) -> None:
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        if not isfinite(delay_seconds) or delay_seconds < 0:
            raise ValueError("delay_seconds must be non-negative and finite")
        self._timeout_seconds = timeout_seconds
        self._delay_seconds = delay_seconds
        self._playwright = None
        self._browser = None
        self._context = None
        self._last_read_at: float | None = None

    def _start(self) -> None:
        if self._context is not None:
            return
        try:
            self._playwright = _sync_playwright().start()
            self._browser = self._playwright.chromium.launch()
            self._context = self._browser.new_context()
        except Exception as error:
            self.close()
            raise _BrowserUnavailableError("Playwright Chromium is unavailable") from error

    @staticmethod
    def _visible_text(page, selector: str) -> str | None:
        try:
            texts = page.locator(selector).all_inner_texts()
        except Exception:
            return None
        return next((text.strip() for text in texts if text.strip()), None)

    @classmethod
    def _extract_rows(cls, page, option_type: str, selector: str) -> tuple[YahooBrowserOptionRow, ...]:
        try:
            rows = page.locator(selector)
            extracted = []
            for index in range(rows.count()):
                cells = tuple(text.strip() for text in rows.nth(index).locator("td").all_inner_texts())
                if cells:
                    extracted.append(YahooBrowserOptionRow(option_type=option_type, cells=cells))
            return tuple(extracted)
        except Exception:
            return ()

    def read_current_page(self, symbol: str) -> YahooBrowserPageData:
        self._start()
        if self._last_read_at is not None and self._delay_seconds:
            remaining_delay = self._delay_seconds - (time.monotonic() - self._last_read_at)
            if remaining_delay > 0:
                time.sleep(remaining_delay)

        page = None
        try:
            page = self._context.new_page()
            response = page.goto(
                f"https://ca.finance.yahoo.com/quote/{symbol}/options/",
                wait_until="domcontentloaded",
                timeout=self._timeout_seconds * 1_000,
            )
            if response is None or not response.ok:
                raise _BrowserPageUnavailableError("Yahoo options page is unavailable")

            body_text = self._visible_text(page, "body")
            if body_text is None:
                raise _BrowserPageUnavailableError("Yahoo options page has no visible content")
            underlying_price = next(
                (text for selector in self._QUOTE_SELECTORS if (text := self._visible_text(page, selector))),
                None,
            )
            rows = tuple(
                row
                for option_type, selector in self._ROW_SELECTORS
                for row in self._extract_rows(page, option_type, selector)
            )
            return YahooBrowserPageData(
                body_text=body_text,
                underlying_price=underlying_price,
                rows=rows,
            )
        except _BrowserPageUnavailableError:
            raise
        except Exception as error:
            raise _BrowserPageUnavailableError("Yahoo options page could not be read") from error
        finally:
            self._last_read_at = time.monotonic()
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    def close(self) -> None:
        for attribute, method_name in (
            ("_context", "close"),
            ("_browser", "close"),
            ("_playwright", "stop"),
        ):
            resource = getattr(self, attribute)
            if resource is None:
                continue
            try:
                getattr(resource, method_name)()
            except Exception:
                pass
            finally:
                setattr(self, attribute, None)


def _is_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in _MISSING_VALUE)


def _parse_number(value: object, *, percent: bool = False) -> float | None:
    if _is_missing(value):
        return None
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace(",", "")
    cleaned = cleaned.replace("%", "")
    cleaned = _CURRENCY_PREFIX.sub(r"\g<sign>", cleaned)
    cleaned = _CURRENCY_SUFFIX.sub("", cleaned)
    try:
        parsed = float(cleaned)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(parsed):
        return None
    return parsed / 100 if percent else parsed


def _parse_expiration(option_symbol: str, option_type: str) -> date | None:
    match = _CONTRACT_SYMBOL.fullmatch(option_symbol)
    if match is None:
        return None
    expected_kind = "C" if option_type == "call" else "P" if option_type == "put" else ""
    if match.group("kind") != expected_kind:
        return None
    try:
        return datetime.strptime(match.group("expiration"), "%y%m%d").date()
    except ValueError:
        return None


def _parse_contract(row: YahooBrowserOptionRow) -> OptionContract | None:
    if row.option_type not in ("call", "put") or len(row.cells) < 11:
        return None
    option_symbol = row.cells[0].strip()
    expiration = _parse_expiration(option_symbol, row.option_type)
    strike = _parse_number(row.cells[2])
    bid = _parse_number(row.cells[4])
    ask = _parse_number(row.cells[5])
    implied_volatility = _parse_number(row.cells[10], percent=True)
    open_interest = _parse_number(row.cells[9])
    numeric_cells = (row.cells[2], row.cells[4], row.cells[5], row.cells[9], row.cells[10])
    parsed_values = (strike, bid, ask, open_interest, implied_volatility)
    if expiration is None or strike is None or strike <= 0:
        return None
    if any(not _is_missing(cell) and value is None for cell, value in zip(numeric_cells, parsed_values)):
        return None

    bid = bid or 0.0
    ask = ask or 0.0
    midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 else None
    return OptionContract(
        option_symbol=option_symbol,
        option_type=row.option_type,
        expiration=expiration,
        strike=strike,
        bid=bid,
        ask=ask,
        midpoint=midpoint,
        bid_ask_spread_pct=(ask - bid) / midpoint if midpoint else None,
        implied_volatility=implied_volatility,
        open_interest=int(open_interest) if open_interest is not None else None,
    )


def parse_yahoo_browser_page(
    page_data: YahooBrowserPageData, symbol: str, collected_at: datetime,
) -> ProviderResult:
    if any(marker in page_data.body_text.lower() for marker in _RATE_LIMIT_MARKERS):
        return ProviderResult.unavailable("yahoo_browser", "browser_rate_limited")

    underlying_price = _parse_number(page_data.underlying_price)
    if underlying_price is None or underlying_price <= 0:
        return ProviderResult.unavailable("yahoo_browser", "browser_parse_failed")

    contracts = []
    invalid_rows = 0
    for row in page_data.rows:
        contract = _parse_contract(row)
        if contract is None:
            invalid_rows += 1
            continue
        contracts.append(contract)
    if not contracts:
        return ProviderResult.unavailable("yahoo_browser", "browser_parse_failed")

    capability = ProviderCapability(
        provider="yahoo_browser",
        available=True,
        code="partial_data" if invalid_rows else "available",
        supported_fields=SUPPORTED_FIELDS,
    )
    return ProviderResult(
        snapshot=OptionChainSnapshot(
            symbol=symbol,
            collected_at=collected_at,
            provider="yahoo_browser",
            provider_capabilities=(capability,),
            underlying_price=underlying_price,
            contracts=tuple(contracts),
            data_quality_flags=("partial_contract_data",) if invalid_rows else (),
        ),
        capability=capability,
    )


class YahooBrowserOptionsProvider:
    name = "yahoo_browser"

    def __init__(
        self,
        reader: YahooBrowserPageReader,
        clock: Callable[[], datetime],
    ) -> None:
        self._reader = reader
        self._clock = clock

    def fetch_current_chain(self, symbol: str) -> ProviderResult:
        try:
            page_data = self._reader.read_current_page(symbol)
        except _BrowserPageUnavailableError:
            return ProviderResult.unavailable(self.name, "browser_page_unavailable")
        except _BrowserUnavailableError:
            return ProviderResult.unavailable(self.name, "browser_unavailable")
        return parse_yahoo_browser_page(page_data, symbol, self._clock())

    def fetch_historical_chain(self, symbol: str, as_of: date) -> ProviderResult:
        return ProviderResult.unavailable(self.name, "unsupported")

    def close(self) -> None:
        self._reader.close()
