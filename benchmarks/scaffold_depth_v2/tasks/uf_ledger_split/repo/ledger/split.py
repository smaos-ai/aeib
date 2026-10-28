"""Splitting a paid bill among participants."""
from __future__ import annotations

from typing import Dict, Sequence

from .accounts import Ledger
from .transfer import post_transfer


def split_bill(ledger: Ledger, payer: str, participants: Sequence[str], total_cents: int) -> Dict[str, int]:
    """Split `total_cents`, already paid by `payer`, among `participants`; return the shares."""
    raise NotImplementedError("split_bill")
