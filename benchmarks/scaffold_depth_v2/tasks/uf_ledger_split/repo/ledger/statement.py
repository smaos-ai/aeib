"""Per-account statements built from the journal."""
from __future__ import annotations

from typing import List, Tuple

from .accounts import Ledger
from .money import format_cents


def entries_for(ledger: Ledger, name: str) -> List[Tuple[str, int]]:
    """(counterparty, signed cents) for every journal entry touching `name`."""
    ledger.get(name)
    out = []
    for src, dst, cents in ledger.journal:
        if src == name:
            out.append((dst, -cents))
        elif dst == name:
            out.append((src, cents))
    return out


def render_statement(ledger: Ledger, name: str) -> str:
    lines = [f"STATEMENT {name}"]
    for other, cents in entries_for(ledger, name):
        direction = "from" if cents > 0 else "to"
        lines.append(f"  {direction:4s} {other:12s} {format_cents(cents):>12s}")
    lines.append(f"BALANCE {format_cents(ledger.balance(name))}")
    return "\n".join(lines)


def net_position(ledger: Ledger, name: str) -> int:
    return sum(cents for _other, cents in entries_for(ledger, name))
