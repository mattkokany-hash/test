#!/usr/bin/env python3
"""Paper-trade the polymm engine against LIVE Polymarket books and LIVE spot.

This sends NO orders and needs NO credentials. It discovers real active crypto
Up/Down markets via Gamma, pulls the real CLOB book and a real spot price, runs
the quoting + risk core, and simulates fills against that real liquidity.

    python3 run_paper.py            # a few cycles, then summarize
    python3 run_paper.py --cycles 50 --interval 3

Going live is a deliberate, separate step: construct a
``polymm.live.LiveExecutionClient`` (needs ``py-clob-client`` + POLY_* env
credentials) and pass it as ``execution=`` to ``LiveRunner``. Validate paper
numbers on your own data first.
"""

from __future__ import annotations

import argparse
import time

from polymm.config import StrategyConfig
from polymm.live import LiveRunner, GammaClient, MultiSourceSpot, PaperExecutionClient


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--assets", default="BTC,ETH")
    args = ap.parse_args()

    assets = {a.strip().upper() for a in args.assets.split(",") if a.strip()}
    runner = LiveRunner(
        StrategyConfig(),
        execution=PaperExecutionClient(),
        spot=MultiSourceSpot(),
        gamma=GammaClient(),
        assets=assets,
        discovery_interval_s=30.0,
    )

    print(f"paper trading (no orders sent) | assets={sorted(assets)}")
    print("-" * 84)
    for i in range(args.cycles):
        snap = runner.poll()
        print(
            f"cycle {snap['cycle']:>3}  tracked={snap['tracked']:>3}  "
            f"open_orders={snap['open_orders']:>3}  "
            f"pnl=${snap['realized_pnl']:8.2f}  fills={runner.stats.fills:>4}  "
            f"settled={runner.stats.settled:>3}"
            + ("  HALTED" if snap["halted"] else "")
        )
        if i < args.cycles - 1:
            time.sleep(args.interval)

    print("-" * 84)
    for ev in runner.stats.events[-10:]:
        print("  event:", ev)
    if not runner.tracked:
        print("  (no active up/down markets discovered -- none open right now, or")
        print("   this network can't reach gamma-api.polymarket.com)")


if __name__ == "__main__":
    main()
