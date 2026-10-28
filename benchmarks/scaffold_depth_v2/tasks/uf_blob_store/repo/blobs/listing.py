"""Listing helpers over the index."""
from __future__ import annotations

from typing import Dict, List

from .index import Index


def with_prefix(index: Index, prefix: str) -> List[str]:
    return [n for n in index.names() if n.startswith(prefix)]


def tree(index: Index) -> Dict[str, List[str]]:
    """Top-level directory -> names below it ('' for names without a directory)."""
    out: Dict[str, List[str]] = {}
    for name in index.names():
        top = name.split("/", 1)[0] if "/" in name else ""
        out.setdefault(top, []).append(name)
    return out


def total_size(index: Index, prefix: str = "") -> int:
    return sum(size for name, size in index.load().items() if name.startswith(prefix))
