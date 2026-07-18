import math

from polymm.fairvalue import up_probability, binary_delta, norm_cdf


def test_at_the_money_is_half():
    # Spot == strike, symmetric diffusion => ~0.5 (tiny drift correction).
    p = up_probability(spot=100.0, strike=100.0, sigma=0.001, tau=100.0)
    assert abs(p - 0.5) < 0.02


def test_monotonic_in_spot():
    lo = up_probability(99.0, 100.0, 0.001, 100.0)
    mid = up_probability(100.0, 100.0, 0.001, 100.0)
    hi = up_probability(101.0, 100.0, 0.001, 100.0)
    assert lo < mid < hi


def test_converges_to_step_as_tau_shrinks():
    # Well in the money with little time left => near 1.
    p = up_probability(101.0, 100.0, 0.001, tau=1.0)
    assert p > 0.9
    # Below strike with little time left => near 0.
    p = up_probability(99.0, 100.0, 0.001, tau=1.0)
    assert p < 0.1


def test_tau_zero_is_deterministic():
    assert up_probability(101.0, 100.0, 0.001, 0.0) == 1.0
    assert up_probability(99.0, 100.0, 0.001, 0.0) == 0.0
    assert up_probability(100.0, 100.0, 0.001, 0.0) == 0.5


def test_probability_bounds():
    for spot in (80.0, 95.0, 100.0, 105.0, 120.0):
        p = up_probability(spot, 100.0, 0.002, 50.0)
        assert 0.0 <= p <= 1.0


def test_norm_cdf_reference_values():
    assert abs(norm_cdf(0.0) - 0.5) < 1e-12
    assert abs(norm_cdf(1.96) - 0.975) < 1e-3


def test_delta_positive_and_peaks_near_atm():
    atm = binary_delta(100.0, 100.0, 0.001, 100.0)
    otm = binary_delta(90.0, 100.0, 0.001, 100.0)
    assert atm > 0.0
    assert atm > otm  # sensitivity is largest near the money


def test_delta_matches_finite_difference():
    spot, strike, sigma, tau = 100.5, 100.0, 0.0015, 80.0
    analytic = binary_delta(spot, strike, sigma, tau)
    h = 1e-4
    up = up_probability(math.exp(math.log(spot) + h), strike, sigma, tau)
    dn = up_probability(math.exp(math.log(spot) - h), strike, sigma, tau)
    numeric = (up - dn) / (2 * h)
    assert abs(analytic - numeric) / analytic < 1e-3
