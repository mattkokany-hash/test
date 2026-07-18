"""Model fair value for a short-horizon 'Up / Down' binary.

A window resolves YES (pays $1) if the underlying spot at close ``S_T`` is at or
above the reference/open price ``K``; otherwise it pays $0. We model the log
price as a driftless geometric Brownian motion over the (short) remaining
horizon -- for sub-hour crypto windows the risk-neutral drift is negligible
relative to diffusion, so assuming zero drift is both simpler and less prone to
overfitting a spurious trend.

    ln S_T = ln S_t - 1/2 * sigma^2 * tau + sigma * sqrt(tau) * Z ,  Z ~ N(0,1)

Let d = ln(S_t / K). Then

    P(S_T >= K) = Phi( (d - 1/2 * sigma^2 * tau) / (sigma * sqrt(tau)) )

where Phi is the standard-normal CDF. This is the whole "temporal arbitrage"
edge in one line: it updates continuously as ``S_t`` moves and ``tau`` shrinks,
and it is what we compare against the quoted book to find dislocations.
"""

from __future__ import annotations

import math

__all__ = ["norm_cdf", "norm_pdf", "up_probability", "binary_delta"]


def norm_cdf(x: float) -> float:
    """Standard-normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard-normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _m(spot: float, strike: float, sigma: float, tau: float) -> float:
    """The standardized moneyness argument of Phi in the model above."""
    d = math.log(spot / strike)
    denom = sigma * math.sqrt(tau)
    return (d - 0.5 * sigma * sigma * tau) / denom


def up_probability(
    spot: float,
    strike: float,
    sigma: float,
    tau: float,
    *,
    min_sigma: float = 1e-6,
) -> float:
    """Model probability that the window finishes 'Up' (S_T >= K).

    Parameters
    ----------
    spot   : current underlying price ``S_t``.
    strike : window reference/open price ``K``.
    sigma  : per-sqrt-second volatility of log returns.
    tau    : seconds remaining until resolution.

    Handles the degenerate limits cleanly: at ``tau <= 0`` (or ``sigma`` at the
    floor) the payoff is a step function of whether spot is already above the
    strike.
    """
    if spot <= 0.0 or strike <= 0.0:
        raise ValueError("spot and strike must be positive")

    sigma = max(sigma, min_sigma)

    if tau <= 0.0:
        d = math.log(spot / strike)
        if d > 0.0:
            return 1.0
        if d < 0.0:
            return 0.0
        return 0.5

    return norm_cdf(_m(spot, strike, sigma, tau))


def binary_delta(
    spot: float,
    strike: float,
    sigma: float,
    tau: float,
    *,
    min_sigma: float = 1e-6,
) -> float:
    """Sensitivity of the 'Up' probability to a unit change in ``ln(spot)``.

        d p / d ln S = phi(m) / (sigma * sqrt(tau))

    This is the per-unit-notional underlying-delta of one YES token, and it is
    what the hedge advisor nets across overlapping windows. It blows up as
    ``tau -> 0`` near the money -- which is exactly the gamma risk the
    adverse-selection guard is there to sidestep.
    """
    sigma = max(sigma, min_sigma)
    if tau <= 0.0:
        return 0.0
    m = _m(spot, strike, sigma, tau)
    return norm_pdf(m) / (sigma * math.sqrt(tau))
