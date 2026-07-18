from polymm.attribution import (
    Trade, classify_trigger, trigger_conditions, rank_setups, top_setups,
)
from polymm.backtest import BacktestConfig, run_backtest


def test_classify_buckets():
    # Late, model strongly favours up, we buy YES.
    assert classify_trigger("buy", 0.9, 0.2) == "LATE_STRONG_YES"
    # Early, coin-flip, we sell YES.
    assert classify_trigger("sell", 0.5, 0.9) == "EARLY_COINFLIP_NO"
    # Selling YES when model says up is likely = we took the unlikely side.
    assert classify_trigger("sell", 0.85, 0.5) == "MID_CONTRARIAN_NO"


def test_trigger_conditions_roundtrip():
    c = trigger_conditions("LATE_STRONG_YES")
    assert c["phase"] == "LATE" and c["conviction"] == "STRONG"
    assert c["action"] == "buy YES"
    assert "0.00" in c["time_remaining_frac"]     # LATE spans 0.00–0.33


def test_rank_orders_by_total_pnl():
    trades = [
        Trade("", "buy", 10, 0.4, 0.5, 0.2, 1.0, 5.0, "A"),
        Trade("", "buy", 10, 0.4, 0.5, 0.2, 1.0, 3.0, "A"),
        Trade("", "buy", 10, 0.6, 0.5, 0.5, 0.0, 9.0, "B"),
    ]
    ranked = rank_setups(trades)
    # B has the highest total ($9 in one trade); A is $8 across two.
    assert ranked[0].setup == "B" and ranked[0].total_pnl == 9.0
    assert ranked[1].setup == "A" and ranked[1].total_pnl == 8.0
    assert ranked[1].count == 2 and ranked[1].win_rate == 1.0


def test_top_setups_respects_min_count():
    trades = [Trade("", "buy", 1, 0.4, 0.5, 0.2, 1.0, 100.0, "RARE")]
    trades += [Trade("", "buy", 1, 0.4, 0.5, 0.2, 1.0, 1.0, "COMMON")
               for _ in range(10)]
    top = top_setups(trades, n=5, min_count=5)
    assert [s.setup for s in top] == ["COMMON"]   # RARE filtered out


def test_backtest_collects_and_labels_trades():
    r = run_backtest(BacktestConfig(steps=4000), collect_trades=True)
    assert len(r.trades) > 0
    for t in r.trades[:20]:
        assert t.setup == classify_trigger(t.side, t.fair, t.tau_frac)
        assert t.outcome in (0.0, 1.0)


def test_focus_setups_reduces_fills():
    full = run_backtest(BacktestConfig(steps=4000))
    disc = run_backtest(BacktestConfig(steps=4000), collect_trades=True)
    keys = tuple(s.setup for s in top_setups(disc.trades, n=2))
    assert keys, "expected at least one qualifying setup"
    focused = run_backtest(BacktestConfig(steps=4000, focus_setups=keys))
    # Restricting to 2 setups must not trade more than the unrestricted book.
    assert focused.n_fills <= full.n_fills
