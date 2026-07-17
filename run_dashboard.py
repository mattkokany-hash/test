#!/usr/bin/env python3
"""Generate the polymm HTML dashboard from a backtest + toxicity sweep.

    python3 run_dashboard.py               # writes polymm/dashboard/dashboard.html

The page is self-contained (inline SVG charts, no external requests) and opens
straight from disk. The same data contract is produced by the live/paper
RunnerStats, so this page can front a live session too.
"""

from __future__ import annotations

import math
import pathlib

from polymm.config import StrategyConfig
from polymm.backtest import BacktestConfig, run_backtest
from polymm.dashboard import build_dashboard
from polymm.fairvalue import up_probability, binary_delta
from polymm.quoting import QuotingEngine

# A LIVE market snapshot (captured via the Crypto.com ticker, which tracks
# Bybit/Binance spot within a few bps; direct Bybit REST is CDN-blocked from this
# sandbox's cloud IP). Regenerate on a normal network with a real spot feed.
LIVE_SNAPSHOT = {
    "ts": "2026-07-17T09:49Z",
    "source": "live spot · Crypto.com ticker (≈ Bybit)",
    "raw": {
        "BTC": {"last": 62997.60, "high": 64908.73, "low": 62650.02},
        "ETH": {"last": 1832.98, "high": 1894.66, "low": 1820.80},
    },
    "window_s": 300.0,
}


def _parkinson(high: float, low: float) -> float:
    daily = math.log(high / low) / math.sqrt(4.0 * math.log(2.0))
    return daily / math.sqrt(86400.0)


def _live_markets(cfg: StrategyConfig) -> dict:
    quoter = QuotingEngine(cfg)
    tau = LIVE_SNAPSHOT["window_s"] / 2
    markets = []
    for asset, m in LIVE_SNAPSHOT["raw"].items():
        sigma = _parkinson(m["high"], m["low"])
        strike = m["last"]
        p = up_probability(strike, strike, sigma, tau, min_sigma=cfg.min_sigma)
        d = binary_delta(strike, strike, sigma, tau, min_sigma=cfg.min_sigma)
        q = quoter.quote(f"{asset}-win", p, inventory=0.0, tau=tau)
        markets.append({
            "asset": asset, "last": m["last"],
            "vol_pct": sigma * math.sqrt(86400.0) * 100,
            "fair": p, "delta": d, "bid": q.bid, "ask": q.ask,
        })
    return {"ts": LIVE_SNAPSHOT["ts"], "source": LIVE_SNAPSHOT["source"],
            "markets": markets}


def main() -> None:
    cfg = StrategyConfig()
    base_bt = BacktestConfig()
    baseline = run_backtest(base_bt, cfg)

    sweep = [(tox, run_backtest(BacktestConfig(toxicity=tox), cfg))
             for tox in (0.0, 0.3, 0.6, 1.0, 1.5)]

    html = build_dashboard(baseline, sweep, cfg, base_bt, live=_live_markets(cfg))
    out = pathlib.Path(__file__).parent / "polymm" / "dashboard" / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html):,} bytes)")
    print(f"  realized_pnl=${baseline.realized_pnl:.2f}  win={baseline.win_rate:.1%}"
          f"  sharpe={baseline.sharpe:.2f}  maxDD=${baseline.max_drawdown:.2f}")


if __name__ == "__main__":
    main()
