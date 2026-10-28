import pytest

from shipping.errors import InvalidShipment, UnknownCarrier
from shipping.rates import quote


def test_postal_and_express():
    assert quote("postal", 400, 1) == 390
    assert quote("express", 1500, 2) == 2036


def test_courier_zone_limit():
    with pytest.raises(InvalidShipment):
        quote("courier", 100, 3)


def test_unknown_carrier():
    with pytest.raises(UnknownCarrier):
        quote("drone", 100, 1)


def test_bad_weight_wins_over_unknown_carrier():
    with pytest.raises(InvalidShipment):
        quote("drone", 0, 1)


def test_freight_minimum_and_zone_surcharge():
    assert quote("freight", 10000, 1) == 4900
    assert quote("freight", 80000, 5) == (6800 * 21000 + 5000) // 10000
    with pytest.raises(InvalidShipment):
        quote("freight", 9999, 1)
