"""Bybit perpetuals adapter: public book reads, order routing, and a market-
making runner wired to the perps quoting engine.

Safety posture mirrors the Polymarket adapter:
* ``dry_run=True`` is the default on the execution client — it logs the exact
  order it would place and sends nothing.
* live routing uses signed v5 calls (``BybitAuth``); ``testnet=True`` is the
  default so a misconfiguration hits the sandbox exchange, not real funds.

Untested against the live venue from the polymm dev sandbox (Bybit CDN-blocks
datacenter IPs); pure logic is unit-tested and the runner degrades gracefully
when the feed is unreachable.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field

from ..perps import PerpsConfig, PerpsQuotingEngine
from ..inventory import Inventory
from ..vol import EwmaVol
from .http import get_json, HttpError
from .bybit_auth import BybitAuth

__all__ = ["BybitPerpsBook", "BybitExecutionClient", "BybitPerpsRunner"]

_PUB = {False: "https://api.bybit.com", True: "https://api-testnet.bybit.com"}


class BybitPerpsBook:
    """Public best bid/ask/mid for a linear perp (no auth)."""

    def __init__(self, testnet: bool = True, timeout: float = 5.0):
        self.base = _PUB[testnet]
        self.timeout = timeout

    def top(self, symbol: str) -> tuple[float, float]:
        data = get_json(f"{self.base}/v5/market/tickers",
                        {"category": "linear", "symbol": symbol}, timeout=self.timeout)
        lst = data.get("result", {}).get("list", [])
        if not lst:
            raise HttpError(self.base, None, f"no ticker for {symbol}")
        t = lst[0]
        return float(t["bid1Price"]), float(t["ask1Price"])

    def mid(self, symbol: str) -> float:
        bid, ask = self.top(symbol)
        return (bid + ask) / 2.0


@dataclass
class BybitExecutionClient:
    """Post-only limit order routing (or dry-run logging) for linear perps."""
    auth: BybitAuth | None = None
    dry_run: bool = True
    echo: bool = True
    log: list[dict] = field(default_factory=list)
    _ids: "itertools.count" = field(default_factory=lambda: itertools.count(1))

    def submit(self, symbol: str, side: str, price: float, qty: float) -> str | None:
        """``side`` is 'buy'/'sell'. Returns an order id (or a dry-run id)."""
        bside = "Buy" if side == "buy" else "Sell"
        if self.dry_run or self.auth is None:
            oid = f"dry-{next(self._ids)}"
            rec = {"order_id": oid, "symbol": symbol, "side": bside,
                   "price": price, "qty": qty}
            self.log.append(rec)
            if self.echo:
                print(f"  [DRY-RUN] {bside} {qty} {symbol} @ {price}")
            return oid
        resp = self.auth.post("/v5/order/create", {
            "category": "linear", "symbol": symbol, "side": bside,
            "orderType": "Limit", "qty": str(qty), "price": str(price),
            "timeInForce": "PostOnly",
        })
        return resp.get("result", {}).get("orderId")

    def cancel_all(self, symbol: str) -> None:
        if self.dry_run or self.auth is None:
            return
        self.auth.post("/v5/order/cancel-all",
                       {"category": "linear", "symbol": symbol})

    def position(self, symbol: str) -> float:
        """Signed position size in contracts (long positive). 0 in dry-run."""
        if self.dry_run or self.auth is None:
            return 0.0
        resp = self.auth.get("/v5/position/list",
                             {"category": "linear", "symbol": symbol})
        net = 0.0
        for p in resp.get("result", {}).get("list", []):
            size = float(p.get("size", 0) or 0)
            net += size if p.get("side") == "Buy" else -size
        return net


@dataclass
class BybitPerpsRunner:
    """Lean perps market-making loop: poll mid, quote, route (dry-run default)."""
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    cfg: PerpsConfig = field(default_factory=PerpsConfig)
    testnet: bool = True
    max_daily_loss: float = 200.0
    clock: object = field(default=time.time)

    def __post_init__(self):
        self.book = BybitPerpsBook(testnet=self.testnet)
        self.execution = BybitExecutionClient(dry_run=True)
        self.quoter = PerpsQuotingEngine(self.cfg)
        self.inv = Inventory()
        self.vol: dict[str, EwmaVol] = {}
        self.halted = False
        self.events: list[str] = []

    def attach_live(self, auth: BybitAuth) -> None:
        """Switch execution to live (still testnet unless auth.testnet is False)."""
        self.execution = BybitExecutionClient(auth=auth, dry_run=False)

    def poll(self) -> dict:
        now = self.clock() if callable(self.clock) else time.time()
        if self.inv.realized_pnl <= -self.max_daily_loss and not self.halted:
            self.halted = True
            self.events.append(f"halt: daily loss {self.inv.realized_pnl:.2f}")

        snapshot = {}
        for sym in self.symbols:
            try:
                mid = self.book.mid(sym)
            except Exception as e:  # noqa: BLE001 - feed hiccup skips this symbol
                self.events.append(f"{sym} feed failed: {e}")
                continue
            v = self.vol.setdefault(sym, EwmaVol())
            v.update(mid, now)
            if self.halted:
                self.execution.cancel_all(sym)
                continue
            inv = self.execution.position(sym) if not self.execution.dry_run \
                else self.inv.position(sym).qty
            q = self.quoter.quote(sym, mid, v.sigma, inv)
            self.execution.cancel_all(sym)
            if q.bid is not None:
                self.execution.submit(sym, "buy", q.bid, q.bid_size)
            if q.ask is not None:
                self.execution.submit(sym, "sell", q.ask, q.ask_size)
            snapshot[sym] = {"mid": mid, "sigma": v.sigma,
                             "bid": q.bid, "ask": q.ask, "inv": inv}
        return {"halted": self.halted, "markets": snapshot}

    def run(self, *, max_cycles: int | None = None, interval_s: float = 2.0,
            sleep=time.sleep) -> None:
        n = 0
        while max_cycles is None or n < max_cycles:
            self.poll()
            n += 1
            if max_cycles is None or n < max_cycles:
                sleep(interval_s)
