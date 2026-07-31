from datetime import date

from earnings_export.date_window import get_next_week_window, iter_weekdays


def test_get_next_week_window_from_2026_07_31():
    start_date, end_date = get_next_week_window(date(2026, 7, 31))
    assert start_date == date(2026, 8, 3)
    assert end_date == date(2026, 8, 7)


def test_iter_weekdays_returns_monday_through_friday():
    days = iter_weekdays(date(2026, 8, 3), date(2026, 8, 7))
    assert days == [
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
        date(2026, 8, 6),
        date(2026, 8, 7),
    ]
