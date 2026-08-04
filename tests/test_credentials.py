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


def test_rejects_group_or_other_readable_file(tmp_path):
    credentials = tmp_path / "credentials.env"
    credentials.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    credentials.chmod(0o644)
    with pytest.raises(ValueError, match="owner-only"):
        load_alpha_vantage_api_key({}, credentials)
