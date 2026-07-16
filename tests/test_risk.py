from polymm.config import StrategyConfig
from polymm.inventory import Inventory
from polymm.risk import RiskEngine


def test_position_cap_blocks_increase():
    inv = Inventory()
    r = RiskEngine(StrategyConfig(max_position_per_market=100.0), inv)
    assert r.allow("M", "buy", 100.0, {"M": 0.5})
    inv.fill("M", "buy", 100.0, 0.5)
    assert not r.allow("M", "buy", 1.0, {"M": 0.5})  # would exceed cap


def test_reducing_trade_always_allowed_even_when_halted():
    inv = Inventory()
    r = RiskEngine(StrategyConfig(), inv)
    inv.fill("M", "buy", 100.0, 0.5)
    r._halt("test")
    # Selling reduces the long -> permitted despite the halt.
    assert r.allow("M", "sell", 50.0, {"M": 0.5})
    # Buying increases -> blocked while halted.
    assert not r.allow("M", "buy", 10.0, {"M": 0.5})


def test_daily_loss_kill_switch():
    inv = Inventory()
    r = RiskEngine(StrategyConfig(max_daily_loss=100.0), inv)
    inv.realized_pnl = -150.0
    r.mark({})
    assert r.state.halted
    assert "daily loss" in r.state.halt_reason


def test_drawdown_kill_switch():
    inv = Inventory()
    r = RiskEngine(StrategyConfig(max_drawdown=100.0), inv)
    inv.realized_pnl = 200.0
    r.mark({})                 # peak = 200
    inv.realized_pnl = 50.0
    r.mark({})                 # drawdown 150 > 100
    assert r.state.halted
    assert "drawdown" in r.state.halt_reason


def test_gross_exposure_cap():
    inv = Inventory()
    r = RiskEngine(StrategyConfig(max_gross_exposure=100.0,
                                  max_position_per_market=1e9), inv)
    inv.fill("A", "buy", 150.0, 0.5)   # notional 75
    # Another 75 notional in B would push gross to 150 > 100.
    assert not r.allow("B", "buy", 150.0, {"A": 0.5, "B": 0.5})
