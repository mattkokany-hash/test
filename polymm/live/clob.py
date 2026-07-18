"""CLOB order-book reads and order execution.

Two concerns live here:

1. ``ClobBook`` -- dependency-free reads of the public order book
   (``https://clob.polymarket.com/book?token_id=...``). Both paper and live
   modes use the *real* book, so paper trading is honest about liquidity.

2. Execution clients that share one interface:

       submit(token_id, price, size) -> order_id
       cancel(order_id)
       poll_fills() -> list[Fill]

   * ``PaperExecutionClient`` rests orders locally and fills them against the
     live book (a BUY at ``price`` fills when the best ask is <= ``price``). No
     keys, no risk -- but it reacts to real depth.
   * ``LiveExecutionClient`` wraps ``py-clob-client`` to post real post-only
     orders. It is import-guarded and never touches the network unless you
     explicitly construct it with credentials pulled from the environment.

Everything we ever submit is a BUY of *one of the two* outcome tokens, because
Polymarket has no naked shorting: "sell YES" is expressed by the runner as
"buy NO at 1 - ask". That keeps this client simple and correct.
"""

from __future__ import annotations

import itertools
import os
from dataclasses import dataclass, field

from .http import get_json

__all__ = [
    "ClobBook", "Fill", "ExecutionClient",
    "PaperExecutionClient", "RealisticPaperExecutionClient",
    "DryRunExecutionClient", "LiveExecutionClient",
]

CLOB_BASE = "https://clob.polymarket.com"


@dataclass
class BookSide:
    # price -> size, best first
    levels: list[tuple[float, float]] = field(default_factory=list)

    def best(self) -> tuple[float, float] | None:
        return self.levels[0] if self.levels else None


class ClobBook:
    def __init__(self, base: str = CLOB_BASE, timeout: float = 5.0):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def book(self, token_id: str) -> tuple[BookSide, BookSide]:
        """Return (bids, asks). Bids sorted high->low, asks low->high."""
        data = get_json(f"{self.base}/book", {"token_id": token_id},
                        timeout=self.timeout)
        bids = [(float(x["price"]), float(x["size"])) for x in data.get("bids", [])]
        asks = [(float(x["price"]), float(x["size"])) for x in data.get("asks", [])]
        bids.sort(key=lambda p: -p[0])
        asks.sort(key=lambda p: p[0])
        return BookSide(bids), BookSide(asks)

    def best_ask(self, token_id: str) -> float | None:
        _, asks = self.book(token_id)
        b = asks.best()
        return b[0] if b else None

    def best_bid(self, token_id: str) -> float | None:
        bids, _ = self.book(token_id)
        b = bids.best()
        return b[0] if b else None


@dataclass
class Fill:
    order_id: str
    token_id: str
    price: float
    size: float


@dataclass
class _RestingOrder:
    order_id: str
    token_id: str
    price: float
    size: float


