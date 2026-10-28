import pytest

from orders.models import ValidationError
from orders.repository import OrderRepository
from orders.service import create_order, update_order

GOOD = {"sku": "PEN-1", "quantity": 2, "unit_price_cents": 250, "currency": "EUR"}


def test_create_and_total():
    repo = OrderRepository()
    order = create_order(repo, dict(GOOD))
    assert order.id == 1 and order.total_cents() == 500


def test_create_rejects_bad_quantity():
    with pytest.raises(ValidationError) as info:
        create_order(OrderRepository(), dict(GOOD, quantity=0))
    assert (info.value.field, info.value.message) == ("quantity", "out of range")


def test_update_rejects_bad_currency_and_keeps_order():
    repo = OrderRepository()
    create_order(repo, dict(GOOD))
    with pytest.raises(ValidationError):
        update_order(repo, 1, {"currency": "JPY"})
    assert repo.get(1).currency == "EUR"
