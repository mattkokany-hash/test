"""Inventory-skewed quoting for a single binary market.

The mid is the model fair value ``p``. We compute an Avellaneda-Stoikov style
*reservation price* that shifts away from fair value in proportion to current
inventory, so the book leans to offload risk:

    reservation = p - q * gamma * p * (1 - p)

(the ``p*(1-p)`` term is the instantaneous variance of a $1 binary payoff, the
natural risk unit here). Around the reservation price we post a half-spread made
of three parts:

    half_spread = base_edge + fee_per_side + adverse_component(tau)

The adverse component grows as resolution approaches, and inside
``resolution_cutoff_s`` we pull quotes entirely. Each side is additionally
EV-gated: we only post if the expected capture after fees clears ``base_edge``.
Size is fractional Kelly on the model edge, capped.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import StrategyConfig

__all__ = ["Quote", "QuotingEngine"]


@dataclass
class Quote:
    market_id: str
    bid: float | None          # price at which we buy YES (None => no bid)
    bid_size: float
    ask: float | None          # price at which we sell YES (None => no ask)
    ask_size: float
    fair: float
    reservation: float

    def is_empty(self) -> bool:
        return self.bid is None and self.ask is None


class QuotingEngine:
    def __init__(self, cfg: StrategyConfig):
        self.cfg = cfg

    def _fee_per_side(self) -> float:
        # fee_bps is round-trip on ~$1 notional; split across the two sides.
        return (self.cfg.fee_bps / 1e4) / 2.0

    def _adverse_component(self, tau: float) -> float:
        """Extra half-spread that ramps up as resolution nears."""
        w = self.cfg.widen_window_s
        if tau >= w:
            return 0.0
        frac = max(0.0, (w - tau) / w)  # 0 far out, ->1 at the cutoff
        return frac * self.cfg.max_half_spread

    def _round_to_tick(self, price: float) -> float:
        t = self.cfg.tick
        return round(price / t) * t

    def _kelly_size(self, edge: float) -> float:
        """Fractional-Kelly stake for a $1 binary with model edge ``edge``.

        For a near-even binary the Kelly fraction is ~2*edge; we scale by
        ``kelly_fraction`` and the per-order cap. ``edge`` is the model's
        advantage over the price we'd transact at, in probability units.
        """
        if edge <= 0.0:
            return 0.0
        frac = self.cfg.kelly_fraction * min(1.0, 2.0 * edge)
        return min(self.cfg.max_order_size, frac * self.cfg.max_order_size)

    def quote(self, market_id: str, fair: float, inventory: float, tau: float) -> Quote:
        """Produce a two-sided quote (either side may be suppressed).

        ``fair``      : model 'Up' probability in [0,1].
        ``inventory`` : current net YES tokens for this market.
        ``tau``       : seconds to resolution.
        """
        cfg = self.cfg
        fair = min(max(fair, 0.0), 1.0)

        # Too close to resolution: quotes are pure adverse selection. Pull them.
        if tau <= cfg.resolution_cutoff_s:
            return Quote(market_id, None, 0.0, None, 0.0, fair, fair)

        # Reservation price skews against inventory.
        variance = fair * (1.0 - fair)
        reservation = fair - inventory * cfg.inventory_gamma * variance / cfg.max_position_per_market
        reservation = min(max(reservation, 0.0), 1.0)

        fee = self._fee_per_side()
        half = cfg.base_edge + fee + self._adverse_component(tau)
        half = min(half, cfg.max_half_spread)

        raw_bid = reservation - half
        raw_ask = reservation + half

        # --- Bid side (we buy YES): profit if fair - price - fee > base_edge ---
        bid: float | None = None
        bid_size = 0.0
        bid_edge = fair - raw_bid - fee
        if raw_bid > 0.0 and bid_edge >= cfg.base_edge:
            bid = self._round_to_tick(raw_bid)
            if bid <= 0.0 or bid >= fair:
                bid = None
            else:
                bid_size = self._kelly_size(fair - bid - fee)

        # --- Ask side (we sell YES): profit if price - fair - fee > base_edge --
        ask: float | None = None
        ask_size = 0.0
        ask_edge = raw_ask - fair - fee
        if raw_ask < 1.0 and ask_edge >= cfg.base_edge:
            ask = self._round_to_tick(raw_ask)
            if ask >= 1.0 or ask <= fair:
                ask = None
            else:
                ask_size = self._kelly_size(ask - fair - fee)

        return Quote(market_id, bid, bid_size, ask, ask_size, fair, reservation)
