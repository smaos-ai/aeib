from billing.invoice import Invoice
from billing.money import format_cents
from billing.report import render_invoice


def test_format_cents():
    assert format_cents(1999) == "19.99"
    assert format_cents(-5) == "-0.05"


def test_simple_invoice_renders():
    inv = Invoice("A-1").add("pen", "2.50", 2)
    text = render_invoice(inv)
    assert text.splitlines()[0] == "INVOICE A-1"
    assert text.splitlines()[-1] == "TOTAL 5.00"


def test_reported_widget_invoice():
    inv = Invoice("A-2").add("widget", "0.29", 3)
    assert render_invoice(inv).splitlines()[-1] == "TOTAL 0.87"


def test_tax_line():
    inv = Invoice("A-3", tax_bps=2000).add("pen", "2.50", 2)
    lines = render_invoice(inv).splitlines()
    assert "TAX 1.00" in lines and lines[-1] == "TOTAL 6.00"
