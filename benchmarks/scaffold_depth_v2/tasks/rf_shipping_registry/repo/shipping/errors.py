"""Shipping errors."""


class ShippingError(ValueError):
    """Base class."""


class UnknownCarrier(ShippingError):
    """No such carrier."""


class InvalidShipment(ShippingError):
    """Weight or zone out of range for the carrier."""
