from __future__ import annotations

from pathlib import Path
from typing import Mapping


DEFAULT_CREDENTIALS_PATH = Path.home() / ".config" / "earnings-options-research" / "credentials.env"


def load_alpha_vantage_api_key(
    environ: Mapping[str, str], credentials_path: Path = DEFAULT_CREDENTIALS_PATH
) -> str | None:
    if environ.get("ALPHAVANTAGE_API_KEY"):
        return environ["ALPHAVANTAGE_API_KEY"]
    if not credentials_path.exists():
        return None
    if credentials_path.stat().st_mode & 0o077:
        raise ValueError("credentials file must be owner-only")
    for line in credentials_path.read_text().splitlines():
        if line.startswith("ALPHAVANTAGE_API_KEY="):
            return line.partition("=")[2].strip() or None
    return None
