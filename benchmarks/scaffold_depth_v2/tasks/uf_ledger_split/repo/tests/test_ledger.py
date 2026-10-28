import pytest

from ledger.accounts import Ledger
from ledger.split import split_bill
from ledger.transfer import post_transfer


def _ledger():
    led = Ledger()
    for name in ("ann", "bob", "cyd"):
        led.open(name, 10_000)
    return led


def test_transfer_moves_money():
    led = _ledger()
    post_transfer(led, "ann", "bob", 250)
    assert led.balance("ann") == 9_750 and led.balance("bob") == 10_250


def test_transfer_rejects_float():
    with pytest.raises(TypeError):
        post_transfer(_ledger(), "ann", "bob", 2.5)


def test_even_split():
    led = _ledger()
    shares = split_bill(led, "ann", ["ann", "bob", "cyd"], 3_000)
    assert shares == {"ann": 1_000, "bob": 1_000, "cyd": 1_000}
    assert led.balance("ann") == 12_000 and led.balance("bob") == 9_000
