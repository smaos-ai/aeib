"""Signing keys addressed by key id, with rotation (not yet wired into tokens)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class KeyRing:
    keys: Dict[str, bytes] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)

    def add(self, kid: str, key: bytes) -> None:
        if len(key) < 16:
            raise ValueError("key too short")
        if kid in self.keys:
            raise ValueError(f"duplicate key id {kid!r}")
        self.keys[kid] = key
        self.order.append(kid)

    def current(self) -> bytes:
        if not self.order:
            raise LookupError("empty keyring")
        return self.keys[self.order[-1]]

    def retire(self, kid: str) -> None:
        self.keys.pop(kid)
        self.order.remove(kid)
