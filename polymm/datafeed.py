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
    """Deprecated placeholder -- the real live adapter now lives in ``polymm.live``.

    Use those instead:

    * ``polymm.live.GammaClient``      -- market discovery
    * ``polymm.live.MultiSourceSpot``  -- underlying spot feed
    * ``polymm.live.ClobBook`` / ``PaperExecutionClient`` / ``LiveExecutionClient``
    * ``polymm.live.LiveRunner``       -- the paper/live poll loop

    See ``run_paper.py`` for a no-credentials paper-trading entry point.
    """

    def __init__(self, *_, **__):
        raise NotImplementedError(
            "PolymarketAdapter has been superseded by the polymm.live package. "
            "Use polymm.live.LiveRunner (paper mode by default); see run_paper.py."
        )
