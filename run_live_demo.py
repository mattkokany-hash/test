#!/usr/bin/env python3
"""Run the polymm engine on a LIVE market snapshot.

The spot prices below were captured live at the timestamp shown (Crypto.com
ticker, which tracks Bybit/Binance spot within a few bps — direct Bybit REST is
CDN-blocked from this sandbox's cloud IP, so the price was sourced through a
reachable venue). Per-second volatility is estimated from the session
high/low with the Parkinson range estimator.

For a fresh Up/Down window (strike = last price, 5 min to resolve) it shows the
model 'Up' probability and the two-sided quote the engine would post as spot
drifts around the strike — i.e. the engine actually running on live data.

    python3 run_live_demo.py
"""

from __future__ import annotations

import math

from polymm.config import StrategyConfig
from polymm.fairvalue import up_probability, binary_delta
from polymm.quoting import QuotingEngine

# --- LIVE SNAPSHOT (captured via Crypto.com ticker) -----------------------
SNAP_TS = "2026-07-17T09:49Z"
LIVE = {
    "BTC": {"last": 62997.60, "high": 64908.73, "low": 62650.02},
    "ETH": {"last": 1832.98, "high": 1894.66, "low": 1820.80},
}
WINDOW_S = 300.0   # 5-minute Up/Down window
DAY_S = 86400.0


def parkinson_sigma_per_sqrt_s(high: float, low: float) -> float:
    """Parkinson range-based daily vol, converted to per-sqrt-second."""
    daily = math.log(high / low) / math.sqrt(4.0 * math.log(2.0))
    return daily / math.sqrt(DAY_S)


def main() -> None:
    cfg = StrategyConfig()
    quoter = QuotingEngine(cfg)

    print(f"polymm — LIVE run on snapshot {SNAP_TS}")
    print(f"window = {int(WINDOW_S)}s, tau at open = {int(WINDOW_S)}s, "
          f"fees = {cfg.fee_bps}bps\n")

    for asset, m in LIVE.items():
        sigma = parkinson_sigma_per_sqrt_s(m["high"], m["low"])
        strike = m["last"]
        daily_pct = sigma * math.sqrt(DAY_S) * 100
        print(f"=== {asset}  last=${m['last']:,.2f}  "
              f"est vol≈{daily_pct:.2f}%/day ({sigma:.2e}/√s) ===")
        print(f"  {'spot move':>10} {'spot':>12} {'tau':>5} "
              f"{'P(Up)':>7} {'delta':>8}   quote (bid / ask)")
        # Mid-window (half the time elapsed) so quotes are live, and a spread
        # of spot offsets around the strike.
        tau = WINDOW_S / 2
        for bps in (-15, -5, 0, 5, 15):
            spot = strike * (1 + bps / 1e4)
            p = up_probability(spot, strike, sigma, tau, min_sigma=cfg.min_sigma)
            d = binary_delta(spot, strike, sigma, tau, min_sigma=cfg.min_sigma)
            q = quoter.quote(f"{asset}-win", p, inventory=0.0, tau=tau)
            bid = f"{q.bid:.3f}" if q.bid is not None else "  -  "
            ask = f"{q.ask:.3f}" if q.ask is not None else "  -  "
            print(f"  {bps:>+8}bps ${spot:>11,.2f} {int(tau):>5} "
                  f"{p:>7.3f} {d:>8.4f}   {bid} / {ask}")
        print()

    print("Reading it: at the strike P(Up)≈0.5 and the engine quotes a two-sided")
    print("market; as spot drifts, the model probability and the delta move")
    print("continuously — the engine leans its quotes and the hedge advisor would")
    print("net that delta across overlapping windows. This is live model output,")
    print("not a fill simulation; validate fills in paper mode before going live.")


if __name__ == "__main__":
    main()
