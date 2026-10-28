"""A JSON index of stored blobs: name -> size in bytes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

INDEX_NAME = ".index.json"


class Index:
    def __init__(self, root: Path) -> None:
        self.path = Path(root) / INDEX_NAME

    def load(self) -> Dict[str, int]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def add(self, name: str, size: int) -> None:
        data = self.load()
        data[name] = size
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def names(self) -> list:
        return sorted(self.load())
