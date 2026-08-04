from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Mapping

from earnings_export.credentials import DEFAULT_CREDENTIALS_PATH, load_alpha_vantage_api_key


@dataclass(frozen=True)
class AnalysisSettings:
    output_dir: Path
    spread_limit: float
    provider_order: tuple[str, ...]
    alpha_vantage_api_key: str | None
    browser_timeout_seconds: float = 20.0
    browser_delay_seconds: float = 1.0


def _browser_timing(environ: Mapping[str, str], name: str, default: str, *, positive: bool) -> float:
    field_name = "browser_timeout_seconds" if positive else "browser_delay_seconds"
    try:
        value = float(environ.get(name, default))
    except ValueError as error:
        raise ValueError(f"{field_name} must be a finite number") from error
    if not isfinite(value) or (value <= 0 if positive else value < 0):
        comparison = "greater than 0" if positive else "greater than or equal to 0"
        raise ValueError(f"{field_name} must be finite and {comparison}")
    return value


def load_analysis_settings(environ: Mapping[str, str], cwd: Path) -> AnalysisSettings:
    spread_limit = float(environ.get("EARNINGS_OPTIONS_MAX_SPREAD_PCT", "0.10"))
    if not 0 < spread_limit <= 1:
        raise ValueError("spread_limit must be greater than 0 and no greater than 1")
    browser_timeout_seconds = _browser_timing(
        environ,
        "EARNINGS_OPTIONS_BROWSER_TIMEOUT_SECONDS",
        "20.0",
        positive=True,
    )
    browser_delay_seconds = _browser_timing(
        environ,
        "EARNINGS_OPTIONS_BROWSER_DELAY_SECONDS",
        "1.0",
        positive=False,
    )

    return AnalysisSettings(
        output_dir=cwd / environ.get("EARNINGS_OPTIONS_OUTPUT_DIR", "exports/earnings-options"),
        spread_limit=spread_limit,
        provider_order=("alpha_vantage", "yahoo", "yahoo_browser"),
        alpha_vantage_api_key=load_alpha_vantage_api_key(environ, DEFAULT_CREDENTIALS_PATH),
        browser_timeout_seconds=browser_timeout_seconds,
        browser_delay_seconds=browser_delay_seconds,
    )
