"""Posting transfers between accounts."""
from __future__ import annotations

from .accounts import Ledger
from .money import require_cents


def post_transfer(ledger: Ledger, src: str, dst: str, cents: int) -> None:
    """Move `cents` (> 0) from src to dst and record it in the journal."""
    require_cents(cents)
    if src == dst:
        raise ValueError("src and dst must differ")
    source = ledger.get(src)
    target = ledger.get(dst)
    source.balance_cents -= cents
    target.balance_cents += cents
    ledger.journal.append((src, dst, cents))
