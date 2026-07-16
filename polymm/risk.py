"""Risk engine: pre-trade checks and kill switches.

Every prospective fill passes through ``allow``. Session PnL is tracked so the
daily-loss and drawdown kill switches can trip; once tripped the engine refuses
all *risk-increasing* trades (it will still let you reduce/flatten).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import StrategyConfig
from .inventory import Inventory

__all__ = ["RiskState", "RiskEngine"]


@dataclass
class RiskState:
    peak_equity: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    breaches: list[str] = field(default_factory=list)


class RiskEngine:
    def __init__(self, cfg: StrategyConfig, inventory: Inventory):
        self.cfg = cfg
        self.inv = inventory
        self.state = RiskState()

    def mark(self, marks: dict[str, float]) -> None:
        """Update equity peak and evaluate the kill switches."""
        equity = self.inv.equity(marks)
        self.state.peak_equity = max(self.state.peak_equity, equity)

        if self.inv.realized_pnl <= -self.cfg.max_daily_loss:
            self._halt(f"daily loss limit hit ({self.inv.realized_pnl:.2f})")

        drawdown = self.state.peak_equity - equity
        if drawdown >= self.cfg.max_drawdown:
            self._halt(f"max drawdown hit ({drawdown:.2f})")

    def _halt(self, reason: str) -> None:
        if not self.state.halted:
            self.state.halted = True
            self.state.halt_reason = reason
            self.state.breaches.append(reason)

    def allow(self, market_id: str, side: str, qty: float, marks: dict[str, float]) -> bool:
        """Pre-trade gate. ``side`` in {'buy','sell'}; ``qty`` > 0.

        A trade is permitted if it is risk-*reducing* (moves the position toward
        zero) even when halted; otherwise it must pass the position and gross
        caps and the halt must not be active.
        """
        if qty <= 0.0:
            return False

        pos = self.inv.position(market_id)
        signed = qty if side == "buy" else -qty
        new_qty = pos.qty + signed
        reducing = abs(new_qty) < abs(pos.qty)

        if reducing:
            return True

        if self.state.halted:
            return False

        if abs(new_qty) > self.cfg.max_position_per_market:
            return False

        # Gross exposure with this hypothetical fill applied.
        projected = self.inv.gross_exposure(marks)
        mark = marks.get(market_id, pos.avg_cost)
        projected += (abs(new_qty) - abs(pos.qty)) * mark
        if projected > self.cfg.max_gross_exposure:
            return False

        return True
