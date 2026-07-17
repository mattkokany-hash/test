#!/usr/bin/env python3
"""Run the perps market-making strategy on Bybit — dry-run by default.

    python3 run_bybit_paper.py --cycles 10             # dry-run vs live book
    python3 run_bybit_paper.py --testnet-live          # real orders on TESTNET
                                                        # (needs OAuth creds)

Going to real-money mainnet is a further, deliberate step you take yourself:
load mainnet OAuth creds (BybitAuth(testnet=False)) and pass --live. This script
intentionally does not expose a one-flag mainnet path.
"""

from __future__ import annotations

import argparse

from polymm.perps import PerpsConfig
from polymm.live.bybit import BybitPerpsRunner
from polymm.live.bybit_auth import BybitAuth
from polymm.live.bybit_oauth import BybitOAuth


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--testnet-live", action="store_true",
                    help="place real orders on Bybit TESTNET (requires OAuth creds)")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    runner = BybitPerpsRunner(symbols=symbols, cfg=PerpsConfig(), testnet=True)

    if args.testnet_live:
        creds = BybitOAuth.load_credentials()
        if creds is None:
            raise SystemExit("No OAuth credentials found. Run run_bybit_oauth.py first.")
        if BybitOAuth.is_expired(creds):
            raise SystemExit("Credentials expired. Re-run run_bybit_oauth.py (or refresh).")
        runner.attach_live(BybitAuth.from_oauth_credentials(creds, testnet=True))
        mode = "TESTNET LIVE (real testnet orders)"
    else:
        mode = "DRY-RUN (no orders sent)"

    print(f"Bybit perps · {mode} | symbols={symbols}")
    print("-" * 80)
    for i in range(args.cycles):
        snap = runner.poll()
        for sym, m in snap["markets"].items():
            print(f"cycle {i+1:>3}  {sym:<9} mid={m['mid']:.2f} "
                  f"sigma={m['sigma']:.2e} bid={m['bid']} ask={m['ask']} inv={m['inv']}")
        if snap["halted"]:
            print("  HALTED"); break
        if not snap["markets"]:
            print(f"cycle {i+1:>3}  (no market data — Bybit unreachable from here?)")
        if i < args.cycles - 1:
            import time
            time.sleep(args.interval)

    for ev in runner.events[-6:]:
        print("  event:", ev)


if __name__ == "__main__":
    main()
