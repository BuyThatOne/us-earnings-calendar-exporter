from datetime import date, datetime, timezone

from earnings_export.models import EarningsEvent
from earnings_export.options_history import build_earnings_move_history
from earnings_export.sources.optionslam_evr import EvrResult


def _event(earnings_date: date, ticker: str = "AAPL") -> EarningsEvent:
    return EarningsEvent(
        earnings_date=earnings_date,
        ticker=ticker,
        company_name="Apple",
        earnings_time="AMC",
        exchange="NASDAQ",
        source_calendar_url=f"https://calendar.test/{earnings_date.isoformat()}",
    )


def _evr(value: float | None = None, status: str = "not_found") -> EvrResult:
    return EvrResult(
        value=value,
        source_url="https://www.optionslam.com/aapl/",
        status=status,
        collected_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )


def test_history_calculates_absolute_moves_from_the_next_available_close():
    history = build_earnings_move_history(
        events=[_event(date(2026, 7, 31)), _event(date(2026, 5, 1))],
        closes={
            date(2026, 5, 1): 100.0,
            date(2026, 5, 4): 106.0,
            date(2026, 7, 31): 100.0,
            date(2026, 8, 3): 92.0,
        },
        iv_changes=(-0.20, -0.10),
        evr=_evr(4.0, "available"),
    )

    assert history.historical_earnings_events == (date(2026, 5, 1), date(2026, 7, 31))
    assert history.one_day_post_earnings_moves == (0.06, 0.08)
    assert history.absolute_move_mean == 0.07
    assert history.absolute_move_median == 0.07
    assert history.absolute_move_max == 0.08
    assert history.historical_iv_observations == (-0.20, -0.10)
    assert history.optionslam_evr == 4.0


def test_history_omits_events_without_both_closes_and_labels_missing_inputs():
    history = build_earnings_move_history(
        events=[_event(date(2026, 5, 1)), _event(date(2026, 7, 31))],
        closes={date(2026, 5, 1): 100.0, date(2026, 5, 4): 106.0},
        iv_changes=(),
        evr=_evr(),
    )

    assert history.historical_earnings_events == (date(2026, 5, 1),)
    assert history.one_day_post_earnings_moves == (0.06,)
    assert history.source_provenance == (
        "https://calendar.test/2026-05-01",
        "https://www.optionslam.com/aapl/",
    )
    assert history.data_quality_flags == (
        "historical_event_close_unavailable",
        "historical_iv_unavailable",
        "optionslam_evr_not_found",
    )
