"""Orchestrator that ties the pieces together into per-tick decisions.

The engine is deliberately *venue-agnostic*: it consumes prices and active
market descriptors and emits desired quotes + a hedge recommendation. Wiring it
to a live venue (order placement, cancels, fills) is the job of an adapter; the
backtester in ``backtest.py`` is one such adapter over a synthetic world, and a
real Polymarket CLOB adapter would implement the same surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import StrategyConfig
from .fairvalue import up_probability
from .vol import EwmaVol
from .quoting import QuotingEngine, Quote
from .risk import RiskEngine
from .inventory import Inventory
from .hedge import HedgeAdvisor, HedgeAdvice

__all__ = ["MarketState", "TickResult", "MarketMaker"]


@dataclass
class MarketState:
    market_id: str
    strike: float          # window reference/open price
    resolve_at: float      # absolute resolution timestamp (seconds)


@dataclass
class TickResult:
    fair: dict[str, float]
    quotes: list[Quote]
    hedge: HedgeAdvice | None
    sigma: float
    halted: bool


class MarketMaker:
    def __init__(self, cfg: StrategyConfig | None = None):
        self.cfg = cfg or StrategyConfig()
        self.inv = Inventory()
        self.vol = EwmaVol(self.cfg.vol_halflife_s, self.cfg.min_sigma)
        self.quoter = QuotingEngine(self.cfg)
        self.risk = RiskEngine(self.cfg, self.inv)
        self.hedger = HedgeAdvisor(self.cfg)

    def on_tick(self, spot: float, now: float, markets: list[MarketState]) -> TickResult:
        """Advance one step. Returns desired quotes and a hedge recommendation.

        The caller is responsible for turning ``quotes`` into venue orders and
        for reporting fills back via ``record_fill`` / ``settle``.
        """
        sigma = self.vol.update(spot, now)

        fair: dict[str, float] = {}
        hedge_inputs: dict[str, dict] = {}
        for m in markets:
            tau = m.resolve_at - now
            p = up_probability(spot, m.strike, sigma, max(tau, 0.0),
                               min_sigma=self.cfg.min_sigma)
            fair[m.market_id] = p
            hedge_inputs[m.market_id] = {
                "spot": spot, "strike": m.strike, "sigma": sigma, "tau": max(tau, 0.0),
            }

        # Mark risk on model fair values and check kill switches.
        self.risk.mark(fair)

        quotes: list[Quote] = []
        if not self.risk.state.halted:
            for m in markets:
                tau = m.resolve_at - now
                pos = self.inv.position(m.market_id)
                quotes.append(
                    self.quoter.quote(m.market_id, fair[m.market_id], pos.qty, tau)
                )

        hedge = self.hedger.advise(self.inv, hedge_inputs)

        return TickResult(
            fair=fair,
            quotes=quotes,
            hedge=hedge,
            sigma=sigma,
            halted=self.risk.state.halted,
        )

    # -- fill / settlement plumbing the adapter calls back into -------------

    def record_fill(self, market_id: str, side: str, qty: float, price: float,
                    marks: dict[str, float]) -> bool:
        """Gate a prospective fill through risk, then book it. Returns whether
        it was allowed."""
        if not self.risk.allow(market_id, side, qty, marks):
            return False
        self.inv.fill(market_id, side, qty, price)
        return True

    def settle(self, market_id: str, outcome: float) -> None:
        self.inv.settle(market_id, outcome)
