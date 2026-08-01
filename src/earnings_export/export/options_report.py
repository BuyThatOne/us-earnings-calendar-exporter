from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Mapping, Sequence

from earnings_export.options_models import (
    OptionChainSnapshot,
    OptionContract,
    OptionGreeks,
    ProviderCapability,
    StrategyCandidate,
)


_SCHEMA_VERSION = 1
_CREDENTIAL_QUERY_PARAMETER = re.compile(
    r"\b("
    r"api[_-]?key|key|token|access[_-]?token|client[_-]?secret|password|signature"
    r")=([^&#\s]*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AnalysisRunResult:
    run_at: datetime
    candidates: tuple[StrategyCandidate, ...]
    exclusions: Mapping[str, int]
    capabilities: Sequence[ProviderCapability]
    snapshots: Sequence[OptionChainSnapshot]


@dataclass(frozen=True)
class OptionsArtifactPaths:
    markdown_path: Path
    json_path: Path
    snapshots_path: Path


def build_run_dir(output_dir: Path, run_at: datetime) -> Path:
    return output_dir / run_at.date().isoformat()


def _redact(value: str | None) -> str | None:
    if value is None:
        return None
    return _CREDENTIAL_QUERY_PARAMETER.sub(r"\1=[REDACTED]", value)


def _datetime_value(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _date_value(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _greeks_dict(greeks: OptionGreeks | None) -> dict[str, float | None] | None:
    if greeks is None:
        return None
    return {
        "delta": greeks.delta,
        "gamma": greeks.gamma,
        "theta": greeks.theta,
        "vega": greeks.vega,
        "rho": greeks.rho,
    }


def _contract_dict(contract: OptionContract) -> dict[str, object]:
    return {
        "option_symbol": contract.option_symbol,
        "option_type": contract.option_type,
        "expiration": _date_value(contract.expiration),
        "strike": contract.strike,
        "bid": contract.bid,
        "ask": contract.ask,
        "midpoint": contract.midpoint,
        "bid_ask_spread_pct": contract.bid_ask_spread_pct,
        "implied_volatility": contract.implied_volatility,
        "greeks": _greeks_dict(contract.greeks),
        "open_interest": contract.open_interest,
        "quote_timestamp": _datetime_value(contract.quote_timestamp),
    }


def _capability_dict(capability: ProviderCapability) -> dict[str, object]:
    return {
        "provider": capability.provider,
        "available": capability.available,
        "code": capability.code,
        "supported_fields": list(capability.supported_fields),
        "message": _redact(capability.message),
    }


def _candidate_dict(candidate: StrategyCandidate) -> dict[str, object]:
    return {
        "ticker": candidate.ticker,
        "earnings_date": candidate.earnings_date.isoformat(),
        "strategy_type": candidate.strategy_type,
        "defined_risk": candidate.defined_risk,
        "legs": [_contract_dict(leg) for leg in candidate.legs],
        "entry_limit": candidate.entry_limit,
        "maximum_loss": candidate.maximum_loss,
        "implied_move_pct": candidate.implied_move_pct,
        "historical_median_move_pct": candidate.historical_median_move_pct,
        "historical_iv_change_pct": candidate.historical_iv_change_pct,
        "warnings": [_redact(warning) for warning in candidate.warnings],
        "rationale": _redact(candidate.rationale),
        "execution_status": candidate.execution_status,
    }


def _snapshot_dict(snapshot: OptionChainSnapshot) -> dict[str, object]:
    return {
        "symbol": snapshot.symbol,
        "collected_at": _datetime_value(snapshot.collected_at),
        "provider": snapshot.provider,
        "provider_capabilities": [
            _capability_dict(capability) for capability in snapshot.provider_capabilities
        ],
        "underlying_price": snapshot.underlying_price,
        "contracts": [_contract_dict(contract) for contract in snapshot.contracts],
        "data_quality_flags": list(snapshot.data_quality_flags),
    }


def _provider_provenance(result: AnalysisRunResult) -> list[str]:
    providers = {capability.provider for capability in result.capabilities}
    providers.update(snapshot.provider for snapshot in result.snapshots)
    return sorted(providers)


def _warnings(result: AnalysisRunResult) -> list[str]:
    return sorted({_redact(warning) for candidate in result.candidates for warning in candidate.warnings})


def _order_intents_payload(result: AnalysisRunResult) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "run_at": _datetime_value(result.run_at),
        "execution_status": "research_only",
        "provider_provenance": _provider_provenance(result),
        "capabilities": [_capability_dict(capability) for capability in result.capabilities],
        "warnings": _warnings(result),
        "exclusions": dict(sorted(result.exclusions.items())),
        "candidates": [_candidate_dict(candidate) for candidate in result.candidates],
    }


def _snapshots_payload(result: AnalysisRunResult) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "run_at": _datetime_value(result.run_at),
        "snapshots": [_snapshot_dict(snapshot) for snapshot in result.snapshots],
    }


def _markdown_cell(value: object) -> str:
    return _redact(str(value)).replace("|", "\\|").replace("\n", "<br>")


def _markdown(result: AnalysisRunResult) -> str:
    lines = [
        "# Earnings Options Research",
        "",
        f"Run at: {_datetime_value(result.run_at)}",
        "",
        "## Provider Capabilities",
        "",
        "| Provider | Available | Code | Supported fields | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for capability in result.capabilities:
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_cell(capability.provider),
                    _markdown_cell(capability.available),
                    _markdown_cell(capability.code),
                    _markdown_cell(", ".join(capability.supported_fields)),
                    _markdown_cell(capability.message or ""),
                )
            )
            + " |"
        )

    lines.extend(("", "## Candidates", ""))
    if not result.candidates:
        lines.append("No eligible candidate was found for this research run.")
    else:
        for candidate in result.candidates:
            lines.extend(
                (
                    f"### {_markdown_cell(candidate.ticker)} {_markdown_cell(candidate.strategy_type)}",
                    "",
                    f"Execution status: {_markdown_cell(candidate.execution_status)}",
                    f"Rationale: {_markdown_cell(candidate.rationale)}",
                    f"Warnings: {_markdown_cell('; '.join(candidate.warnings) or 'None')}",
                    "",
                )
            )
    return "\n".join(lines) + "\n"


def _write_atomically(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary_file:
        temporary_file.write(content)
        temporary_path = Path(temporary_file.name)
    try:
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _serialize_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n"


def write_options_artifacts(result: AnalysisRunResult, output_dir: Path) -> OptionsArtifactPaths:
    if any(candidate.execution_status != "research_only" for candidate in result.candidates):
        raise ValueError("All candidate execution_status values must be research_only")

    order_intents_json = _serialize_json(_order_intents_payload(result))
    snapshots_json = _serialize_json(_snapshots_payload(result))
    run_dir = build_run_dir(output_dir, result.run_at)
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = OptionsArtifactPaths(
        markdown_path=run_dir / "earnings_options_research.md",
        json_path=run_dir / "earnings_options_order_intents.json",
        snapshots_path=run_dir / "option_chain_snapshots.json",
    )
    _write_atomically(paths.markdown_path, _markdown(result))
    _write_atomically(paths.json_path, order_intents_json)
    _write_atomically(paths.snapshots_path, snapshots_json)
    return paths
