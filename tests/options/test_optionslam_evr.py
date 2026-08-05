from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from earnings_export.sources.optionslam_evr import (
    OPTIONSLAM_HOME_URL,
    OPTIONSLAM_LOGIN_URL,
    OptionSlamEvrProvider,
    parse_optionslam_evr,
)


FIXED_TIME = datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)
SOURCE_URL = "https://www.optionslam.com/earnings/stocks/AAPL"


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


def test_parse_authenticated_stock_page_with_membership_nav_still_returns_evr():
    html = """
    <html>
      <body>
        <a href="/insider_member/">Membership Benefits</a>
        <a href="/help/track_rating/">EVR</a>
        <table>
          <tr><td>EVR:</td><td>2.7</td></tr>
        </table>
      </body>
    </html>
    """

    result = parse_optionslam_evr(html, "NTES", SOURCE_URL, FIXED_TIME)

    assert result.value == 2.7
    assert result.status == "available"


def test_parse_stock_page_prefers_explicit_evr_cell_over_earlier_page_numbers():
    html = """
    <html>
      <body>
        <a href="/help/track_rating/">EVR</a> 1.0 transitional
        <div>Some page chrome before the value</div>
        <table>
          <tr><td>EVR:</td><td>2.7</td></tr>
        </table>
      </body>
    </html>
    """

    result = parse_optionslam_evr(html, "NTES", SOURCE_URL, FIXED_TIME)

    assert result.value == 2.7
    assert result.status == "available"


class RecordingResponse:
    text = "<p>EVR: 6.5%</p>"

    def raise_for_status(self):
        return None


class RecordingSession:
    def __init__(self):
        self.calls = []
        self.post_calls = 0

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return RecordingResponse()

    def post(self, *args, **kwargs):
        self.post_calls += 1
        raise AssertionError("authentication or form submission is not allowed")


class MembershipResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        raise requests.HTTPError("403 Client Error")


class MembershipSession:
    def __init__(self, text):
        self.response = MembershipResponse(text)

    def get(self, *args, **kwargs):
        return self.response

    def post(self, *args, **kwargs):
        raise AssertionError("authentication or form submission is not allowed")


class LoginResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class RedirectResponse(LoginResponse):
    def __init__(self, location: str):
        super().__init__("")
        self.status_code = 302
        self.headers = {"Location": location}
        self.url = "https://www.optionslam.com/aapl/"


class LoginThenSymbolSession:
    def __init__(self, public_html: str, authenticated_html: str):
        self.public_html = public_html
        self.authenticated_html = authenticated_html
        self.login_calls = 0
        self.symbol_get_calls = 0
        self.post_calls = 0
        self.calls = []

    def get(self, url, *args, **kwargs):
        self.calls.append(("get", url, kwargs))
        if url == SOURCE_URL:
            self.symbol_get_calls += 1
            if self.symbol_get_calls == 1:
                return LoginResponse(self.public_html)
            return LoginResponse(self.authenticated_html)
        if url == OPTIONSLAM_HOME_URL:
            return LoginResponse(
                """
                <form method="post" action="/accounts/os_login/">
                    <input type="hidden" name="next" value="/" />
                    <input type="hidden" name="csrfmiddlewaretoken" value="fixture-token" />
                </form>
                """
            )
        return LoginResponse(self.public_html)

    def post(self, *args, **kwargs):
        self.login_calls += 1
        self.post_calls += 1
        self.calls.append(("post", args[0], kwargs))
        return LoginResponse("<html><body>Signed in</body></html>")


class FailedLoginSession:
    def __init__(self, public_html: str):
        self.public_html = public_html
        self.login_calls = 0
        self.symbol_get_calls = 0

    def get(self, url, *args, **kwargs):
        if url == SOURCE_URL:
            self.symbol_get_calls += 1
        return LoginResponse(self.public_html)

    def post(self, *args, **kwargs):
        self.login_calls += 1
        return LoginResponse(self.public_html)


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


def test_fetch_public_evr_classifies_non_2xx_membership_response(load_fixture):
    session = MembershipSession(load_fixture("optionslam_evr/membership_response.html"))
    provider = OptionSlamEvrProvider(session=session, clock=lambda: FIXED_TIME)

    result = provider.fetch_public_evr("AAPL")

    assert result.value is None
    assert result.status == "authentication_required"


