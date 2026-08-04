from __future__ import annotations

import errno
import os
import stat
from pathlib import Path
from typing import Mapping


DEFAULT_CREDENTIALS_PATH = Path.home() / ".config" / "earnings-options-research" / "credentials.env"


def _validate_credentials_path(credentials_path: Path) -> os.stat_result | None:
    try:
        path_stat = credentials_path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(path_stat.st_mode):
        raise ValueError("credentials file must not be a symbolic link")
    if not stat.S_ISREG(path_stat.st_mode):
        raise ValueError("credentials path must be a regular file")
    return path_stat


def _open_credentials_file(credentials_path: Path) -> int | None:
    if _validate_credentials_path(credentials_path) is None:
        return None

    flags = os.O_RDONLY
    if os.name == "posix":
        flags |= os.O_NOFOLLOW
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


def load_alpha_vantage_api_key(
    environ: Mapping[str, str], credentials_path: Path = DEFAULT_CREDENTIALS_PATH
) -> str | None:
    if environ.get("ALPHAVANTAGE_API_KEY"):
        return environ["ALPHAVANTAGE_API_KEY"]
    descriptor = _open_credentials_file(credentials_path)
    if descriptor is None:
        return None
    with os.fdopen(descriptor, encoding="utf-8") as credentials_file:
        for line in credentials_file:
            if line.startswith("ALPHAVANTAGE_API_KEY="):
                return line.partition("=")[2].strip() or None
    return None
