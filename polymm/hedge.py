"""Delta-based partial hedging across markets on the same underlying.

Each open YES position carries an underlying-delta of ``qty * binary_delta(...)``
-- how much its value moves per unit change in ``ln(spot)``. Overlapping and
adjacent 'Up/Down' windows on the same coin are highly correlated, so the right
thing is to net their deltas and hedge the *aggregate* excess, not each leg.

The advisor sums net delta, and if it sits outside ``+/- delta_band`` recommends
the offsetting trade (in the most liquid / longest-dated market supplied) that
pulls it back to the band edge. This is the "partial hedge" -- we deliberately
leave a band of directional exposure rather than paying spread to be perfectly
flat.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import StrategyConfig
from .fairvalue import binary_delta
from .inventory import Inventory

__all__ = ["HedgeAdvice", "HedgeAdvisor", "MarketDelta"]


@dataclass
class MarketDelta:
    market_id: str
    spot: float
    strike: float
    sigma: float
    tau: float
    unit_delta: float          # binary_delta per YES token
    position_delta: float      # unit_delta * qty


@dataclass
class HedgeAdvice:
    net_delta: float
    within_band: bool
    hedge_market_id: str | None
    hedge_side: str | None     # 'buy' or 'sell' YES to neutralize
    hedge_qty: float
    per_market: list[MarketDelta]


class HedgeAdvisor:
    def __init__(self, cfg: StrategyConfig):
        self.cfg = cfg

    def advise(self, inventory: Inventory, markets: dict[str, dict]) -> HedgeAdvice:
        """``markets`` maps market_id -> {spot, strike, sigma, tau}. Only markets
        with an open position contribute to net delta, but any supplied market
        is eligible to carry the hedge."""
        per_market: list[MarketDelta] = []
        net = 0.0
        for mid, m in markets.items():
            pos = inventory.positions.get(mid)
            qty = pos.qty if pos else 0.0
            ud = binary_delta(m["spot"], m["strike"], m["sigma"], m["tau"],
                              min_sigma=self.cfg.min_sigma)
            pd = ud * qty
            net += pd
            per_market.append(MarketDelta(mid, m["spot"], m["strike"],
                                          m["sigma"], m["tau"], ud, pd))

        band = self.cfg.delta_band
        if abs(net) <= band:
            return HedgeAdvice(net, True, None, None, 0.0, per_market)

        excess = abs(net) - band  # delta units to remove

        # Hedge in the market with the largest unit delta (most delta per token
        # traded == least spread paid). Prefer ones with a live tau.
        candidates = [md for md in per_market if md.tau > 0.0 and md.unit_delta > 0.0]
        if not candidates:
            return HedgeAdvice(net, False, None, None, 0.0, per_market)
        target = max(candidates, key=lambda md: md.unit_delta)

        qty = excess / target.unit_delta
        # If net delta is positive (too long the underlying) we sell YES there.
        side = "sell" if net > 0.0 else "buy"
        return HedgeAdvice(net, False, target.market_id, side, qty, per_market)
