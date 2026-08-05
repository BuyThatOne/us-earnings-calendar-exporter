from datetime import datetime, timezone
from pathlib import Path

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
    assert result.status in {"authentication_required", "request_failed", "not_found"}
