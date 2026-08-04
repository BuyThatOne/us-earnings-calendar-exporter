from __future__ import annotations

from decimal import Decimal
from datetime import date
from math import isfinite
from statistics import median

from earnings_export.options_models import (
    EarningsMoveHistory,
    OptionChainSnapshot,
    OptionContract,
    StrategyCandidate,
)


_STRATEGY_PRIORITY = {
    "iron_condor": 0,
    "iron_butterfly": 1,
    "calendar": 2,
    "straddle": 3,
    "strangle": 4,
}
_UNDEFINED_RISK_WARNING = (
    "Undefined-risk structure: maximum loss is not bounded by this research model."
)


def spread_pct(contract: OptionContract) -> float | None:
    if contract.bid <= 0 or contract.ask <= 0:
        return None
    midpoint = (contract.bid + contract.ask) / 2
    return (contract.ask - contract.bid) / midpoint


def contract_is_liquid(contract: OptionContract, spread_limit: float) -> bool:
    if (
        contract.bid <= 0
        or contract.ask <= 0
        or contract.ask < contract.bid
        or not all(isfinite(value) for value in (contract.bid, contract.ask, spread_limit))
    ):
        return False

    bid = Decimal(str(contract.bid))
    ask = Decimal(str(contract.ask))
    midpoint = (bid + ask) / Decimal(2)
    spread = (ask - bid) / midpoint
    return spread <= Decimal(str(spread_limit))


def _midpoint(contract: OptionContract) -> float:
    return (contract.bid + contract.ask) / 2


def _contract_at(
    contracts: tuple[OptionContract, ...], option_type: str, strike: float,
) -> OptionContract | None:
    matches = [
        contract
        for contract in contracts
        if contract.option_type == option_type and contract.strike == strike
    ]
    return min(matches, key=lambda contract: contract.option_symbol) if matches else None


def _rationale(history: EarningsMoveHistory, implied_move_pct: float) -> str:
    evidence = [f"Market-implied move {implied_move_pct:.2%}"]
    historical = []
    if history.absolute_move_median is not None:
        historical.append(f"median {history.absolute_move_median:.2%}")
    if history.absolute_move_mean is not None:
        historical.append(f"mean {history.absolute_move_mean:.2%}")
    if history.absolute_move_max is not None:
        historical.append(f"maximum {history.absolute_move_max:.2%}")
    if historical:
        evidence.append("historical absolute one-day moves: " + ", ".join(historical))
    if history.historical_iv_observations:
        evidence.append(
            f"historical IV change median {median(history.historical_iv_observations):.2%}"
        )
    if history.optionslam_evr is not None:
        evidence.append(f"OptionSlam EVR {history.optionslam_evr:g}")
    return "; ".join(evidence) + ". Historical evidence is context, not expected profit."


def _warnings(history: EarningsMoveHistory, defined_risk: bool) -> tuple[str, ...]:
    warnings = []
    if not defined_risk:
        warnings.append(_UNDEFINED_RISK_WARNING)
    warnings.extend(f"Source data quality: {flag}." for flag in history.data_quality_flags)
    return tuple(warnings)


def _candidate(
    ticker: str,
    earnings_date: date,
    strategy_type: str,
    defined_risk: bool,
    legs: tuple[OptionContract, ...],
    entry_limit: float,
    maximum_loss: float | None,
    implied_move_pct: float,
    history: EarningsMoveHistory,
    spread_limit: float,
) -> StrategyCandidate | None:
    serialized_entry_limit = round(entry_limit, 4)
    if (
        not legs
        or not isfinite(entry_limit)
        or serialized_entry_limit <= 0
        or not all(contract_is_liquid(leg, spread_limit) for leg in legs)
    ):
        return None
    return StrategyCandidate(
        ticker=ticker,
        earnings_date=earnings_date,
        strategy_type=strategy_type,
        defined_risk=defined_risk,
        legs=legs,
        entry_limit=serialized_entry_limit,
        maximum_loss=round(maximum_loss, 2) if maximum_loss is not None else None,
        implied_move_pct=implied_move_pct,
        historical_median_move_pct=history.absolute_move_median,
        historical_iv_change_pct=(
            median(history.historical_iv_observations)
            if history.historical_iv_observations
            else None
        ),
        warnings=_warnings(history, defined_risk),
        rationale=_rationale(history, implied_move_pct),
    )


def _evidence_score(candidate: StrategyCandidate, history: EarningsMoveHistory) -> float:
    score = sum(
        value is not None
        for value in (
            history.absolute_move_median,
            history.absolute_move_mean,
            history.absolute_move_max,
            candidate.historical_iv_change_pct,
            history.optionslam_evr,
        )
    )
    if history.absolute_move_median is not None:
        score += 1 / (1 + abs(candidate.implied_move_pct - history.absolute_move_median))
    return float(score)


