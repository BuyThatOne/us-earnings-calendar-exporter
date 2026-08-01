import json
from datetime import date, datetime, timezone

import pytest

from earnings_export.export.options_report import (
    AnalysisRunResult,
    build_run_dir,
    write_options_artifacts,
)
from earnings_export.options_models import (
    OptionChainSnapshot,
    OptionContract,
    ProviderCapability,
    StrategyCandidate,
)


FIXED_TIME = datetime(2026, 7, 31, 14, 30, tzinfo=timezone.utc)


def empty_run(run_at: datetime) -> AnalysisRunResult:
    return AnalysisRunResult(
        run_at=run_at,
        candidates=(),
        exclusions={"missing_liquid_chain": 2},
        capabilities=(
            ProviderCapability(
                provider="yahoo",
                available=True,
                code="available",
                supported_fields=("current_chain",),
            ),
        ),
        snapshots=(),
    )


def run_with_provider_detail(message: str) -> AnalysisRunResult:
    contract = OptionContract(
        option_symbol="AAPL260807C00200000",
        option_type="call",
        expiration=date(2026, 8, 7),
        strike=200.0,
        bid=4.2,
        ask=4.6,
        quote_timestamp=FIXED_TIME,
    )
    capability = ProviderCapability(
        provider="alpha_vantage",
        available=False,
        code="request_failed",
        message=message,
    )
    candidate = StrategyCandidate(
        ticker="AAPL",
        earnings_date=date(2026, 8, 6),
        strategy_type="iron_condor",
        defined_risk=True,
        legs=(contract,),
        entry_limit=1.25,
        maximum_loss=375.0,
        implied_move_pct=0.05,
        historical_median_move_pct=0.04,
        historical_iv_change_pct=None,
        warnings=("Review provider response.",),
        rationale="Fixture candidate.",
    )
    snapshot = OptionChainSnapshot(
        symbol="AAPL",
        collected_at=FIXED_TIME,
        provider="alpha_vantage",
        provider_capabilities=(capability,),
        underlying_price=198.0,
        contracts=(contract,),
        data_quality_flags=("partial_data",),
    )
    return AnalysisRunResult(
        run_at=FIXED_TIME,
        candidates=(candidate,),
        exclusions={"missing_history": 1},
        capabilities=(capability,),
        snapshots=(snapshot,),
    )


def test_empty_run_writes_markdown_and_json_with_no_candidates(tmp_path):
    paths = write_options_artifacts(empty_run(FIXED_TIME), tmp_path)

    assert paths.markdown_path.parent == tmp_path / "2026-07-31"
    assert paths.markdown_path.read_text().find("No eligible candidate was found") >= 0
    payload = json.loads(paths.json_path.read_text())
    assert payload["schema_version"] == 1
    assert payload["execution_status"] == "research_only"
    assert payload["candidates"] == []
    assert payload["exclusions"] == {"missing_liquid_chain": 2}
    assert "| Provider | Available | Code | Supported fields | Message |" in paths.markdown_path.read_text()
    assert json.loads(paths.snapshots_path.read_text()) == {
        "schema_version": 1,
        "run_at": "2026-07-31T14:30:00+00:00",
        "snapshots": [],
    }


def test_artifacts_serialize_provenance_capability_status_and_candidate_warnings(tmp_path):
    paths = write_options_artifacts(run_with_provider_detail("temporary failure"), tmp_path)

    order_intents = json.loads(paths.json_path.read_text())
    snapshot_payload = json.loads(paths.snapshots_path.read_text())

    assert order_intents["provider_provenance"] == ["alpha_vantage"]
    assert order_intents["capabilities"] == [
        {
            "provider": "alpha_vantage",
            "available": False,
            "code": "request_failed",
            "supported_fields": [],
            "message": "temporary failure",
        }
    ]
    assert order_intents["candidates"][0]["warnings"] == ["Review provider response."]
    assert snapshot_payload["snapshots"][0]["contracts"][0]["expiration"] == "2026-08-07"


@pytest.mark.parametrize(
    ("credential_parameter", "credential_value"),
    (
        ("key", "key-secret"),
        ("token", "token-secret"),
        ("client_secret", "client-secret"),
        ("password", "password-secret"),
        ("signature", "signature-secret"),
    ),
)
def test_artifacts_redact_credential_query_parameter_values(
    tmp_path, credential_parameter, credential_value
):
    paths = write_options_artifacts(
        run_with_provider_detail(f"https://provider.example/api?{credential_parameter}={credential_value}"),
        tmp_path,
    )

    for path in (paths.markdown_path, paths.json_path, paths.snapshots_path):
        assert credential_value not in path.read_text()


def test_non_research_candidate_is_rejected_before_artifact_creation(tmp_path):
    run = run_with_provider_detail("temporary failure")
    candidate = run.candidates[0]
    unsafe_run = AnalysisRunResult(
        run_at=run.run_at,
        candidates=(
            StrategyCandidate(
                ticker=candidate.ticker,
                earnings_date=candidate.earnings_date,
                strategy_type=candidate.strategy_type,
                defined_risk=candidate.defined_risk,
                legs=candidate.legs,
                entry_limit=candidate.entry_limit,
                maximum_loss=candidate.maximum_loss,
                implied_move_pct=candidate.implied_move_pct,
                historical_median_move_pct=candidate.historical_median_move_pct,
                historical_iv_change_pct=candidate.historical_iv_change_pct,
                warnings=candidate.warnings,
                rationale=candidate.rationale,
                execution_status="approved",
            ),
        ),
        exclusions=run.exclusions,
        capabilities=run.capabilities,
        snapshots=run.snapshots,
    )

    with pytest.raises(ValueError, match="research_only"):
        write_options_artifacts(unsafe_run, tmp_path)

    assert not build_run_dir(tmp_path, FIXED_TIME).exists()


def test_build_run_dir_uses_the_run_date(tmp_path):
    assert build_run_dir(tmp_path, FIXED_TIME) == tmp_path / "2026-07-31"
