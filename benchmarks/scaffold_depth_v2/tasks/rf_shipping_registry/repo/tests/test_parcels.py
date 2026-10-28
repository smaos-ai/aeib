from shipping.parcels import Parcel, cheapest, quote_parcel


def test_volumetric_weight_wins_for_bulky_parcel():
    p = Parcel(weight_g=500, length_cm=40, width_cm=30, height_cm=20)
    assert p.billable_g() == 4800
    assert quote_parcel("express", p, 1) == 1290 + 240 * 5


def test_cheapest_skips_carriers_that_cannot_ship():
    p = Parcel(weight_g=12000, length_cm=10, width_cm=10, height_cm=10)
    assert cheapest(["postal", "courier", "freight", "express"], p, 1) == ("express", 4170)
