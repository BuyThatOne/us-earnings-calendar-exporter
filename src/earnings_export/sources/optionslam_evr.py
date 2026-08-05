from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Callable

import requests


OPTIONSLAM_HOME_URL = "https://www.optionslam.com/"
OPTIONSLAM_URL = "https://www.optionslam.com/earnings/stocks/{symbol}"
OPTIONSLAM_LOGIN_URL = "https://www.optionslam.com/accounts/os_login/"


@dataclass(frozen=True)
class EvrResult:
    value: float | None
    source_url: str
    status: str
    collected_at: datetime


def parse_optionslam_evr(
    html: str, symbol: str, source_url: str, collected_at: datetime,
) -> EvrResult:
    if _requires_authentication(html):
        return EvrResult(None, source_url, "authentication_required", collected_at)

    patterns = (
        r"EVR:\s*</td>\s*<td>\s*([0-9]+(?:\.[0-9]+)?)",
        r"Expected Volatility Range\s*\(EVR\)\s*:\s*([0-9]+(?:\.[0-9]+)?)%",
        r"EVR[^0-9]*([0-9]+(?:\.[0-9]+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match is not None:
            return EvrResult(float(match.group(1)), source_url, "available", collected_at)
    if match is None:
        return EvrResult(None, source_url, "not_found", collected_at)
    return EvrResult(None, source_url, "not_found", collected_at)


def diagnose_optionslam_response(
    html: str,
    status_code: int,
    symbol: str,
    source_url: str,
    collected_at: datetime,
    location: str | None = None,
    response_url: str | None = None,
) -> EvrResult:
    if _is_login_redirect(status_code, location, response_url):
        return EvrResult(None, source_url, "authentication_required", collected_at)
    parsed = parse_optionslam_evr(html, symbol, source_url, collected_at)
    if parsed.status == "authentication_required":
        return parsed
    if status_code >= 400:
        return EvrResult(None, source_url, "request_failed", collected_at)
    return parsed


class OptionSlamEvrProvider:
    name = "optionslam"

    def __init__(
        self,
        session: requests.Session,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._clock = clock
        self._username = username
        self._password = password
        self._authenticated = False
        self._login_attempted = False

    def _fetch_symbol(self, symbol: str, *, public: bool = False) -> EvrResult:
        source_url = OPTIONSLAM_URL.format(symbol=symbol.strip().upper())
        collected_at = self._clock()
        try:
            response = self._get_symbol(source_url, public=public)
        except requests.RequestException:
            return EvrResult(None, source_url, "request_failed", collected_at)
        return diagnose_optionslam_response(
            response.text,
            getattr(response, "status_code", 200),
            symbol,
            source_url,
            collected_at,
            getattr(response, "headers", {}).get("Location"),
            getattr(response, "url", None),
        )

    def _get_symbol(self, source_url: str, *, public: bool):
        request_kwargs = {
            "headers": {"User-Agent": "Mozilla/5.0"},
            "timeout": 30,
            "allow_redirects": False,
        }
        cookies = getattr(self._session, "cookies", None)
        if not public or cookies is None:
            return self._session.get(source_url, **request_kwargs)

        authenticated_cookies = cookies.copy()
        cookies.clear()
        try:
            return self._session.get(source_url, **request_kwargs)
        finally:
            cookies.update(authenticated_cookies)

    def _login(self) -> bool:
        if self._authenticated:
            return True
        if self._login_attempted:
            return False
        self._login_attempted = True
        if not self._username or not self._password:
            return False

        try:
            login_page = self._session.get(
                OPTIONSLAM_HOME_URL,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            csrf_match = re.search(
                r'name="csrfmiddlewaretoken"\s+value="([^"]+)"',
                login_page.text,
            )
            next_match = re.search(r'name="next"\s+value="([^"]+)"', login_page.text)
            response = self._session.post(
                OPTIONSLAM_LOGIN_URL,
                data={
                    "username": self._username,
                    "password": self._password,
                    "csrfmiddlewaretoken": csrf_match.group(1) if csrf_match else "",
                    "next": next_match.group(1) if next_match else "/",
                },
                headers={
                    "Referer": OPTIONSLAM_HOME_URL,
                    "User-Agent": "Mozilla/5.0",
                },
                timeout=30,
                allow_redirects=False,
            )
        except requests.RequestException:
            return False

        if getattr(response, "status_code", 200) >= 400:
            return False
        if _requires_authentication(response.text):
            return False

        self._authenticated = True
        return True

    def fetch_public_evr(self, symbol: str) -> EvrResult:
        public_result = self._fetch_symbol(symbol, public=True)
        if public_result.status == "available":
            return public_result
        if public_result.status != "authentication_required":
            return public_result
        if not self._username or not self._password:
            return public_result
        if not self._login():
            return EvrResult(
                None,
                public_result.source_url,
                "login_failed",
                public_result.collected_at,
            )
        return self._fetch_symbol(symbol)


def _requires_authentication(html: str) -> bool:
    lowered = html.lower()
    return (
        "please login first" in lowered
        or "please log in first" in lowered
        or "sign in to continue" in lowered
        or "please sign in" in lowered
    )


def _is_login_redirect(
    status_code: int, location: str | None, response_url: str | None,
) -> bool:
    if not 300 <= status_code < 400:
        return False
    return any(value and "/login" in value.lower() for value in (location, response_url))
