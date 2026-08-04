import os

import pytest

from earnings_export.credentials import load_alpha_vantage_api_key


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


def test_loads_file_without_unix_mode_check_on_non_posix(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    credentials.chmod(0o644)
    monkeypatch.setattr("earnings_export.credentials.os.name", "nt")

    assert load_alpha_vantage_api_key({}, credentials) == "file-key"


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
