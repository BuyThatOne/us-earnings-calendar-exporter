from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from earnings_export.sources.optionslam_evr import (
    OptionSlamEvrProvider,
    parse_optionslam_evr,
)


FIXED_TIME = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)
SOURCE_URL = "https://www.optionslam.com/aapl/"


@pytest.fixture
def load_fixture():
    def load(relative_path: str) -> str:
        return (Path("tests/fixtures") / relative_path).read_text()

    return load


def test_parse_public_evr_returns_value_and_public_status(load_fixture):
    result = parse_optionslam_evr(
        load_fixture("optionslam_evr/public_page.html"), "AAPL", SOURCE_URL, FIXED_TIME,
    )

    assert result.value == 6.5
    assert result.source_url == SOURCE_URL
    assert result.status == "available"
    assert result.collected_at == FIXED_TIME


def test_parse_login_page_never_attempts_authentication(load_fixture):
    result = parse_optionslam_evr(
        load_fixture("optionslam_evr/login_page.html"), "AAPL", SOURCE_URL, FIXED_TIME,
    )

    assert result.value is None
    assert result.status == "authentication_required"


def test_parse_page_without_evr_returns_not_found():
    result = parse_optionslam_evr("<html><body>No data</body></html>", "AAPL", SOURCE_URL, FIXED_TIME)

    assert result.value is None
    assert result.status == "not_found"


class RecordingResponse:
    text = "<p>EVR: 6.5%</p>"

    def raise_for_status(self):
        return None


class RecordingSession:
    def __init__(self):
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return RecordingResponse()

    def post(self, *args, **kwargs):
        raise AssertionError("authentication or form submission is not allowed")


def test_fetch_public_evr_makes_exactly_one_public_get_without_authentication():
    session = RecordingSession()
    provider = OptionSlamEvrProvider(session=session, clock=lambda: FIXED_TIME)

    result = provider.fetch_public_evr("AAPL")

    assert result.value == 6.5
    assert result.status == "available"
    assert len(session.calls) == 1
    args, kwargs = session.calls[0]
    assert args == (SOURCE_URL,)
    assert kwargs == {
        "headers": {"User-Agent": "Mozilla/5.0"},
        "timeout": 30,
        "allow_redirects": False,
    }


class FailingSession:
    def __init__(self):
        self.get_calls = 0

    def get(self, *args, **kwargs):
        self.get_calls += 1
        raise requests.ConnectionError("offline")

    def post(self, *args, **kwargs):
        raise AssertionError("authentication or form submission is not allowed")


def test_fetch_public_evr_returns_request_failed_without_retrying():
    session = FailingSession()
    provider = OptionSlamEvrProvider(session=session, clock=lambda: FIXED_TIME)

    result = provider.fetch_public_evr("AAPL")

    assert result.value is None
    assert result.status == "request_failed"
    assert session.get_calls == 1
