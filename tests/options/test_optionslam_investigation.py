import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import requests

from earnings_export.sources.optionslam_evr import diagnose_optionslam_response


FIXED_TIME = datetime(2026, 8, 5, 14, 0, tzinfo=timezone.utc)


def load_fixture(relative_path: str) -> str:
    return (Path("tests/fixtures") / relative_path).read_text()


def test_diagnose_membership_or_variant_response_classifies_ntes_failure():
    result = diagnose_optionslam_response(
        load_fixture("optionslam_evr/ntes_failure_response.html"),
        403,
        "NTES",
        "https://www.optionslam.com/ntes/",
        FIXED_TIME,
    )

    assert result.value is None
    assert result.status == "authentication_required"


def test_live_diagnostic_uses_environment_credentials_and_sanitizes_request_errors(
    monkeypatch, capsys,
):
    script_path = Path("scripts/optionslam_ntes_diagnose.py")
    spec = importlib.util.spec_from_file_location("optionslam_ntes_diagnose", script_path)
    assert spec is not None and spec.loader is not None
    diagnostic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diagnostic)

    class FailingSession:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError("offline for proto-user")

    captured_environ = {}

    def load_credentials(environ):
        captured_environ.update(environ)
        return environ.get("OPTIONSLAM_USERNAME"), environ.get("OPTIONSLAM_PASSWORD")

    monkeypatch.setenv("OPTIONSLAM_USERNAME", "proto-user")
    monkeypatch.setenv("OPTIONSLAM_PASSWORD", "proto-pass")
    monkeypatch.setattr(diagnostic.requests, "Session", FailingSession)
    monkeypatch.setattr(diagnostic, "load_optionslam_credentials", load_credentials)

    assert diagnostic._run_live("NTES") == 0

    assert captured_environ["OPTIONSLAM_USERNAME"] == "proto-user"
    assert captured_environ["OPTIONSLAM_PASSWORD"] == "proto-pass"
    assert capsys.readouterr().out == (
        "symbol=NTES mode=live http_status=unavailable "
        "final_url=https://www.optionslam.com/earnings/stocks/NTES result_status=request_failed\n"
    )