def _rank_key(
    scored_candidate: tuple[float, StrategyCandidate],
) -> tuple[float, int, int, str]:
    score, candidate = scored_candidate
    return (
        -score,
        0 if candidate.defined_risk else 1,
        _STRATEGY_PRIORITY[candidate.strategy_type],
        candidate.strategy_type,
    )


def build_ranked_candidates(
    ticker: str,
    earnings_date: date,
    snapshot: OptionChainSnapshot,
    history: EarningsMoveHistory,
    spread_limit: float,
) -> list[StrategyCandidate]:
    spot = snapshot.underlying_price
    if spot is None or spot <= 0:
        return []

    expirations = sorted(
        {
            contract.expiration
            for contract in snapshot.contracts
            if contract.expiration is not None and contract.expiration >= earnings_date
        }
    )
    if not expirations:
        return []

    front_expiration = expirations[0]
    front = tuple(
        contract for contract in snapshot.contracts if contract.expiration == front_expiration
    )
    call_strikes = {contract.strike for contract in front if contract.option_type == "call"}
    put_strikes = {contract.strike for contract in front if contract.option_type == "put"}
    paired_strikes = call_strikes & put_strikes
    if not paired_strikes:
        return []

    at_money_strike = min(paired_strikes, key=lambda strike: (abs(strike - spot), strike))
    at_money_call = _contract_at(front, "call", at_money_strike)
    at_money_put = _contract_at(front, "put", at_money_strike)
    if (
        at_money_call is None
        or at_money_put is None
        or not contract_is_liquid(at_money_call, spread_limit)
        or not contract_is_liquid(at_money_put, spread_limit)
    ):
        return []

    implied_move_pct = (_midpoint(at_money_call) + _midpoint(at_money_put)) / spot
    candidates: list[StrategyCandidate] = []
    lower_puts = sorted(
        (contract for contract in front if contract.option_type == "put" and contract.strike < at_money_strike),
        key=lambda contract: (-contract.strike, contract.option_symbol),
    )
    upper_calls = sorted(
        (contract for contract in front if contract.option_type == "call" and contract.strike > at_money_strike),
        key=lambda contract: (contract.strike, contract.option_symbol),
    )

    if len(lower_puts) >= 2 and len(upper_calls) >= 2:
        short_put, long_put = lower_puts[:2]
        short_call, long_call = upper_calls[:2]
        credit = (
            _midpoint(short_put)
            + _midpoint(short_call)
            - _midpoint(long_put)
            - _midpoint(long_call)
        )
        width = max(short_put.strike - long_put.strike, long_call.strike - short_call.strike)
        candidate = _candidate(
            ticker,
            earnings_date,
            "iron_condor",
            True,
            (long_put, short_put, short_call, long_call),
            credit,
            max(0.0, width - credit) * 100,
            implied_move_pct,
            history,
            spread_limit,
        )
        if candidate is not None:
            candidates.append(candidate)

    if lower_puts and upper_calls:
        wing_put = lower_puts[0]
        wing_call = upper_calls[0]
        butterfly_credit = (
            _midpoint(at_money_put)
            + _midpoint(at_money_call)
            - _midpoint(wing_put)
            - _midpoint(wing_call)
        )
        butterfly_width = max(
            at_money_strike - wing_put.strike,
            wing_call.strike - at_money_strike,
        )
        candidate = _candidate(
            ticker,
            earnings_date,
            "iron_butterfly",
            True,
            (wing_put, at_money_put, at_money_call, wing_call),
            butterfly_credit,
            max(0.0, butterfly_width - butterfly_credit) * 100,
            implied_move_pct,
            history,
            spread_limit,
        )
        if candidate is not None:
            candidates.append(candidate)

        candidate = _candidate(
            ticker,
            earnings_date,
            "strangle",
            False,
            (wing_put, wing_call),
            _midpoint(wing_put) + _midpoint(wing_call),
            None,
            implied_move_pct,
            history,
            spread_limit,
        )
        if candidate is not None:
            candidates.append(candidate)

    if len(expirations) >= 2:
        back = tuple(
            contract for contract in snapshot.contracts if contract.expiration == expirations[1]
        )
        back_call = _contract_at(back, "call", at_money_strike)
        if back_call is not None:
            debit = _midpoint(back_call) - _midpoint(at_money_call)
            candidate = _candidate(
                ticker,
                earnings_date,
                "calendar",
                True,
                (at_money_call, back_call),
                debit,
                max(0.0, debit) * 100,
                implied_move_pct,
                history,
                spread_limit,
            )
            if candidate is not None:
                candidates.append(candidate)

    candidate = _candidate(
        ticker,
        earnings_date,
        "straddle",
        False,
        (at_money_put, at_money_call),
        _midpoint(at_money_put) + _midpoint(at_money_call),
        None,
        implied_move_pct,
        history,
        spread_limit,
    )
    if candidate is not None:
        candidates.append(candidate)

    scored = [(_evidence_score(candidate, history), candidate) for candidate in candidates]
    return [candidate for _, candidate in sorted(scored, key=_rank_key)]
