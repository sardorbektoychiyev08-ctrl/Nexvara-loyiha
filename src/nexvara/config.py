"""Where NEXVARA keeps user data (outside the Git repo)."""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """NEXVARA_DATA env var, else D:\\NEXVARA when drive D: exists, else Documents\\NEXVARA."""
    env = os.environ.get("NEXVARA_DATA")
    if env:
        return Path(env)
    if os.name == "nt" and Path("D:/").exists():
        return Path("D:/NEXVARA")
    return Path.home() / "Documents" / "NEXVARA"


def textbooks_dir() -> Path:
    return data_dir() / "Darsliklar"


def database_path() -> Path:
    return data_dir() / "nexvara.db"


def tests_output_dir() -> Path:
    return data_dir() / "Testlar"
