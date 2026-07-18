"""polymm — a principled market-making / temporal-arbitrage engine for
short-horizon crypto "Up / Down" binary markets (e.g. Polymarket hourly
BTC/ETH up-or-down markets).

Design goals (what makes this a "better version"):

1. A *model* fair value, not order-book pattern matching. The probability a
   window finishes "Up" is derived from a driftless-GBM terminal-price model
   given live spot, the window reference price, time remaining, and an EWMA
   realized-vol estimate. This is the real engine behind "temporal arbitrage":
   as spot drifts and the clock runs down, the model probability updates
   continuously and usually faster than the quoted book.

2. Inventory-skewed quoting (Avellaneda-Stoikov adapted to binary settlement),
   so the book leans against existing inventory and rotates it, rather than
   accumulating one-sided risk.

3. Delta-based *partial hedging* across overlapping/adjacent windows on the same
   underlying — net the directional exposure instead of hedging leg by leg.

4. A real risk engine: per-market caps, gross-exposure caps, daily-loss and
   drawdown kill switches, and an adverse-selection guard that pulls quotes near
   resolution.

5. An EV gate + fractional-Kelly sizing so we never post negative-edge quotes
   after fees, and a backtester so edge is validated before a cent is risked.

Nothing here is a promise of profit. A ~56% hit rate on near-50/50 binaries is a
thin edge that fees, latency and adverse selection erase easily. Treat the
backtester as the product: if it can't show positive risk-adjusted edge on your
own data with realistic fees, do not run it live.
"""

from .config import StrategyConfig
from .fairvalue import up_probability, binary_delta
from .vol import EwmaVol
from .quoting import QuotingEngine, Quote
from .risk import RiskEngine, RiskState
from .inventory import Inventory, Position
from .hedge import HedgeAdvisor, HedgeAdvice
from .strategy import MarketMaker, MarketState

__all__ = [
    "StrategyConfig",
    "up_probability",
    "binary_delta",
    "EwmaVol",
    "QuotingEngine",
    "Quote",
    "RiskEngine",
    "RiskState",
    "Inventory",
    "Position",
    "HedgeAdvisor",
    "HedgeAdvice",
    "MarketMaker",
    "MarketState",
]

__version__ = "0.1.0"
