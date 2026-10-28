"""Creating and updating orders."""
from __future__ import annotations

import dataclasses
from typing import Any, Dict

from .models import Order, ValidationError
from .repository import OrderRepository
from .validation import CURRENCIES

FIELDS = ("sku", "quantity", "unit_price_cents", "currency", "note")


def create_order(repo: OrderRepository, data: Dict[str, Any]) -> Order:
    unknown = sorted(set(data) - set(FIELDS))
    if unknown:
        raise ValidationError(unknown[0], "unknown field")
    sku = data.get("sku")
    if not isinstance(sku, str) or not sku:
        raise ValidationError("sku", "required")
    if len(sku) > 32:
        raise ValidationError("sku", "too long")
    if not all(c.isalnum() or c == "-" for c in sku):
        raise ValidationError("sku", "invalid characters")
    qty = data.get("quantity")
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise ValidationError("quantity", "must be an integer")
    if not 1 <= qty <= 1000:
        raise ValidationError("quantity", "out of range")
    price = data.get("unit_price_cents")
    if isinstance(price, bool) or not isinstance(price, int):
        raise ValidationError("unit_price_cents", "must be an integer")
    if price < 0:
        raise ValidationError("unit_price_cents", "must be >= 0")
    if data.get("currency") not in CURRENCIES:
        raise ValidationError("currency", "unsupported")
    note = data.get("note", "")
    if not isinstance(note, str) or len(note) > 200:
        raise ValidationError("note", "must be a string of at most 200 characters")
    order = Order(repo.next_id(), sku, qty, price, data["currency"], note)
    return repo.save(order)


def update_order(repo: OrderRepository, order_id: int, changes: Dict[str, Any]) -> Order:
    current = repo.get(order_id)
    if "id" in changes:
        raise ValidationError("id", "immutable")
    data = {f: getattr(current, f) for f in FIELDS}
    data.update(changes)
    unknown = sorted(set(data) - set(FIELDS))
    if unknown:
        raise ValidationError(unknown[0], "unknown field")
    sku = data.get("sku")
    if not isinstance(sku, str) or not sku:
        raise ValidationError("sku", "required")
    if len(sku) > 32:
        raise ValidationError("sku", "too long")
    if not all(c.isalnum() or c == "-" for c in sku):
        raise ValidationError("sku", "invalid characters")
    qty = data.get("quantity")
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise ValidationError("quantity", "must be an integer")
    if not 1 <= qty <= 1000:
        raise ValidationError("quantity", "out of range")
    price = data.get("unit_price_cents")
    if isinstance(price, bool) or not isinstance(price, int):
        raise ValidationError("unit_price_cents", "must be an integer")
    if price < 0:
        raise ValidationError("unit_price_cents", "must be >= 0")
    if data.get("currency") not in CURRENCIES:
        raise ValidationError("currency", "unsupported")
    note = data.get("note", "")
    if not isinstance(note, str) or len(note) > 200:
        raise ValidationError("note", "must be a string of at most 200 characters")
    updated = dataclasses.replace(current, **{k: data[k] for k in FIELDS})
    return repo.save(updated)
