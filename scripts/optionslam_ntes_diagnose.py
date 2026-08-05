from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import requests

from earnings_export.credentials import load_optionslam_credentials
from earnings_export.sources.optionslam_evr import (
    OPTIONSLAM_URL,
    OptionSlamEvrProvider,
    diagnose_optionslam_response,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print sanitized OptionSlam NTES diagnostics without exposing secrets or HTML."
    )
    parser.add_argument("--fixture", type=Path, help="Local HTML fixture path for offline diagnosis.")
    parser.add_argument("--symbol", default="NTES", help="Ticker symbol to diagnose.")
    parser.add_argument(
        "--status-code",
        type=int,
        default=403,
        help="HTTP status code to pair with --fixture input. Defaults to 403.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch the symbol with current local credentials instead of using a fixture.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    symbol = args.symbol.upper()

    if args.live:
        return _run_live(symbol)
    if args.fixture is None:
        parser.error("offline mode requires --fixture PATH unless --live is set")
    return _run_fixture(args.fixture, symbol, args.status_code)


def _run_fixture(fixture_path: Path, symbol: str, status_code: int) -> int:
    source_url = OPTIONSLAM_URL.format(symbol=symbol.lower())
    result = diagnose_optionslam_response(
        fixture_path.read_text(),
        status_code,
        symbol,
        source_url,
        datetime.now(timezone.utc),
    )
    print(
        f"symbol={symbol} mode=fixture http_status={status_code} "
        f"final_url={source_url} result_status={result.status}"
    )
    return 0


def _run_live(symbol: str) -> int:
    session = requests.Session()
    username, password = load_optionslam_credentials({})
    provider = OptionSlamEvrProvider(
        session=session,
        username=username,
        password=password,
    )
    provider._login()
    source_url = OPTIONSLAM_URL.format(symbol=symbol.lower())
    response = session.get(
        source_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
        allow_redirects=False,
    )
    result = diagnose_optionslam_response(
        response.text,
        getattr(response, "status_code", 200),
        symbol,
        source_url,
        datetime.now(timezone.utc),
    )
    final_url = getattr(response, "url", source_url)
    print(
        f"symbol={symbol} mode=live http_status={getattr(response, 'status_code', 200)} "
        f"final_url={final_url} result_status={result.status}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
