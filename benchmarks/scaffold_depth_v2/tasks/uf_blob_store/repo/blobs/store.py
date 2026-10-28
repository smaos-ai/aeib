"""BlobStore: blobs are files below a root directory."""
from __future__ import annotations

from pathlib import Path

from .index import Index
from .paths import normalize_name


class BlobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = Index(self.root)

    def put(self, name: str, data: bytes) -> Path:
        """Store `data` under `name`; return the written path."""
        raise NotImplementedError("put")

    def get(self, name: str) -> bytes:
        return (self.root / normalize_name(name)).read_bytes()

    def names(self) -> list:
        return self.index.names()
