from __future__ import annotations

from datetime import date, timedelta


def get_next_week_window(today: date) -> tuple[date, date]:
    days_until_next_monday = 7 - today.weekday()
    start_date = today + timedelta(days=days_until_next_monday)
    end_date = start_date + timedelta(days=4)
    return start_date, end_date


def iter_weekdays(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days
