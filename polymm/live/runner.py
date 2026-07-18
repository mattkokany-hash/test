"""Live / paper orchestration loop.

Ties the spot feed, Gamma discovery, the quoting+risk core, and an execution
client into one poll loop. Shares a single ``Inventory`` and ``RiskEngine``
across all assets (so gross-exposure and the kill switches are global) while
keeping a per-asset volatility estimator.

Quote-to-order mapping (Polymarket has no naked shorting):

    quote.bid  (buy YES @ b)   -> BUY  yes_token @ b
    quote.ask  (sell YES @ a)  -> BUY  no_token  @ (1 - a)

A fill on the NO token is booked as a YES *sell* at ``1 - fill_price`` so the
inventory and PnL math is identical to the backtester.

Default mode is ``paper``: real book, real spot, simulated fills, zero
credentials, zero risk of sending an order. ``live`` mode requires a
``LiveExecutionClient`` constructed from environment credentials and should only
be flipped on after the paper numbers hold up on your own data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..config import StrategyConfig
from ..fairvalue import up_probability
from ..vol import EwmaVol
from ..quoting import QuotingEngine
from ..risk import RiskEngine
from ..inventory import Inventory
from ..hedge import HedgeAdvisor
from .gamma import GammaClient, PolyMarket
from .spot import SpotSource, MultiSourceSpot
from .clob import ExecutionClient, PaperExecutionClient, Fill

__all__ = ["LiveRunner", "TrackedMarket", "OrderRec"]


@dataclass
class TrackedMarket:
    market: PolyMarket
    strike: float | None = None
    strike_time: float | None = None
    resolved: bool = False


@dataclass
class OrderRec:
    order_id: str
    market_id: str
    token_id: str
    is_yes: bool          # True => BUY yes_token; False => BUY no_token (sell YES)
    yes_price: float      # price expressed in YES terms (for inventory booking)
    size: float


@dataclass
class RunnerStats:
    cycles: int = 0
    fills: int = 0
    fees_paid: float = 0.0
    settled: int = 0
    events: list[str] = field(default_factory=list)


class LiveRunner:
    def __init__(
        self,
        cfg: StrategyConfig | None = None,
        *,
        execution: ExecutionClient | None = None,
        spot: SpotSource | None = None,
        gamma: GammaClient | None = None,
        assets: set[str] | None = None,
        discovery_interval_s: float = 30.0,
        clock=time.time,
    ):
        self.cfg = cfg or StrategyConfig()
        self.exec = execution or PaperExecutionClient()
        self.spot = spot or MultiSourceSpot()
        self.gamma = gamma or GammaClient()
        self.assets = assets or {"BTC", "ETH"}
        self.discovery_interval_s = discovery_interval_s
        self.clock = clock

        self.inv = Inventory()
        self.risk = RiskEngine(self.cfg, self.inv)
        self.quoter = QuotingEngine(self.cfg)
        self.hedger = HedgeAdvisor(self.cfg)
        self.vol: dict[str, EwmaVol] = {}

        self.tracked: dict[str, TrackedMarket] = {}
        self.orders: dict[str, OrderRec] = {}
        self.market_orders: dict[str, list[str]] = {}
        self.stats = RunnerStats()
        self._last_discovery = -1e18
        self._fee_per_side = (self.cfg.fee_bps / 1e4) / 2.0

    # -- discovery ----------------------------------------------------------

    def _refresh_markets(self, now: float) -> None:
        if now - self._last_discovery < self.discovery_interval_s:
            return
        self._last_discovery = now
        try:
            found = self.gamma.active_up_down(assets=self.assets)
        except Exception as e:  # noqa: BLE001 - discovery is best-effort
            self.stats.events.append(f"discovery failed: {e}")
            return
        for m in found:
            if m.market_id not in self.tracked:
                self.tracked[m.market_id] = TrackedMarket(market=m)

    # -- per-asset spot -----------------------------------------------------

    def _spot_for(self, asset: str, now: float) -> float | None:
        try:
            px = self.spot.price(asset)
        except Exception as e:  # noqa: BLE001 - a feed hiccup skips this asset
            self.stats.events.append(f"spot {asset} failed: {e}")
            return None
        v = self.vol.setdefault(asset, EwmaVol(self.cfg.vol_halflife_s,
                                               self.cfg.min_sigma))
        v.update(px, now)
        return px

    # -- settlement ---------------------------------------------------------

    def _resolve_outcome(self, tm: TrackedMarket, spot: float) -> float:
        """Best-effort resolution. Prefer the venue's own resolution; fall back
        to spot vs the captured strike."""
        try:
            raw = self.gamma.market_by_condition(tm.market.market_id)
        except Exception:  # noqa: BLE001
            raw = None
        if raw and raw.get("closed"):
            prices = raw.get("outcomePrices")
            if isinstance(prices, list) and prices:
                try:
                    return 1.0 if float(prices[0]) >= 0.5 else 0.0
                except (TypeError, ValueError):
                    pass
        if tm.strike is None:
            return 0.0
        return 1.0 if spot >= tm.strike else 0.0

    def _settle(self, tm: TrackedMarket, spot: float) -> None:
        outcome = self._resolve_outcome(tm, spot)
        # Cancel any resting orders on this market first.
        for oid in self.market_orders.pop(tm.market.market_id, []):
            self.exec.cancel(oid)
            self.orders.pop(oid, None)
        self.inv.settle(tm.market.market_id, outcome)
        tm.resolved = True
        self.stats.settled += 1
        self.stats.events.append(
            f"settled {tm.market.market_id} -> {'UP' if outcome else 'DOWN'}")

    # -- fills --------------------------------------------------------------

    def _book_fills(self, fills: list[Fill]) -> None:
        for f in fills:
            rec = self.orders.get(f.order_id)
            if rec is None:
                continue
            side = "buy" if rec.is_yes else "sell"
            yes_price = f.price if rec.is_yes else (1.0 - f.price)
            marks = {rec.market_id: yes_price}
            if self.risk.allow(rec.market_id, side, f.size, marks):
                self.inv.fill(rec.market_id, side, f.size, yes_price)
                fee = self._fee_per_side * f.price * f.size
                self.inv.realized_pnl -= fee
                self.inv.cash -= fee
                self.stats.fees_paid += fee
                self.stats.fills += 1
            # Order is consumed either way.
            self.orders.pop(f.order_id, None)
            lst = self.market_orders.get(rec.market_id)
            if lst and f.order_id in lst:
                lst.remove(f.order_id)

    # -- quoting ------------------------------------------------------------

    def _cancel_market_orders(self, market_id: str) -> None:
        for oid in self.market_orders.pop(market_id, []):
            self.exec.cancel(oid)
            self.orders.pop(oid, None)

    def _quote_market(self, tm: TrackedMarket, spot: float, sigma: float,
                      now: float, marks: dict[str, float]) -> None:
        m = tm.market
        tau = m.resolve_at - now
        pos = self.inv.position(m.market_id)
        q = self.quoter.quote(m.market_id, marks[m.market_id], pos.qty, tau)

        # Cancel-replace: simplest correct policy for a reference impl.
        self._cancel_market_orders(m.market_id)
        if q.is_empty():
            return

        new_ids: list[str] = []
        if q.bid is not None and q.bid_size > 0.0 and \
                self.risk.allow(m.market_id, "buy", q.bid_size, marks):
            oid = self.exec.submit(m.yes_token_id, q.bid, q.bid_size)
            self.orders[oid] = OrderRec(oid, m.market_id, m.yes_token_id,
                                        True, q.bid, q.bid_size)
            new_ids.append(oid)
        if q.ask is not None and q.ask_size > 0.0 and \
                self.risk.allow(m.market_id, "sell", q.ask_size, marks):
            no_price = round(1.0 - q.ask, 3)
            oid = self.exec.submit(m.no_token_id, no_price, q.ask_size)
            self.orders[oid] = OrderRec(oid, m.market_id, m.no_token_id,
                                        False, q.ask, q.ask_size)
            new_ids.append(oid)
        if new_ids:
            self.market_orders[m.market_id] = new_ids

    # -- main step ----------------------------------------------------------

    def poll(self) -> dict:
        """Run one cycle. Returns a small snapshot for logging/tests."""
        now = self.clock()
        self.stats.cycles += 1
        self._refresh_markets(now)

        # First, reconcile any fills from the previous cycle's resting orders.
        self._book_fills(self.exec.poll_fills())

        # Group active markets by asset and price them.
        by_asset: dict[str, list[TrackedMarket]] = {}
        for tm in self.tracked.values():
            if not tm.resolved:
                by_asset.setdefault(tm.market.asset, []).append(tm)

        fair_snapshot: dict[str, float] = {}
        for asset, tms in by_asset.items():
            spot = self._spot_for(asset, now)
            if spot is None:
                continue
            sigma = self.vol[asset].sigma

            # Capture strikes for windows that have started.
            for tm in tms:
                if tm.strike is None and now >= tm.market.start_at:
                    tm.strike = spot
                    tm.strike_time = now

            # Settle expired windows.
            for tm in tms:
                if now >= tm.market.resolve_at and not tm.resolved:
                    self._settle(tm, spot)

            live = [tm for tm in tms if not tm.resolved and tm.strike is not None]

            # Mark risk on model fair values before quoting.
            marks: dict[str, float] = {}
            for tm in live:
                tau = max(tm.market.resolve_at - now, 0.0)
                p = up_probability(spot, tm.strike, sigma, tau,
                                   min_sigma=self.cfg.min_sigma)
                marks[tm.market.market_id] = p
                fair_snapshot[tm.market.market_id] = p
            self.risk.mark(marks)

            if self.risk.state.halted:
                # Pull all quotes for this asset while halted.
                for tm in live:
                    self._cancel_market_orders(tm.market.market_id)
                continue

            for tm in live:
                self._quote_market(tm, spot, sigma, now, marks)

        return {
            "cycle": self.stats.cycles,
            "tracked": len(self.tracked),
            "open_orders": len(self.orders),
            "fair": fair_snapshot,
            "realized_pnl": self.inv.realized_pnl,
            "halted": self.risk.state.halted,
            "halt_reason": self.risk.state.halt_reason,
        }

    def run(self, *, max_cycles: int | None = None, interval_s: float = 2.0,
            sleep=time.sleep) -> None:
        """Poll until ``max_cycles`` (or forever). Uses ``sleep`` between cycles."""
        n = 0
        while max_cycles is None or n < max_cycles:
            self.poll()
            n += 1
            if max_cycles is None or n < max_cycles:
                sleep(interval_s)
