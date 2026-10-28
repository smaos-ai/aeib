"""Receipt rendering for a cart."""
from __future__ import annotations

from .cart import Cart
from .money import format_cents


def render_receipt(cart: Cart) -> str:
    lines = []
    for sku, unit, qty in cart.lines:
        lines.append(f"{sku:10s} {qty:>3d} x {format_cents(unit):>8s} = {format_cents(cart.line_total(unit, qty)):>9s}")
    if cart.coupon_code:
        lines.append(f"coupon {cart.coupon_code.upper()}")
    lines.append(f"TOTAL {format_cents(cart.total_cents())}")
    return "\n".join(lines)


def savings_cents(cart: Cart) -> int:
    gross = sum(unit * qty for _sku, unit, qty in cart.lines)
    return gross - cart.total_cents()
