"""Event-driven backtester over a synthetic world of overlapping 'Up/Down'
windows on one underlying.

The synthetic world is deliberately adversarial-honest:

* Spot follows a GBM path you control (``true_sigma``).
* Overlapping windows open every ``stagger_s`` and last ``window_len_s`` -- so
  several are live at once and the hedge advisor has something to net.
* The venue's reference price is the *true* fair value plus two kinds of error:
  - ``noise_sigma``: mean-zero mispricing. This is the edge we exist to capture.
  - ``toxicity``:    flow correlated with the *upcoming* move, i.e. adverse
    selection -- we tend to get filled right before the market moves against us.
  Turn ``toxicity`` up and watch the edge evaporate; that is the point.

Fills: at each tick, if our bid sits at/above the venue reference we buy; if our
ask sits at/below it we sell. Fees are deducted per fill. Windows settle 0/1 at
expiry. The runner reports realized PnL, per-window win rate, Sharpe and max
drawdown.

This is a *model of a market*, not the market. Positive results here mean the
engine is internally sound, not that it will print money live. Re-run it against
your own recorded Polymarket data before believing anything.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .config import StrategyConfig
from .strategy import MarketMaker, MarketState

__all__ = ["BacktestConfig", "BacktestResult", "run_backtest", "gbm_path"]


def gbm_path(n: int, dt: float, sigma: float, s0: float, rng: random.Random) -> list[float]:
    """Driftless GBM price path of ``n`` steps at spacing ``dt``."""
    path = [s0]
    for _ in range(n - 1):
        z = rng.gauss(0.0, 1.0)
        s = path[-1] * math.exp(-0.5 * sigma * sigma * dt + sigma * math.sqrt(dt) * z)
        path.append(s)
    return path


@dataclass
class BacktestConfig:
    steps: int = 20_000
    dt: float = 1.0                 # seconds per step
    true_sigma: float = 0.0009      # per-sqrt-second vol of the real path
    s0: float = 60_000.0
    window_len_s: float = 300.0     # 5-minute windows
    stagger_s: float = 60.0         # a new window opens every minute
    noise_sigma: float = 0.02       # venue mispricing stdev (our edge source)
    toxicity: float = 0.6           # adverse-selection strength (our edge sink)
    tox_horizon_s: float = 30.0     # lookahead the toxic flow "sees"
    seed: int = 7


@dataclass
class BacktestResult:
    realized_pnl: float
    fees_paid: float
    n_fills: int
    n_windows: int
    win_rate: float
    sharpe: float
    max_drawdown: float
    halted: bool
    halt_reason: str
    equity_curve: list[float] = field(default_factory=list)
    per_window_pnl: list[float] = field(default_factory=list)


def _standardized_lookahead(path: list[float], i: int, horizon_steps: int) -> float:
    """Standardized upcoming log-return over ``horizon_steps`` (0 at the end)."""
    j = min(i + horizon_steps, len(path) - 1)
    if j <= i:
        return 0.0
    return math.log(path[j] / path[i])


def run_backtest(bt: BacktestConfig | None = None,
                 cfg: StrategyConfig | None = None) -> BacktestResult:
    bt = bt or BacktestConfig()
    cfg = cfg or StrategyConfig()
    rng = random.Random(bt.seed)

    path = gbm_path(bt.steps, bt.dt, bt.true_sigma, bt.s0, rng)
    mm = MarketMaker(cfg)

    tox_steps = max(1, int(bt.tox_horizon_s / bt.dt))
    fee_per_side = (cfg.fee_bps / 1e4) / 2.0

    # Active windows: market_id -> MarketState. Strikes captured at open.
    active: dict[str, MarketState] = {}
    strikes: dict[str, float] = {}
    next_open_step = 0
    win_counter = 0

    fees_paid = 0.0
    n_fills = 0
    per_window_pnl: list[float] = []
    equity_curve: list[float] = []
    baseline_pnl = 0.0  # realized_pnl at the moment a window opened (for attribution)
    window_open_pnl: dict[str, float] = {}

    for i in range(bt.steps):
        now = i * bt.dt
        spot = path[i]

        # Open new windows on schedule.
        if i >= next_open_step:
            mid = f"W{win_counter}"
            win_counter += 1
            resolve_at = now + bt.window_len_s
            active[mid] = MarketState(mid, strike=spot, resolve_at=resolve_at)
            strikes[mid] = spot
            window_open_pnl[mid] = mm.inv.realized_pnl
            next_open_step += max(1, int(bt.stagger_s / bt.dt))

        markets = list(active.values())
        result = mm.on_tick(spot, now, markets)

        # Attempt fills against the synthetic venue reference for each market.
        if not result.halted:
            z = _standardized_lookahead(path, i, tox_steps)
            for q in result.quotes:
                if q.is_empty():
                    continue
                fair = result.fair[q.market_id]
                # Venue reference = fair + mispricing + adverse-flow component.
                eps = rng.gauss(0.0, bt.noise_sigma) + bt.toxicity * z
                venue = min(max(fair + eps, 0.0), 1.0)

                marks = result.fair
                # Buy YES if our bid is at/above where the venue will sell.
                if q.bid is not None and q.bid_size > 0.0 and venue <= q.bid:
                    if mm.record_fill(q.market_id, "buy", q.bid_size, q.bid, marks):
                        fee = fee_per_side * q.bid * q.bid_size
                        mm.inv.realized_pnl -= fee
                        mm.inv.cash -= fee
                        fees_paid += fee
                        n_fills += 1
                # Sell YES if our ask is at/below where the venue will buy.
                elif q.ask is not None and q.ask_size > 0.0 and venue >= q.ask:
                    if mm.record_fill(q.market_id, "sell", q.ask_size, q.ask, marks):
                        fee = fee_per_side * q.ask * q.ask_size
                        mm.inv.realized_pnl -= fee
                        mm.inv.cash -= fee
                        fees_paid += fee
                        n_fills += 1

        # Settle expired windows.
        expired = [mid for mid, m in active.items() if now >= m.resolve_at]
        for mid in expired:
            outcome = 1.0 if path[i] >= strikes[mid] else 0.0
            before = mm.inv.realized_pnl
            mm.settle(mid, outcome)
            per_window_pnl.append(mm.inv.realized_pnl - window_open_pnl[mid])
            del active[mid]

        equity_curve.append(mm.inv.equity(result.fair))

    # Settle anything still open at the true final price.
    final = path[-1]
    for mid, m in list(active.items()):
        outcome = 1.0 if final >= strikes[mid] else 0.0
        mm.settle(mid, outcome)
        per_window_pnl.append(mm.inv.realized_pnl - window_open_pnl[mid])

    wins = sum(1 for p in per_window_pnl if p > 1e-9)
    graded = [p for p in per_window_pnl if abs(p) > 1e-9]
    win_rate = wins / len(graded) if graded else 0.0

    if len(graded) > 1:
        mean = sum(graded) / len(graded)
        var = sum((p - mean) ** 2 for p in graded) / (len(graded) - 1)
        sd = math.sqrt(var)
        sharpe = (mean / sd) * math.sqrt(len(graded)) if sd > 0.0 else 0.0
    else:
        sharpe = 0.0

    peak = -math.inf
    max_dd = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        max_dd = max(max_dd, peak - e)

    return BacktestResult(
        realized_pnl=mm.inv.realized_pnl,
        fees_paid=fees_paid,
        n_fills=n_fills,
        n_windows=len(per_window_pnl),
        win_rate=win_rate,
        sharpe=sharpe,
        max_drawdown=max_dd,
        halted=mm.risk.state.halted,
        halt_reason=mm.risk.state.halt_reason,
        equity_curve=equity_curve,
        per_window_pnl=per_window_pnl,
    )
