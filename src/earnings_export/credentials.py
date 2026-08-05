from __future__ import annotations

import errno
import os
import stat
from pathlib import Path
from typing import Mapping


DEFAULT_CREDENTIALS_PATH = Path.home() / ".config" / "earnings-options-research" / "credentials.env"


def _required_posix_no_follow_flag() -> int:
    if os.name != "posix":
        return 0
    try:
        return os.O_NOFOLLOW
    except AttributeError as error:
        raise ValueError(
            "credentials security error: O_NOFOLLOW is unavailable on POSIX"
        ) from error


def _open_credentials_file(credentials_path: Path) -> int | None:
    if os.name != "posix":
        if os.path.lexists(credentials_path):
            raise ValueError(
                "credentials security error: cannot access an existing credentials path "
                "without atomic no-follow support"
            )
        return None

    flags = os.O_RDONLY | _required_posix_no_follow_flag()
    try:
        descriptor = os.open(credentials_path, flags)
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError("credentials file must not be a symbolic link") from error
        raise

    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("credentials path must be a regular file")
        if os.name == "posix" and file_stat.st_mode & 0o077:
            raise ValueError("credentials file must be owner-only")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def load_named_credential(
    environ: Mapping[str, str],
    credential_name: str,
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
) -> str | None:
    if environ.get(credential_name):
        return environ[credential_name]
    descriptor = _open_credentials_file(credentials_path)
    if descriptor is None:
        return None
    with os.fdopen(descriptor, encoding="utf-8") as credentials_file:
        for line in credentials_file:
            if line.startswith(f"{credential_name}="):
                return line.partition("=")[2].strip() or None
    return None


def load_alpha_vantage_api_key(
    environ: Mapping[str, str], credentials_path: Path = DEFAULT_CREDENTIALS_PATH
) -> str | None:
    return load_named_credential(environ, "ALPHAVANTAGE_API_KEY", credentials_path)


def load_optionslam_credentials(
    environ: Mapping[str, str],
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
) -> tuple[str | None, str | None]:
    return (
        load_named_credential(environ, "OPTIONSLAM_USERNAME", credentials_path),
        load_named_credential(environ, "OPTIONSLAM_PASSWORD", credentials_path),
    )
