from polymm.inventory import Inventory


def test_buy_then_settle_yes_wins():
    inv = Inventory()
    inv.fill("M", "buy", 100.0, 0.40)   # bought 100 YES at $0.40
    inv.settle("M", 1.0)                # resolves YES
    assert abs(inv.realized_pnl - 100 * (1.0 - 0.40)) < 1e-9


def test_buy_then_settle_no_loses():
    inv = Inventory()
    inv.fill("M", "buy", 100.0, 0.40)
    inv.settle("M", 0.0)
    assert abs(inv.realized_pnl - 100 * (0.0 - 0.40)) < 1e-9


def test_round_trip_realizes_spread():
    inv = Inventory()
    inv.fill("M", "buy", 100.0, 0.40)
    inv.fill("M", "sell", 100.0, 0.55)
    assert abs(inv.realized_pnl - 100 * (0.55 - 0.40)) < 1e-9
    assert inv.position("M").qty == 0.0


def test_short_then_settle_no_wins():
    inv = Inventory()
    inv.fill("M", "sell", 100.0, 0.60)  # short YES == long NO at effective $0.40
    inv.settle("M", 0.0)                # YES loses => short wins
    assert abs(inv.realized_pnl - 100 * (0.60 - 0.0)) < 1e-9


def test_average_cost_blends():
    inv = Inventory()
    inv.fill("M", "buy", 100.0, 0.40)
    inv.fill("M", "buy", 100.0, 0.60)
    assert abs(inv.position("M").avg_cost - 0.50) < 1e-9


def test_flip_through_zero():
    inv = Inventory()
    inv.fill("M", "buy", 100.0, 0.40)
    inv.fill("M", "sell", 150.0, 0.50)  # close 100, open 50 short at 0.50
    pos = inv.position("M")
    assert abs(pos.qty - (-50.0)) < 1e-9
    assert abs(pos.avg_cost - 0.50) < 1e-9
    # realized on the closed 100 @ (0.50-0.40)
    assert abs(inv.realized_pnl - 100 * (0.50 - 0.40)) < 1e-9


def test_gross_exposure():
    inv = Inventory()
    inv.fill("A", "buy", 100.0, 0.40)
    inv.fill("B", "sell", 50.0, 0.60)
    ge = inv.gross_exposure({"A": 0.45, "B": 0.55})
    assert abs(ge - (100 * 0.45 + 50 * 0.55)) < 1e-9
