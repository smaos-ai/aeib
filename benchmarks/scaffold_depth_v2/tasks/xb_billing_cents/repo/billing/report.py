"""Plain-text rendering of invoices."""
from __future__ import annotations

from .invoice import Invoice
from .money import format_cents


def render_invoice(invoice: Invoice) -> str:
    out = [f"INVOICE {invoice.number}"]
    for line in invoice.lines:
        out.append(f"{line.sku:12s} {line.quantity:>4d} x {line.unit_price:>8s} = {format_cents(line.net_cents()):>10s}")
    out.append(f"SUBTOTAL {format_cents(invoice.subtotal_cents())}")
    if invoice.tax_bps:
        out.append(f"TAX {format_cents(invoice.tax_cents())}")
    out.append(f"TOTAL {format_cents(invoice.total_cents())}")
    return "\n".join(out)
