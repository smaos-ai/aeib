"""Accounts and the ledger that owns them."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


class UnknownAccount(KeyError):
    """Raised for an account name that was never opened."""


@dataclass
class Account:
    name: str
    balance_cents: int = 0


@dataclass
class Ledger:
    accounts: Dict[str, Account] = field(default_factory=dict)
    journal: List[Tuple[str, str, int]] = field(default_factory=list)

    def open(self, name: str, balance_cents: int = 0) -> Account:
        if name in self.accounts:
            raise ValueError(f"account {name!r} exists")
        self.accounts[name] = Account(name, balance_cents)
        return self.accounts[name]

    def get(self, name: str) -> Account:
        try:
            return self.accounts[name]
        except KeyError:
            raise UnknownAccount(name) from None

    def balance(self, name: str) -> int:
        return self.get(name).balance_cents

    def snapshot(self) -> Dict[str, int]:
        return {n: a.balance_cents for n, a in sorted(self.accounts.items())}
