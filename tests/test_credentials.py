import os

import pytest

from earnings_export.credentials import (
    load_alpha_vantage_api_key,
    load_named_credential,
    load_optionslam_credentials,
)


def test_load_named_credential_reads_requested_key_only(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text(
        "# local settings\n"
        "ALPHAVANTAGE_API_KEY=test-key\n"
        "OPTIONSLAM_USERNAME=proto-user\n"
        "OPTIONSLAM_PASSWORD=proto-pass\n"
    )
    credentials.chmod(0o600)

    assert load_named_credential({}, "OPTIONSLAM_USERNAME", credentials) == "proto-user"
    assert load_named_credential({}, "OPTIONSLAM_PASSWORD", credentials) == "proto-pass"


def test_optionslam_environment_values_take_precedence_over_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text(
        "OPTIONSLAM_USERNAME=file-user\n"
        "OPTIONSLAM_PASSWORD=file-pass\n"
    )
    credentials.chmod(0o600)

    assert load_optionslam_credentials(
        {
            "OPTIONSLAM_USERNAME": "env-user",
            "OPTIONSLAM_PASSWORD": "env-pass",
        },
        credentials,
    ) == ("env-user", "env-pass")


def test_loads_only_alpha_vantage_key_from_owner_only_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("# local settings\nALPHAVANTAGE_API_KEY=test-key\nOTHER=value\n")
    credentials.chmod(0o600)
    assert load_alpha_vantage_api_key({}, credentials) == "test-key"


def test_environment_key_takes_precedence_over_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    credentials.chmod(0o600)
    assert load_alpha_vantage_api_key({"ALPHAVANTAGE_API_KEY": "env-key"}, credentials) == "env-key"


@pytest.mark.skipif(os.name != "posix", reason="Unix permission bits are POSIX-only")
def test_rejects_group_or_other_readable_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    credentials.chmod(0o644)
    with pytest.raises(ValueError, match="owner-only"):
        load_alpha_vantage_api_key({}, credentials)


def test_loader_fails_closed_for_existing_path_on_non_posix(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    credentials.chmod(0o644)
    monkeypatch.setattr("earnings_export.credentials.os.name", "nt")

    with pytest.raises(ValueError, match="atomic no-follow support"):
        load_alpha_vantage_api_key({}, credentials)


@pytest.mark.skipif(os.name != "posix", reason="O_NOFOLLOW is a POSIX-only requirement")
def test_loader_fails_closed_when_posix_lacks_o_nofollow(monkeypatch, tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    credentials.chmod(0o600)
    monkeypatch.delattr("earnings_export.credentials.os.O_NOFOLLOW")

    with pytest.raises(ValueError, match="O_NOFOLLOW is unavailable on POSIX"):
        load_alpha_vantage_api_key({}, credentials)


def test_rejects_symbolic_link_credentials_file(tmp_path):
    target = tmp_path / "target.env"
    target.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    credentials = tmp_path / "credentials.env"
    try:
        credentials.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symbolic links are unavailable: {error}")

    with pytest.raises(ValueError, match="symbolic link"):
        load_alpha_vantage_api_key({}, credentials)


def test_rejects_non_regular_credentials_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.mkdir()

    with pytest.raises(ValueError, match="regular file"):
        load_alpha_vantage_api_key({}, credentials)
