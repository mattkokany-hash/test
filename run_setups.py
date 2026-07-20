#!/usr/bin/env python3
"""Show the bot's top-5 money-making setups and their exact triggers — then
check whether they hold up out-of-sample, and run the bot focused on just them.

    python3 run_setups.py

This makes the "brain" legible: every fill is tagged with the setup that
triggered it (phase × conviction × side), setups are ranked by realized profit,
and the top 5 are printed with the precise conditions that fire them.

HONEST NOTE: the ranking is in-sample. The out-of-sample section re-checks the
same setups on unseen data — if a setup's edge vanishes there, it was noise, not
signal. Trust the out-of-sample column, not the discovery column.
"""

from __future__ import annotations

from polymm.config import StrategyConfig
from polymm.backtest import BacktestConfig, run_backtest
from polymm.attribution import top_setups, rank_setups, trigger_conditions

DISCOVERY_SEED = 7
VALIDATION_SEEDS = [101, 202, 303, 404, 505]   # several unseen worlds, averaged


def main() -> None:
    cfg = StrategyConfig()

    # 1) Discover setups in-sample.
    disc = run_backtest(BacktestConfig(seed=DISCOVERY_SEED), cfg, collect_trades=True)
    top = top_setups(disc.trades, n=5)
    if not top:
        print("No setups met the minimum trade count; run more steps.")
        return

    print("=" * 78)
    print("TOP 5 SETUPS — the triggers inside the bot's brain (in-sample)")
    print("=" * 78)
    for i, s in enumerate(top, 1):
        c = trigger_conditions(s.setup)
        print(f"\n#{i}  {s.setup}")
        print(f"    trades={s.count}   total=${s.total_pnl:8.2f}   "
              f"avg=${s.avg_pnl:6.3f}   win={s.win_rate:5.1%}")
        print(f"    TRIGGER — fire when ALL hold:")
        print(f"      • time remaining is {c['phase']} "
              f"(tau/window in {c['time_remaining_frac']})")
        print(f"      • model conviction is {c['conviction']} "
              f"(prob of our side in {c['aligned_model_prob']})")
        print(f"      • action: {c['action']}")

    # 2) Validate the SAME setups across several unseen worlds (averaged).
    oos_total: dict[str, float] = {}
    oos_wins: dict[str, list] = {}
    for seed in VALIDATION_SEEDS:
        v = run_backtest(BacktestConfig(seed=seed), cfg, collect_trades=True)
        for st in rank_setups(v.trades):
            oos_total[st.setup] = oos_total.get(st.setup, 0.0) + st.total_pnl
            oos_wins.setdefault(st.setup, []).append(st.win_rate)
    n = len(VALIDATION_SEEDS)
    print("\n" + "=" * 78)
    print(f"OUT-OF-SAMPLE CHECK — same setups across {n} unseen worlds (per-world avg)")
    print("=" * 78)
    print(f"{'setup':<22}{'in-sample $':>13}{'oos avg $':>12}{'oos win':>9}  verdict")
    print("-" * 78)
    survivors = 0
    for s in top:
        oos_avg = oos_total.get(s.setup, 0.0) / n
        wr = oos_wins.get(s.setup)
        oosw = f"{sum(wr)/len(wr):.0%}" if wr else "—"
        held = oos_avg > 0
        survivors += held
        print(f"{s.setup:<22}{s.total_pnl:>13.2f}{oos_avg:>12.2f}{oosw:>9}  "
              f"{'holds up' if held else 'NOISE (dropped)'}")

    # 3) Run the bot focused on just the top-5 setups, averaged over the worlds.
    keys = tuple(s.setup for s in top)
    full_pnl = foc_pnl = full_f = foc_f = 0.0
    for seed in VALIDATION_SEEDS:
        full_pnl += run_backtest(BacktestConfig(seed=seed), cfg).realized_pnl
        fr = run_backtest(BacktestConfig(seed=seed, focus_setups=keys), cfg)
        foc_pnl += fr.realized_pnl
        full_f += run_backtest(BacktestConfig(seed=seed)).n_fills
        foc_f += fr.n_fills
    print("\n" + "=" * 78)
    print(f"FOCUSED RUN — bot trades ONLY the top-5 setups (avg of {n} worlds)")
    print("=" * 78)
    print(f"  full strategy : pnl=${full_pnl/n:8.2f}  fills/world={full_f/n:6.0f}")
    print(f"  top-5 only    : pnl=${foc_pnl/n:8.2f}  fills/world={foc_f/n:6.0f}")
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    if survivors == 0:
        print("  0 of 5 setups survived out-of-sample. On this data the 'best' setups")
        print("  are IN-SAMPLE NOISE — this is the overfitting trap the whole project")
        print("  warns about. Do NOT hard-code these triggers into a live bot.")
    else:
        print(f"  {survivors} of 5 setups kept a positive edge out-of-sample. Those are")
        print("  the only ones worth considering — and still only with tiny live size.")


if __name__ == "__main__":
    main()
