from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from earnings_export.credentials import DEFAULT_CREDENTIALS_PATH, load_alpha_vantage_api_key


@dataclass(frozen=True)
class AnalysisSettings:
    output_dir: Path
    spread_limit: float
    provider_order: tuple[str, ...]
    alpha_vantage_api_key: str | None


def load_analysis_settings(environ: Mapping[str, str], cwd: Path) -> AnalysisSettings:
    spread_limit = float(environ.get("EARNINGS_OPTIONS_MAX_SPREAD_PCT", "0.10"))
    if not 0 < spread_limit <= 1:
        raise ValueError("spread_limit must be greater than 0 and no greater than 1")

    return AnalysisSettings(
        output_dir=cwd / environ.get("EARNINGS_OPTIONS_OUTPUT_DIR", "exports/earnings-options"),
        spread_limit=spread_limit,
        provider_order=("alpha_vantage", "yahoo"),
        alpha_vantage_api_key=load_alpha_vantage_api_key(environ, DEFAULT_CREDENTIALS_PATH),
    )
