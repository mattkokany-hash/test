"""Central configuration. All time units are SECONDS and volatility is per
sqrt-second, so that ``sigma * sqrt(tau)`` is dimensionless everywhere and no
annualization constant ever has to be threaded through the code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    # ---- Fair-value model -------------------------------------------------
    vol_halflife_s: float = 120.0
    """EWMA half-life for realized-vol estimation, in seconds."""

    min_sigma: float = 1e-6
    """Floor on per-sqrt-second vol to avoid divide-by-zero in the model."""

    # ---- Quoting ----------------------------------------------------------
    base_edge: float = 0.010
    """Minimum half-spread we require *on top of* fees, in probability/price
    units (a binary YES token pays $1, so price == probability)."""

    fee_bps: float = 20.0
    """Round-trip taker/settlement fee assumption, in basis points of notional.
    Baked into the EV gate so we never quote through our own costs."""

    inventory_gamma: float = 0.8
    """Avellaneda-Stoikov style inventory-aversion. Larger => quotes skew harder
    to offload inventory."""

    max_half_spread: float = 0.25
    """Cap on half-spread so quotes stay inside a sane band."""

    tick: float = 0.001
    """Price granularity of the venue (Polymarket is $0.001 / 0.1c)."""

    # ---- Adverse-selection guard -----------------------------------------
    resolution_cutoff_s: float = 15.0
    """Inside this many seconds to resolution, pull quotes entirely: the model
    is racing settlement and flow is maximally toxic."""

    widen_window_s: float = 90.0
    """Start widening spreads linearly once time-to-resolution drops below this,
    to price in the rising adverse-selection / gamma risk."""

    # ---- Sizing (fractional Kelly) ---------------------------------------
    kelly_fraction: float = 0.25
    """Fraction of full Kelly to bet on a given edge. Full Kelly is far too hot
    for a thin, uncertain edge."""

    max_order_size: float = 500.0
    """Hard cap on a single quote's size (in YES-token units / dollars)."""

    # ---- Risk limits ------------------------------------------------------
    max_position_per_market: float = 2000.0
    max_gross_exposure: float = 8000.0
    max_daily_loss: float = 1500.0
    """Kill switch: cumulative realized loss for the session."""

    max_drawdown: float = 2000.0
    """Kill switch: drop from the session equity peak."""

    # ---- Hedging ----------------------------------------------------------
    delta_band: float = 300.0
    """Leave net underlying-delta alone while within +/- this band; hedge the
    excess back to the band edge."""
