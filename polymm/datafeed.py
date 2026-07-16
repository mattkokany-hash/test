"""Data-feed interfaces and a Polymarket adapter stub.

The engine only needs two things from the outside world: a stream of underlying
spot prices (to drive the fair-value model) and the set of currently active
windows with their reference/strike prices and resolution times. This module
defines those interfaces so a live adapter is a small, well-scoped piece of
code -- and keeps all network/credential concerns out of the strategy core.

The ``PolymarketAdapter`` here is an intentional stub: it documents the shape of
a real integration (Gamma API for market discovery, CLOB for the book, a spot
feed such as a CEX websocket or a Pyth/Chainlink oracle for the underlying)
without shipping live trading code or embedding any keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Protocol

from .strategy import MarketState


class SpotFeed(Protocol):
    def __iter__(self) -> Iterator[tuple[float, float]]:
        """Yield (timestamp_seconds, spot_price) pairs in time order."""
        ...


@dataclass
class ReplaySpotFeed:
    """Deterministic spot feed backed by a recorded list -- use this to backtest
    against real captured ticks."""
    ticks: list[tuple[float, float]]

    def __iter__(self) -> Iterator[tuple[float, float]]:
        return iter(self.ticks)


class MarketDiscovery(Protocol):
    def active_windows(self, now: float) -> Iterable[MarketState]:
        """Return the windows live at ``now`` with their strikes/resolve times."""
        ...


class PolymarketAdapter:
    """Stub for a live Polymarket 'Up/Down' integration.

    A real implementation would:

    * discover active hourly/short up-down markets via the Gamma API, reading
      each market's reference price and resolution timestamp into ``MarketState``;
    * subscribe to the CLOB order book for best bid/ask and depth;
    * subscribe to a low-latency spot feed for the underlying (the same asset the
      market resolves on) to drive ``up_probability``;
    * translate ``QuotingEngine`` output into post-only CLOB orders and reconcile
      fills back through ``MarketMaker.record_fill`` / ``settle``.

    None of that is implemented here on purpose: live order routing needs
    credentials, rate-limit handling, and careful reconciliation that belong in a
    separately reviewed, well-tested deployment layer -- not bundled with the
    modelling core.
    """

    def __init__(self, *_, **__):
        raise NotImplementedError(
            "PolymarketAdapter is a documentation stub. Implement market "
            "discovery, book subscription, a spot feed, and order routing "
            "before going live, and validate with backtest.run_backtest first."
        )
