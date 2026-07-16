"""EWMA realized-volatility estimator.

Feeds on the same price stream the fair-value model uses. We keep an
exponentially-weighted mean of squared log-returns normalized by the time step,
so the output ``sigma`` is per-sqrt-second and drops straight into
``fairvalue.up_probability`` with no annualization.
"""

from __future__ import annotations

import math

__all__ = ["EwmaVol"]


class EwmaVol:
    def __init__(self, halflife_s: float = 120.0, min_sigma: float = 1e-6):
        if halflife_s <= 0.0:
            raise ValueError("halflife_s must be positive")
        self.halflife_s = halflife_s
        self.min_sigma = min_sigma
        self._var: float | None = None      # EWMA of per-second variance
        self._last_price: float | None = None
        self._last_t: float | None = None

    def update(self, price: float, t: float) -> float:
        """Ingest a (price, timestamp-seconds) sample; return current sigma."""
        if price <= 0.0:
            raise ValueError("price must be positive")

        if self._last_price is None:
            self._last_price, self._last_t = price, t
            return self.sigma

        dt = t - self._last_t
        if dt <= 0.0:
            # Out-of-order or duplicate timestamp: ignore the sample, keep state.
            return self.sigma

        r = math.log(price / self._last_price)
        inst_var = (r * r) / dt  # per-second variance contribution

        # Decay weight for this dt given the half-life.
        alpha = 0.5 ** (dt / self.halflife_s)
        if self._var is None:
            self._var = inst_var
        else:
            self._var = alpha * self._var + (1.0 - alpha) * inst_var

        self._last_price, self._last_t = price, t
        return self.sigma

    @property
    def sigma(self) -> float:
        """Per-sqrt-second volatility estimate (floored)."""
        if self._var is None:
            return self.min_sigma
        return max(math.sqrt(self._var), self.min_sigma)

    def warm(self) -> bool:
        """True once at least one return has been observed."""
        return self._var is not None
