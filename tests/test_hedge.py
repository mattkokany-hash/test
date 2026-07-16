from polymm.config import StrategyConfig
from polymm.hedge import HedgeAdvisor
from polymm.inventory import Inventory


def test_no_hedge_when_flat():
    adv = HedgeAdvisor(StrategyConfig())
    a = adv.advise(Inventory(), {
        "A": {"spot": 100.0, "strike": 100.0, "sigma": 0.001, "tau": 100.0},
    })
    assert a.within_band
    assert a.hedge_market_id is None


def test_hedge_recommended_when_delta_exceeds_band():
    cfg = StrategyConfig(delta_band=10.0)
    adv = HedgeAdvisor(cfg)
    inv = Inventory()
    inv.fill("A", "buy", 5000.0, 0.5)   # big long -> big positive delta
    a = adv.advise(inv, {
        "A": {"spot": 100.0, "strike": 100.0, "sigma": 0.001, "tau": 100.0},
    })
    assert not a.within_band
    assert a.hedge_side == "sell"       # long underlying -> sell to neutralize
    assert a.hedge_qty > 0.0


def test_offsetting_positions_net_down():
    cfg = StrategyConfig(delta_band=10.0)
    adv = HedgeAdvisor(cfg)
    inv = Inventory()
    # Long YES in A and short YES in B on identical windows => deltas cancel.
    inv.fill("A", "buy", 1000.0, 0.5)
    inv.fill("B", "sell", 1000.0, 0.5)
    market = {"spot": 100.0, "strike": 100.0, "sigma": 0.001, "tau": 100.0}
    a = adv.advise(inv, {"A": dict(market), "B": dict(market)})
    assert abs(a.net_delta) < 1e-6
    assert a.within_band
