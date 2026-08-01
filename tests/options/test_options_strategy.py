from dataclasses import replace
from datetime import date, datetime, timezone

from earnings_export.options_models import EarningsMoveHistory, OptionChainSnapshot, OptionContract
from earnings_export.options_strategy import build_ranked_candidates, contract_is_liquid, spread_pct


EARNINGS_DATE = date(2026, 8, 6)
FRONT_EXPIRATION = date(2026, 8, 7)
BACK_EXPIRATION = date(2026, 8, 14)


def _contract(
    option_type: str,
    strike: float,
    midpoint: float,
    expiration: date = FRONT_EXPIRATION,
) -> OptionContract:
    return OptionContract(
        option_symbol=f"AAPL-{expiration}-{option_type}-{strike}",
        option_type=option_type,
        expiration=expiration,
        strike=strike,
        bid=midpoint * 0.96,
        ask=midpoint * 1.04,
        midpoint=midpoint,
    )


def _chain() -> OptionChainSnapshot:
    contracts = (
        _contract("put", 90.0, 1.5),
        _contract("put", 95.0, 3.0),
        _contract("put", 100.0, 4.0),
        _contract("call", 100.0, 4.0),
        _contract("call", 105.0, 3.0),
        _contract("call", 110.0, 1.5),
        _contract("call", 100.0, 5.5, BACK_EXPIRATION),
    )
    return OptionChainSnapshot(
        symbol="AAPL",
        collected_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
        provider="test",
        underlying_price=100.0,
        contracts=contracts,
    )


def _history() -> EarningsMoveHistory:
    return EarningsMoveHistory(
        one_day_post_earnings_moves=(0.04, 0.06, 0.08),
        absolute_move_mean=0.06,
        absolute_move_median=0.06,
        absolute_move_max=0.08,
        historical_iv_observations=(-0.30, -0.20, -0.10),
        optionslam_evr=4.0,
    )


def test_spread_gate_accepts_ten_percent_and_rejects_wider_or_invalid_contracts():
    at_limit = OptionContract(bid=9.5, ask=10.5)

    assert spread_pct(at_limit) == 0.10
    assert contract_is_liquid(at_limit, 0.10) is True
    assert contract_is_liquid(OptionContract(bid=9.0, ask=11.0), 0.10) is False
    assert contract_is_liquid(OptionContract(bid=0.0, ask=10.0), 0.10) is False
    assert contract_is_liquid(OptionContract(bid=11.0, ask=9.0), 0.10) is False


def test_spread_gate_accepts_exact_ten_percent_for_cent_quoted_contract():
    assert contract_is_liquid(OptionContract(bid=0.57, ask=0.63), 0.10) is True
    assert contract_is_liquid(OptionContract(bid=0.56, ask=0.63), 0.10) is False


def test_builders_emit_all_supported_strategies_with_labeled_evidence():
    candidates = build_ranked_candidates("AAPL", EARNINGS_DATE, _chain(), _history(), 0.10)

    assert [candidate.strategy_type for candidate in candidates] == [
        "iron_condor",
        "iron_butterfly",
        "calendar",
        "straddle",
        "strangle",
    ]
    assert all(candidate.implied_move_pct == 0.08 for candidate in candidates)
    assert all(contract_is_liquid(leg, 0.10) for candidate in candidates for leg in candidate.legs)
    assert candidates[0].maximum_loss == 200.0
    assert candidates[2].maximum_loss == 150.0
    assert "median 6.00%" in candidates[0].rationale
    assert "mean 6.00%" in candidates[0].rationale
    assert "maximum 8.00%" in candidates[0].rationale
    assert "not expected profit" in candidates[0].rationale
    assert all(candidate.warnings for candidate in candidates if not candidate.defined_risk)
    assert all("Undefined-risk" in candidate.warnings[0] for candidate in candidates[3:])


def test_defined_risk_candidate_ranks_before_equal_score_undefined_risk_candidates():
    candidates = build_ranked_candidates("AAPL", EARNINGS_DATE, _chain(), _history(), 0.10)

    assert candidates[0].defined_risk is True
    assert candidates[0].strategy_type == "iron_condor"
    assert [candidate.defined_risk for candidate in candidates] == [True, True, True, False, False]


def test_candidate_is_omitted_when_any_selected_leg_exceeds_the_spread_limit():
    chain = _chain()
    contracts = tuple(
        replace(contract, bid=1.0, ask=2.0)
        if contract.option_type == "call" and contract.strike == 110.0
        else contract
        for contract in chain.contracts
    )

    candidates = build_ranked_candidates(
        "AAPL", EARNINGS_DATE, replace(chain, contracts=contracts), _history(), 0.10,
    )

    assert "iron_condor" not in {candidate.strategy_type for candidate in candidates}
    assert all(contract_is_liquid(leg, 0.10) for candidate in candidates for leg in candidate.legs)


def test_candidates_require_a_positive_spot_and_liquid_near_money_pair():
    assert build_ranked_candidates(
        "AAPL", EARNINGS_DATE, replace(_chain(), underlying_price=None), _history(), 0.10,
    ) == []

    chain = _chain()
    contracts = tuple(
        replace(contract, bid=1.0, ask=2.0)
        if contract.option_type == "put" and contract.strike == 100.0
        else contract
        for contract in chain.contracts
    )
    assert build_ranked_candidates(
        "AAPL", EARNINGS_DATE, replace(chain, contracts=contracts), _history(), 0.10,
    ) == []