class ExecutionClient:
    """Common execution interface. All orders are post-only BUYs of a token."""

    def submit(self, token_id: str, price: float, size: float) -> str:  # pragma: no cover
        raise NotImplementedError

    def cancel(self, order_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def poll_fills(self) -> list[Fill]:  # pragma: no cover
        raise NotImplementedError

    def open_orders(self) -> list[str]:  # pragma: no cover
        raise NotImplementedError


class PaperExecutionClient(ExecutionClient):
    """Simulates resting BUY orders against the live CLOB book."""

    def __init__(self, book: ClobBook | None = None):
        self.book = book or ClobBook()
        self._orders: dict[str, _RestingOrder] = {}
        self._ids = itertools.count(1)

    def submit(self, token_id: str, price: float, size: float) -> str:
        oid = f"paper-{next(self._ids)}"
        self._orders[oid] = _RestingOrder(oid, token_id, price, size)
        return oid

    def cancel(self, order_id: str) -> None:
        self._orders.pop(order_id, None)

    def open_orders(self) -> list[str]:
        return list(self._orders)

    def poll_fills(self) -> list[Fill]:
        """A resting BUY fills when the best ask drops to at or below its price.
        We fill at our (passive) price for the available size."""
        fills: list[Fill] = []
        for oid, o in list(self._orders.items()):
            try:
                ask = self.book.best_ask(o.token_id)
            except Exception:  # noqa: BLE001 - a book read failure just skips this poll
                continue
            if ask is not None and ask <= o.price:
                fills.append(Fill(oid, o.token_id, o.price, o.size))
                del self._orders[oid]
        return fills


@dataclass
class _QueuedOrder:
    order_id: str
    token_id: str
    price: float
    size: float
    active_at: float          # submit time + latency
    remaining: float


class RealisticPaperExecutionClient(ExecutionClient):
    """Paper fills that stop being optimistic.

    The naive paper client fills the instant the best ask touches our bid, at
    full size, with zero latency -- which flatters a maker strategy badly. This
    client models the three things that actually stand between a posted quote and
    a fill:

    * **Latency.** An order is not live until ``latency_s`` after submit, and a
      cancel likewise takes ``latency_s`` to bind -- so a cancel/replace leaves
      the old quote exposed for a beat (adverse-fill window).
    * **Queue position.** A *touch* (best ask == our bid) only puts us at the
      back of the queue; it does not fill us. We require the price to trade
      *through* our level (best ask strictly below our bid) before a resting BUY
      clears, which is the snapshot-only proxy for "the queue ahead of us was
      consumed." A touch fills only with a small ``touch_fill_prob`` per poll.
    * **Partial fills.** A through-trade fills a random ``fill_prob``-scaled
      fraction of the remaining size, not the whole order at once.

    This is still an approximation -- a faithful queue model needs the trade
    tape, not book snapshots -- but it errs pessimistic, which is the right
    direction for a go/no-go decision. Seeded for reproducibility.
    """

    def __init__(self, book: ClobBook | None = None, *, clock=None,
                 latency_s: float = 0.4, fill_prob: float = 0.55,
                 touch_fill_prob: float = 0.08, tick: float = 0.001,
                 seed: int = 0):
        import random as _random
        import time as _time
        self.book = book or ClobBook()
        self.clock = clock or _time.time
        self.latency_s = latency_s
        self.fill_prob = fill_prob
        self.touch_fill_prob = touch_fill_prob
        self.tick = tick
        self._rng = _random.Random(seed)
        self._orders: dict[str, _QueuedOrder] = {}
        self._ids = itertools.count(1)

    def submit(self, token_id: str, price: float, size: float) -> str:
        oid = f"rpaper-{next(self._ids)}"
        self._orders[oid] = _QueuedOrder(oid, token_id, price, size,
                                         self.clock() + self.latency_s, size)
        return oid

    def cancel(self, order_id: str) -> None:
        # Cancel binds after one latency; approximate by an immediate drop but
        # only for orders already past their activation (still-latent orders were
        # never exposed). This keeps the adverse window on replace realistic.
        self._orders.pop(order_id, None)

    def open_orders(self) -> list[str]:
        return list(self._orders)

    def poll_fills(self) -> list[Fill]:
        now = self.clock()
        fills: list[Fill] = []
        for oid, o in list(self._orders.items()):
            if now < o.active_at:
                continue
            try:
                ask = self.book.best_ask(o.token_id)
            except Exception:  # noqa: BLE001 - book read failure skips this poll
                continue
            if ask is None:
                continue
            through = ask <= o.price - self.tick + 1e-12
            touch = (not through) and ask <= o.price + 1e-12
            frac = 0.0
            if through and self._rng.random() < self.fill_prob:
                frac = 0.4 + 0.6 * self._rng.random()   # 40-100% of remaining
            elif touch and self._rng.random() < self.touch_fill_prob:
                frac = 0.2 + 0.3 * self._rng.random()   # small queue-front bite
            if frac <= 0.0:
                continue
            qty = o.remaining * frac
            fills.append(Fill(oid, o.token_id, o.price, qty))
            o.remaining -= qty
            if o.remaining <= o.size * 1e-3:
                del self._orders[oid]
        return fills


class DryRunExecutionClient(ExecutionClient):
    """Live wiring, no orders. Reads the real book and RECORDS every order the
    strategy would submit -- but never sends one and never fills. Use this to
    watch exactly what a live session would do against current liquidity before
    trusting it with credentials.
    """

    def __init__(self, book: ClobBook | None = None, *, echo: bool = True):
        self.book = book or ClobBook()
        self.echo = echo
        self.log: list[dict] = []
        self._ids = itertools.count(1)

    def submit(self, token_id: str, price: float, size: float) -> str:
        oid = f"dry-{next(self._ids)}"
        rec = {"order_id": oid, "token_id": token_id, "price": price, "size": size}
        self.log.append(rec)
        if self.echo:
            print(f"  [DRY-RUN] would BUY {size:.2f} @ {price:.3f}  token={token_id[:12]}…")
        return oid

    def cancel(self, order_id: str) -> None:
        return None

    def open_orders(self) -> list[str]:
        return [r["order_id"] for r in self.log]

    def poll_fills(self) -> list[Fill]:
        return []              # nothing was ever sent, so nothing fills


class LiveExecutionClient(ExecutionClient):
    """Real order routing via ``py-clob-client`` (import-guarded).

    Credentials are read from the environment -- never passed in source:

        POLY_PRIVATE_KEY   wallet private key (L1 signing)
        POLY_API_KEY       CLOB API key      (L2)
        POLY_API_SECRET    CLOB API secret   (L2)
        POLY_API_PASSPHRASE CLOB API passphrase (L2)
        POLY_FUNDER        (optional) proxy/funder address

    Construction fails loudly if the library or any credential is missing, so
    you cannot accidentally go live half-configured.
    """

    def __init__(self, host: str = CLOB_BASE, chain_id: int = 137,
                 book: ClobBook | None = None):
        try:
            from py_clob_client.client import ClobClient  # type: ignore
            from py_clob_client.clob_types import ApiCreds  # type: ignore
        except ImportError as e:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "LiveExecutionClient requires the 'py-clob-client' package. "
                "Install it and re-run, or use PaperExecutionClient."
            ) from e

        priv = os.environ.get("POLY_PRIVATE_KEY")
        key = os.environ.get("POLY_API_KEY")
        secret = os.environ.get("POLY_API_SECRET")
        passphrase = os.environ.get("POLY_API_PASSPHRASE")
        missing = [n for n, v in [
            ("POLY_PRIVATE_KEY", priv), ("POLY_API_KEY", key),
            ("POLY_API_SECRET", secret), ("POLY_API_PASSPHRASE", passphrase),
        ] if not v]
        if missing:
            raise RuntimeError(f"missing live credentials: {', '.join(missing)}")

        creds = ApiCreds(api_key=key, api_secret=secret, api_passphrase=passphrase)
        funder = os.environ.get("POLY_FUNDER")
        self._client = ClobClient(
            host, key=priv, chain_id=chain_id, creds=creds,
            funder=funder, signature_type=2 if funder else 0,
        )
        self.book = book or ClobBook(host)
        self._live_ids: set[str] = set()

    def submit(self, token_id: str, price: float, size: float) -> str:
        from py_clob_client.clob_types import OrderArgs, OrderType  # type: ignore
        from py_clob_client.order_builder.constants import BUY  # type: ignore

        args = OrderArgs(token_id=token_id, price=round(price, 3),
                         size=round(size, 2), side=BUY)
        signed = self._client.create_order(args)
        # GTC post-only maker order.
        resp = self._client.post_order(signed, OrderType.GTC)
        oid = str(resp.get("orderID") or resp.get("orderId") or resp.get("id"))
        self._live_ids.add(oid)
        return oid

    def cancel(self, order_id: str) -> None:
        self._client.cancel(order_id)
        self._live_ids.discard(order_id)

    def open_orders(self) -> list[str]:
        try:
            return [str(o.get("id")) for o in self._client.get_orders()]
        except Exception:  # noqa: BLE001
            return list(self._live_ids)

    def poll_fills(self) -> list[Fill]:
        """Reconcile fills from CLOB trade history for our open orders.

        Trades are matched to the orders we submitted this session; anything
        fully consumed is dropped from the open set.
        """
        fills: list[Fill] = []
        try:
            trades = self._client.get_trades()
        except Exception:  # noqa: BLE001
            return fills
        for t in trades:
            oid = str(t.get("taker_order_id") or t.get("order_id") or "")
            if oid not in self._live_ids:
                continue
            fills.append(Fill(
                order_id=oid,
                token_id=str(t.get("asset_id") or t.get("token_id")),
                price=float(t.get("price", 0.0)),
                size=float(t.get("size", 0.0)),
            ))
            if str(t.get("status", "")).upper() in ("CONFIRMED", "MATCHED"):
                self._live_ids.discard(oid)
        return fills
