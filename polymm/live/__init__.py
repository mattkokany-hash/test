"""Live / paper Polymarket adapter for the polymm engine.

Layers, all dependency-free except live order routing:

* ``gamma``  -- market discovery (active Up/Down windows, token ids, timings)
* ``spot``   -- underlying spot feed (Binance primary, Coinbase fallback)
* ``clob``   -- order-book reads + paper/live execution clients
* ``runner`` -- the poll loop that wires it to the quoting + risk core

Default is paper mode: real book, real spot, simulated fills, no credentials.
Live order routing (``clob.LiveExecutionClient``) requires ``py-clob-client``
and environment credentials, and is intentionally opt-in.
"""

from .gamma import GammaClient, PolyMarket
from .spot import (
    SpotSource, BybitSpot, BinanceSpot, CoinbaseSpot, MultiSourceSpot,
)
from .clob import (
    ClobBook, Fill, ExecutionClient, PaperExecutionClient,
    RealisticPaperExecutionClient, DryRunExecutionClient, LiveExecutionClient,
)
from .runner import LiveRunner, TrackedMarket, OrderRec
from .bybit_oauth import OAuthConfig, BybitOAuth, generate_pkce, credential_path
from .bybit_auth import BybitAuth, sign_v5
from .bybit import BybitPerpsBook, BybitExecutionClient, BybitPerpsRunner

__all__ = [
    "GammaClient", "PolyMarket",
    "SpotSource", "BybitSpot", "BinanceSpot", "CoinbaseSpot", "MultiSourceSpot",
    "ClobBook", "Fill", "ExecutionClient",
    "PaperExecutionClient", "RealisticPaperExecutionClient",
    "DryRunExecutionClient", "LiveExecutionClient",
    "LiveRunner", "TrackedMarket", "OrderRec",
    # Bybit perps
    "OAuthConfig", "BybitOAuth", "generate_pkce", "credential_path",
    "BybitAuth", "sign_v5",
    "BybitPerpsBook", "BybitExecutionClient", "BybitPerpsRunner",
]
