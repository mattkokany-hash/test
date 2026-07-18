"""Trade attribution — make the bot's decisions legible.

Every fill the engine makes is the result of a *setup*: a combination of where
we are in the window (phase), how convinced the model is in the direction we
took (conviction), and which outcome token we bought. This module gives those
setups explicit, human-readable names and exact trigger boundaries, so you can
ask "which setups actually make the money, and what exactly triggers them?"

A setup key looks like ``LATE_STRONG_YES`` and decodes to a precise rule:

    phase       from time-remaining fraction  (tau / window length)
        EARLY   tau_frac > 0.66
        MID     0.33 < tau_frac <= 0.66
        LATE    tau_frac <= 0.33
    conviction  from the model's probability for the side we took
        COINFLIP    0.40–0.60      (pure market-making, no view)
        FAVORED     0.60–0.80
        STRONG      > 0.80         (high-confidence convergence)
        CONTRARIAN  < 0.40         (fading the model / betting on mispricing)
    side        YES (we bought YES)  or  NO (we sold YES / bought NO)

These are the *triggers inside the brain*: the exact conditions under which a
trade of each type fires. `top_setups` ranks them by realized profit so you can
see — and optionally focus the bot on — the ones that actually pay.

WARNING: setups ranked on one dataset are *in-sample*. Trading only the top few
because they won yesterday is textbook overfitting (the same survivorship trap
as the viral screenshots). Always re-rank on out-of-sample data before trusting
them — `run_setups.py` does exactly that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "Trade", "classify_trigger", "trigger_conditions", "SetupStats",
    "rank_setups", "top_setups",
]

# Bucket boundaries — these ARE the trigger definitions. One source of truth.
_PHASE = [("EARLY", 0.66, 1.01), ("MID", 0.33, 0.66), ("LATE", -0.01, 0.33)]
_CONV = [("CONTRARIAN", -0.01, 0.40), ("COINFLIP", 0.40, 0.60),
         ("FAVORED", 0.60, 0.80), ("STRONG", 0.80, 1.01)]


@dataclass
class Trade:
    market_id: str
    side: str                 # 'buy' (YES) or 'sell' (YES)
    size: float
    price: float              # fill price in YES terms
    fair: float               # model P(Up) at fill
    tau_frac: float           # time remaining / window length at fill
    outcome: float            # 0.0 / 1.0 settlement
    pnl: float                # realized PnL attributed to this fill (net of fee)
    setup: str = ""


def _bucket(table, value: float) -> str:
    for name, lo, hi in table:
        if lo < value <= hi:
            return name
    return table[-1][0]


def _aligned_prob(side: str, fair: float) -> float:
    """Model probability of the outcome this trade needs to win."""
    return fair if side == "buy" else 1.0 - fair


def classify_trigger(side: str, fair: float, tau_frac: float) -> str:
    """Return the setup key (e.g. 'LATE_STRONG_YES') for a fill's conditions."""
    phase = _bucket(_PHASE, max(0.0, min(1.0, tau_frac)))
    conv = _bucket(_CONV, _aligned_prob(side, fair))
    token = "YES" if side == "buy" else "NO"
    return f"{phase}_{conv}_{token}"


def trigger_conditions(setup: str) -> dict:
    """Decode a setup key back into its exact firing conditions (the 'brain'
    rule). Returns readable ranges for phase, conviction, and side."""
    phase, conv, token = setup.split("_")
    p = next(b for b in _PHASE if b[0] == phase)
    c = next(b for b in _CONV if b[0] == conv)
    side = "buy YES" if token == "YES" else "sell YES (buy NO)"
    return {
        "phase": phase,
        "time_remaining_frac": f"{max(0.0, p[1]):.2f}–{min(1.0, p[2]):.2f}",
        "conviction": conv,
        "aligned_model_prob": f"{max(0.0, c[1]):.2f}–{min(1.0, c[2]):.2f}",
        "action": side,
    }


@dataclass
class SetupStats:
    setup: str
    count: int = 0
    total_pnl: float = 0.0
    wins: int = 0
    size: float = 0.0

    @property
    def avg_pnl(self) -> float:
        return self.total_pnl / self.count if self.count else 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.count if self.count else 0.0


def rank_setups(trades: list[Trade]) -> list[SetupStats]:
    """Aggregate trades by setup, sorted by total realized PnL (frequency ×
    profitability), most profitable first."""
    agg: dict[str, SetupStats] = {}
    for t in trades:
        key = t.setup or classify_trigger(t.side, t.fair, t.tau_frac)
        s = agg.setdefault(key, SetupStats(key))
        s.count += 1
        s.total_pnl += t.pnl
        s.size += t.size
        if t.pnl > 1e-9:
            s.wins += 1
    return sorted(agg.values(), key=lambda s: s.total_pnl, reverse=True)


def top_setups(trades: list[Trade], n: int = 5, *,
               min_count: int = 5) -> list[SetupStats]:
    """Top ``n`` setups by total PnL, ignoring ones too rare to trust
    (``min_count``), so a single lucky fill can't crown a setup."""
    ranked = [s for s in rank_setups(trades) if s.count >= min_count]
    return ranked[:n]
