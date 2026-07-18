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
from polymm.live import (
    LiveRunner, GammaClient, MultiSourceSpot,
    PaperExecutionClient, RealisticPaperExecutionClient, DryRunExecutionClient,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--assets", default="BTC,ETH")
    ap.add_argument("--realistic", action="store_true",
                    help="model latency + queue position + partial fills "
                         "(recommended before trusting any go-live decision)")
    ap.add_argument("--dry-run", action="store_true",
                    help="log the exact orders a LIVE session would send against "
                         "the real book, but send nothing")
    ap.add_argument("--latency", type=float, default=0.4,
                    help="modeled order latency in seconds (--realistic)")
    ap.add_argument("--fill-prob", type=float, default=0.55,
                    help="per-poll fill probability on a through-trade (--realistic)")
    args = ap.parse_args()

    assets = {a.strip().upper() for a in args.assets.split(",") if a.strip()}
    if args.dry_run:
        execution = DryRunExecutionClient()
        mode = "DRY-RUN (live wiring, NO orders sent)"
    elif args.realistic:
        execution = RealisticPaperExecutionClient(
            latency_s=args.latency, fill_prob=args.fill_prob)
        mode = "paper · realistic fills (latency+queue+partials, no orders sent)"
    else:
        execution = PaperExecutionClient()
        mode = "paper · optimistic fills (no orders sent)"

    runner = LiveRunner(
        StrategyConfig(),
        execution=execution,
        spot=MultiSourceSpot(),
        gamma=GammaClient(),
        assets=assets,
        discovery_interval_s=30.0,
    )

    print(f"{mode} | assets={sorted(assets)}")
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
