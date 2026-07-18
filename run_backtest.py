#!/usr/bin/env python3
"""Demo entry point: run the synthetic backtest and print a summary, plus a
small sweep over the adverse-selection ('toxicity') knob so you can see the edge
degrade as flow gets more informed.

    python3 run_backtest.py
"""

from __future__ import annotations

from polymm.backtest import BacktestConfig, run_backtest
from polymm.config import StrategyConfig


def _fmt(r) -> str:
    return (
        f"pnl=${r.realized_pnl:8.2f}  fees=${r.fees_paid:7.2f}  "
        f"fills={r.n_fills:5d}  windows={r.n_windows:4d}  "
        f"win={r.win_rate:5.1%}  sharpe={r.sharpe:6.2f}  "
        f"maxDD=${r.max_drawdown:7.2f}"
        + (f"  HALTED[{r.halt_reason}]" if r.halted else "")
    )


def main() -> None:
    cfg = StrategyConfig()

    print("Baseline run")
    print("-" * 96)
    base = run_backtest(BacktestConfig(), cfg)
    print(_fmt(base))
    print()

    print("Toxicity sweep (edge is regime-dependent and COLLAPSES once flow is")
    print("informed enough -- note the halts at high toxicity, not a clean line)")
    print("-" * 96)
    for tox in (0.0, 0.3, 0.6, 1.0, 1.5):
        r = run_backtest(BacktestConfig(toxicity=tox), cfg)
        print(f"toxicity={tox:<4}  {_fmt(r)}")
    print()

    print("Kill-switch check (tiny loss limit should trip and halt trading)")
    print("-" * 96)
    tight = StrategyConfig(max_daily_loss=50.0, max_drawdown=50.0)
    r = run_backtest(BacktestConfig(toxicity=1.5), tight)
    print(_fmt(r))


if __name__ == "__main__":
    main()