def test_fetch_public_evr_uses_authenticated_fallback_after_membership_gate(load_fixture):
    session = LoginThenSymbolSession(
        public_html=load_fixture("optionslam_evr/login_page.html"),
        authenticated_html="<html><body><p>EVR: 6.5%</p></body></html>",
    )
    provider = OptionSlamEvrProvider(
        session=session,
        clock=lambda: FIXED_TIME,
        username="proto-user",
        password="proto-pass",
    )

    result = provider.fetch_public_evr("AAPL")

    assert result.value == 6.5
    assert result.status == "available"
    assert session.login_calls == 1
    assert session.symbol_get_calls == 2
    assert session.calls[1] == (
        "get",
        OPTIONSLAM_HOME_URL,
        {"headers": {"User-Agent": "Mozilla/5.0"}, "timeout": 30},
    )
    assert session.calls[2] == (
        "post",
        OPTIONSLAM_LOGIN_URL,
        {
            "data": {
                "username": "proto-user",
                "password": "proto-pass",
                "csrfmiddlewaretoken": "fixture-token",
                "next": "/",
            },
            "headers": {
                "Referer": OPTIONSLAM_HOME_URL,
                "User-Agent": "Mozilla/5.0",
            },
            "timeout": 30,
            "allow_redirects": False,
        },
    )


def test_fetch_public_evr_uses_authenticated_fallback_after_login_redirect():
    class RedirectLoginSession:
        def __init__(self):
            self.login_calls = 0
            self.symbol_get_calls = 0

        def get(self, url, *args, **kwargs):
            if url == SOURCE_URL:
                self.symbol_get_calls += 1
                if self.symbol_get_calls == 1:
                    return RedirectResponse("/login/")
                return LoginResponse("<p>EVR: 6.5%</p>")
            return LoginResponse("<html><body>Sign in</body></html>")

        def post(self, *args, **kwargs):
            self.login_calls += 1
            return LoginResponse("<html><body>Signed in</body></html>")

    session = RedirectLoginSession()
    provider = OptionSlamEvrProvider(
        session=session,
        clock=lambda: FIXED_TIME,
        username="proto-user",
        password="proto-pass",
    )

    result = provider.fetch_public_evr("AAPL")

    assert result.value == 6.5
    assert result.status == "available"
    assert session.login_calls == 1


def test_fetch_public_evr_uses_one_login_but_starts_each_gated_symbol_without_cookies():
    class GatedSymbolsSession:
        def __init__(self):
            self.cookies = {}
            self.login_calls = 0
            self.symbol_requests = []

        def get(self, url, *args, **kwargs):
            if url == OPTIONSLAM_HOME_URL:
                return LoginResponse(
                    """
                    <form method="post" action="/accounts/os_login/">
                        <input type="hidden" name="next" value="/" />
                        <input type="hidden" name="csrfmiddlewaretoken" value="fixture-token" />
                    </form>
                    """
                )
            if url == OPTIONSLAM_LOGIN_URL:
                return LoginResponse("<html><body>Sign in</body></html>")
            self.symbol_requests.append((url, dict(self.cookies)))
            if self.cookies:
                return LoginResponse("<p>EVR: 6.5%</p>")
            return RedirectResponse("/login/")

        def post(self, *args, **kwargs):
            self.login_calls += 1
            self.cookies["session"] = "authenticated"
            return LoginResponse("<html><body>Signed in</body></html>")

    session = GatedSymbolsSession()
    provider = OptionSlamEvrProvider(
        session=session,
        clock=lambda: FIXED_TIME,
        username="proto-user",
        password="proto-pass",
    )

    aapl = provider.fetch_public_evr("AAPL")
    msft = provider.fetch_public_evr("MSFT")

    assert [aapl.status, msft.status] == ["available", "available"]
    assert session.login_calls == 1
    assert session.symbol_requests == [
        ("https://www.optionslam.com/earnings/stocks/AAPL", {}),
        ("https://www.optionslam.com/earnings/stocks/AAPL", {"session": "authenticated"}),
        ("https://www.optionslam.com/earnings/stocks/MSFT", {}),
        ("https://www.optionslam.com/earnings/stocks/MSFT", {"session": "authenticated"}),
    ]


def test_fetch_public_evr_does_not_login_when_public_page_is_available():
    session = RecordingSession()
    provider = OptionSlamEvrProvider(
        session=session,
        clock=lambda: FIXED_TIME,
        username="proto-user",
        password="proto-pass",
    )

    result = provider.fetch_public_evr("AAPL")

    assert result.status == "available"
    assert session.post_calls == 0


def test_fetch_public_evr_reports_login_failed_without_retry_loop(load_fixture):
    session = FailedLoginSession(load_fixture("optionslam_evr/login_page.html"))
    provider = OptionSlamEvrProvider(
        session=session,
        clock=lambda: FIXED_TIME,
        username="proto-user",
        password="wrong-pass",
    )

    result = provider.fetch_public_evr("AAPL")

    assert result.value is None
    assert result.status == "login_failed"
    assert session.login_calls == 1
    assert session.symbol_get_calls == 1


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
