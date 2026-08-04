from __future__ import annotations

from datetime import date
from math import isfinite
from statistics import mean, median
from typing import Mapping, Sequence

from earnings_export.models import EarningsEvent
from earnings_export.options_models import EarningsMoveHistory
from earnings_export.sources.optionslam_evr import EvrResult


def _valid_close(value: float | None) -> bool:
    return value is not None and isfinite(value) and value > 0


def build_earnings_move_history(
    events: Sequence[EarningsEvent],
    closes: Mapping[date, float],
    iv_changes: Sequence[float],
    evr: EvrResult,
) -> EarningsMoveHistory:
    close_dates = sorted(day for day, close in closes.items() if _valid_close(close))
    analyzed_events: list[date] = []
    moves: list[float] = []
    provenance: list[str] = []
    missing_event_close = False

    for event in sorted(events, key=lambda item: (item.earnings_date, item.ticker)):
        event_close = closes.get(event.earnings_date)
        next_day = next((day for day in close_dates if day > event.earnings_date), None)
        if not _valid_close(event_close) or next_day is None:
            missing_event_close = True
            continue

        next_close = closes[next_day]
        assert event_close is not None
        analyzed_events.append(event.earnings_date)
        moves.append(abs(next_close - event_close) / event_close)
        if event.source_calendar_url not in provenance:
            provenance.append(event.source_calendar_url)

    if evr.source_url and evr.source_url not in provenance:
        provenance.append(evr.source_url)

    flags = []
    if missing_event_close:
        flags.append("historical_event_close_unavailable")
    if not iv_changes:
        flags.append("historical_iv_unavailable")
    if evr.status != "available":
        flags.append(f"optionslam_evr_{evr.status}")

    return EarningsMoveHistory(
        historical_earnings_events=tuple(analyzed_events),
        one_day_post_earnings_moves=tuple(moves),
        absolute_move_mean=mean(moves) if moves else None,
        absolute_move_median=median(moves) if moves else None,
        absolute_move_max=max(moves) if moves else None,
        historical_iv_observations=tuple(iv_changes) if iv_changes else None,
        optionslam_evr=evr.value,
        source_provenance=tuple(provenance),
        data_quality_flags=tuple(flags),
    )
