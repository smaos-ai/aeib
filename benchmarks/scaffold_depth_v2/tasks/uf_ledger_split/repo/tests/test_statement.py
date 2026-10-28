from ledger.accounts import Ledger
from ledger.statement import entries_for, net_position, render_statement
from ledger.transfer import post_transfer


def test_statement_lists_both_directions():
    led = Ledger()
    led.open("ann", 1_000)
    led.open("bob", 1_000)
    post_transfer(led, "ann", "bob", 300)
    post_transfer(led, "bob", "ann", 50)
    assert entries_for(led, "ann") == [("bob", -300), ("bob", 50)]
    assert net_position(led, "bob") == 250
    assert render_statement(led, "ann").splitlines()[-1] == "BALANCE 7.50"
