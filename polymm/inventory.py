"""Position / inventory / PnL bookkeeping.

A position is measured in YES-token units (equivalently dollars of payoff, since
each YES pays $1 on resolution). A short YES position is a long NO position. Cash
tracks realized flows; ``settle`` closes a market at its 0/1 outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Position", "Inventory"]


@dataclass
class Position:
    market_id: str
    qty: float = 0.0          # net YES tokens (negative == long NO)
    avg_cost: float = 0.0     # average entry price of the current net qty

    def notional(self, mark: float) -> float:
        """Signed mark-to-market notional at price ``mark``."""
        return self.qty * mark


@dataclass
class Inventory:
    cash: float = 0.0
    realized_pnl: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)

    def position(self, market_id: str) -> Position:
        return self.positions.setdefault(market_id, Position(market_id))

    def fill(self, market_id: str, side: str, qty: float, price: float) -> None:
        """Apply a fill. ``side`` is 'buy' (acquire YES) or 'sell' (dispose YES).

        Realized PnL is booked when a fill reduces the existing position
        (crosses toward or through zero); the remainder re-prices the average
        cost. Cash moves by -signed_qty * price.
        """
        if qty <= 0.0:
            raise ValueError("qty must be positive")
        signed = qty if side == "buy" else -qty
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")

        pos = self.position(market_id)
        self.cash -= signed * price

        old_qty = pos.qty
        new_qty = old_qty + signed

        if old_qty == 0.0 or (old_qty > 0.0) == (signed > 0.0):
            # Opening or adding in the same direction: blend average cost.
            total = abs(old_qty) + abs(signed)
            pos.avg_cost = (abs(old_qty) * pos.avg_cost + abs(signed) * price) / total
            pos.qty = new_qty
            return

        # Reducing / flipping: realize PnL on the closed portion.
        closed = min(abs(signed), abs(old_qty))
        direction = 1.0 if old_qty > 0.0 else -1.0
        # Long YES closed by a sell profits when price > avg_cost; short is the
        # mirror image. ``direction`` carries the sign.
        self.realized_pnl += closed * (price - pos.avg_cost) * direction

        if abs(signed) <= abs(old_qty):
            pos.qty = new_qty
            if pos.qty == 0.0:
                pos.avg_cost = 0.0
            # avg_cost of the remaining same-direction lot is unchanged.
        else:
            # Flipped through zero: the residual opens a new position at ``price``.
            pos.qty = new_qty
            pos.avg_cost = price

    def settle(self, market_id: str, outcome: float) -> None:
        """Resolve a market to ``outcome`` in {0.0, 1.0} and flatten it."""
        pos = self.positions.get(market_id)
        if pos is None or pos.qty == 0.0:
            if pos is not None:
                pos.qty = 0.0
                pos.avg_cost = 0.0
            return
        # Payoff on YES tokens is ``outcome`` each; realize vs average cost.
        self.realized_pnl += pos.qty * (outcome - pos.avg_cost)
        self.cash += pos.qty * outcome
        pos.qty = 0.0
        pos.avg_cost = 0.0

    def gross_exposure(self, marks: dict[str, float]) -> float:
        """Sum of |notional| across open positions at the supplied marks."""
        return sum(
            abs(p.qty) * marks.get(mid, p.avg_cost)
            for mid, p in self.positions.items()
            if p.qty != 0.0
        )

    def unrealized_pnl(self, marks: dict[str, float]) -> float:
        return sum(
            p.qty * (marks.get(mid, p.avg_cost) - p.avg_cost)
            for mid, p in self.positions.items()
            if p.qty != 0.0
        )

    def equity(self, marks: dict[str, float]) -> float:
        return self.realized_pnl + self.unrealized_pnl(marks)
