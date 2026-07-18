"""Underlying spot-price feed.

The fair-value model needs a live price for the asset each market resolves on.
This provides a dependency-free polling feed over public REST tickers, with two
interchangeable sources (Binance primary, Coinbase fallback) so a geo-block on
one doesn't take the strategy down. A websocket source can be dropped in later
behind the same ``price`` interface for lower latency.

Prices are returned as floats; the caller pairs them with a monotonic clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .http import get_json, HttpError

__all__ = ["SpotSource", "BybitSpot", "BinanceSpot", "CoinbaseSpot",
           "MultiSourceSpot"]

# Asset symbol -> per-venue product code.
_BYBIT = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
_BINANCE = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
_COINBASE = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}


class SpotSource:
    """Interface: return the latest spot for an asset symbol, or raise."""

    def price(self, asset: str) -> float:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class BybitSpot(SpotSource):
    """Bybit v5 public ticker. ``category`` is 'spot' or 'linear' (USDT perps)."""
    base: str = "https://api.bybit.com"
    category: str = "linear"
    timeout: float = 5.0

    def price(self, asset: str) -> float:
        sym = _BYBIT.get(asset)
        if sym is None:
            raise ValueError(f"unsupported asset for Bybit: {asset}")
        data = get_json(f"{self.base}/v5/market/tickers",
                        {"category": self.category, "symbol": sym},
                        timeout=self.timeout)
        if data.get("retCode") not in (0, None):
            raise HttpError(self.base, None, f"bybit retMsg: {data.get('retMsg')}")
        lst = data.get("result", {}).get("list", [])
        if not lst:
            raise HttpError(self.base, None, f"no ticker for {sym}")
        return float(lst[0]["lastPrice"])


@dataclass
class BinanceSpot(SpotSource):
    base: str = "https://api.binance.com"
    timeout: float = 5.0

    def price(self, asset: str) -> float:
        sym = _BINANCE.get(asset)
        if sym is None:
            raise ValueError(f"unsupported asset for Binance: {asset}")
        data = get_json(f"{self.base}/api/v3/ticker/price",
                        {"symbol": sym}, timeout=self.timeout)
        return float(data["price"])


@dataclass
class CoinbaseSpot(SpotSource):
    base: str = "https://api.exchange.coinbase.com"
    timeout: float = 5.0

    def price(self, asset: str) -> float:
        prod = _COINBASE.get(asset)
        if prod is None:
            raise ValueError(f"unsupported asset for Coinbase: {asset}")
        data = get_json(f"{self.base}/products/{prod}/ticker", timeout=self.timeout)
        return float(data["price"])


@dataclass
class MultiSourceSpot(SpotSource):
    """Try each source in order; return the first that succeeds."""
    sources: list[SpotSource] = field(
        default_factory=lambda: [BybitSpot(), BinanceSpot(), CoinbaseSpot()]
    )

    def price(self, asset: str) -> float:
        last: Exception | None = None
        for src in self.sources:
            try:
                return src.price(asset)
            except (HttpError, ValueError, KeyError) as e:
                last = e
        raise HttpError("spot-feed", None, f"all sources failed: {last}")
