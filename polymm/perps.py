"""Continuous market-making for Bybit perpetuals — the strategy adapted off the
binary 'Up/Down' setting.

The binary engine's fair value is a terminal-probability in [0,1]; a perpetual
has no settlement to 0/1, so the fair value is simply the current mid (or index)
price, and quoting becomes classic Avellaneda-Stoikov around a reservation price
that leans against inventory:

    reservation = mid - q * gamma * (sigma * mid)^2 * horizon
    half_spread = max(min_half, mid * edge_bps/1e4) + fee_component
    bid = reservation - half_spread ,  ask = reservation + half_spread

``q`` is signed inventory in contracts, ``sigma`` is per-sqrt-second return
vol (from the same EWMA estimator). Inventory, risk limits, and the EWMA vol
estimator are reused unchanged from the binary engine — only the fair value and
the quote geometry differ. Sizing shrinks the side that would push inventory past
the per-market cap, so the book self-limits.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PerpsConfig", "PerpsQuote", "PerpsQuotingEngine"]


@dataclass(frozen=True)
class PerpsConfig:
    tick: float = 0.1                # price tick (e.g. BTCUSDT perp = 0.1)
    qty_step: float = 0.001          # contract-size step
    base_edge_bps: float = 4.0       # target half-spread over fees, in bps of mid
    fee_bps: float = 5.5             # round-trip taker-ish fee assumption, bps
    inventory_gamma: float = 0.6     # A-S inventory aversion
    risk_horizon_s: float = 5.0      # horizon for the inventory variance term
    min_half_ticks: float = 1.0      # never quote tighter than this many ticks
    max_order_size: float = 0.05     # per-quote size cap, contracts
    max_position: float = 0.20       # per-symbol inventory cap, contracts


@dataclass
class PerpsQuote:
    symbol: str
    bid: float | None
    bid_size: float
    ask: float | None
    ask_size: float
    mid: float
    reservation: float

    def is_empty(self) -> bool:
        return self.bid is None and self.ask is None


class PerpsQuotingEngine:
    def __init__(self, cfg: PerpsConfig | None = None):
        self.cfg = cfg or PerpsConfig()

    def _round_price(self, p: float) -> float:
        t = self.cfg.tick
        return round(round(p / t) * t, 10)

    def _round_qty(self, q: float) -> float:
        s = self.cfg.qty_step
        return round(round(q / s) * s, 10)

    def _size_for(self, inventory: float, side: str) -> float:
        """Cap size so a fill can't push inventory past the position limit."""
        cfg = self.cfg
        if side == "buy":
            room = cfg.max_position - inventory      # headroom to go longer
        else:
            room = cfg.max_position + inventory       # headroom to go shorter
        room = max(0.0, room)
        return self._round_qty(min(cfg.max_order_size, room))

    def quote(self, symbol: str, mid: float, sigma: float,
              inventory: float) -> PerpsQuote:
        """Two-sided perp quote around an inventory-skewed reservation price.

        ``mid``   : current mid/index price.
        ``sigma`` : per-sqrt-second return volatility.
        ``inventory`` : signed net contracts (long positive).
        """
        cfg = self.cfg
        if mid <= 0.0:
            return PerpsQuote(symbol, None, 0.0, None, 0.0, mid, mid)

        price_var = (sigma * mid) ** 2 * cfg.risk_horizon_s
        reservation = mid - inventory * cfg.inventory_gamma * price_var

        fee_price = mid * (cfg.fee_bps / 1e4) / 2.0
        half = max(cfg.min_half_ticks * cfg.tick,
                   mid * (cfg.base_edge_bps / 1e4)) + fee_price

        raw_bid = self._round_price(reservation - half)
        raw_ask = self._round_price(reservation + half)
        # Keep a strictly positive, non-crossed two-sided market.
        if raw_ask <= raw_bid:
            raw_ask = self._round_price(raw_bid + cfg.tick)

        bid: float | None = raw_bid if raw_bid > 0.0 else None
        ask: float | None = raw_ask

        bid_size = self._size_for(inventory, "buy") if bid is not None else 0.0
        ask_size = self._size_for(inventory, "sell") if ask is not None else 0.0
        if bid is not None and bid_size <= 0.0:
            bid = None
        if ask is not None and ask_size <= 0.0:
            ask = None

        return PerpsQuote(symbol, bid, bid_size, ask, ask_size, mid, reservation)
