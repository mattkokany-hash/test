from polymm.backtest import BacktestConfig, run_backtest, gbm_path
from polymm.config import StrategyConfig
import random


def test_backtest_runs_and_reports():
    r = run_backtest(BacktestConfig(steps=3000))
    assert r.n_windows > 0
    assert len(r.equity_curve) == 3000
    assert 0.0 <= r.win_rate <= 1.0


def test_edge_degrades_with_toxicity():
    clean = run_backtest(BacktestConfig(steps=6000, toxicity=0.0))
    toxic = run_backtest(BacktestConfig(steps=6000, toxicity=1.5))
    # More adverse selection should not help PnL; the clean world should do
    # at least as well as the toxic one.
    assert clean.realized_pnl >= toxic.realized_pnl


def test_kill_switch_trips_under_tight_limits():
    tight = StrategyConfig(max_daily_loss=25.0, max_drawdown=25.0)
    r = run_backtest(BacktestConfig(steps=8000, toxicity=2.0), tight)
    # With a punishing world and a tiny loss budget, the halt should engage.
    assert r.halted


def test_gbm_path_length_and_positivity():
    path = gbm_path(500, 1.0, 0.001, 100.0, random.Random(1))
    assert len(path) == 500
    assert all(p > 0 for p in path)
