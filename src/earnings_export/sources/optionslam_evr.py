from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Callable

import requests


OPTIONSLAM_URL = "https://www.optionslam.com/{symbol}/"


@dataclass(frozen=True)
class EvrResult:
    value: float | None
    source_url: str
    status: str
    collected_at: datetime


def parse_optionslam_evr(
    html: str, symbol: str, source_url: str, collected_at: datetime,
) -> EvrResult:
    lowered = html.lower()
    if "sign in" in lowered or "membership" in lowered:
        return EvrResult(None, source_url, "authentication_required", collected_at)

    match = re.search(r"EVR[^0-9]*([0-9]+(?:\.[0-9]+)?)", html, re.IGNORECASE)
    if match is None:
        return EvrResult(None, source_url, "not_found", collected_at)
    return EvrResult(float(match.group(1)), source_url, "available", collected_at)


class OptionSlamEvrProvider:
    name = "optionslam"

    def __init__(
        self,
        session: requests.Session,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._session = session
        self._clock = clock

    def fetch_public_evr(self, symbol: str) -> EvrResult:
        source_url = OPTIONSLAM_URL.format(symbol=symbol.strip().lower())
        collected_at = self._clock()
        try:
            response = self._session.get(
                source_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
                allow_redirects=False,
            )
            response.raise_for_status()
        except requests.RequestException:
            return EvrResult(None, source_url, "request_failed", collected_at)
        return parse_optionslam_evr(response.text, symbol, source_url, collected_at)
