"""Name normalisation for blob names."""
from __future__ import annotations

from pathlib import PurePosixPath


def normalize_name(name: str) -> str:
    """Strip surrounding whitespace and turn backslashes into forward slashes."""
    if not isinstance(name, str):
        raise TypeError("blob name must be str")
    return name.strip().replace("\\", "/")


def name_parts(name: str) -> tuple:
    return PurePosixPath(normalize_name(name)).parts
