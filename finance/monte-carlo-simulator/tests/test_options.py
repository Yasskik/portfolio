"""
Unit tests for Black-Scholes analytical pricing, Greeks, and Monte Carlo option pricing.
"""

import numpy as np
import pytest
from montecarlo import (
    black_scholes_greeks,
    black_scholes_price,
    monte_carlo_option_pricing,
)


def test_put_call_parity():
    """Validates Put-Call Parity: C - P = S * exp(-q*T) - K * exp(-r*T)."""
    S = 100.0
    K = 105.0
    T = 1.0
    r = 0.05
    sigma = 0.20
    q = 0.02

    call = black_scholes_price(S, K, T, r, sigma, q, "call")
    put = black_scholes_price(S, K, T, r, sigma, q, "put")

    expected_diff = S * np.exp(-q * T) - K * np.exp(-r * T)
    assert np.isclose(call - put, expected_diff, atol=1e-7)


def test_mc_option_price_within_ci_of_black_scholes():
    """Verifies Monte Carlo price estimate falls within 95% Confidence Interval."""
    S = 100.0
    K = 100.0
    T = 0.5
    r = 0.04
    sigma = 0.25
    q = 0.01

    # Call test
    res_call = monte_carlo_option_pricing(
        S, K, T, r, sigma, q, option_type="call", n_sims=50000, seed=42
    )
    assert res_call.ci_lower <= res_call.bs_price <= res_call.ci_upper
    assert abs(res_call.mc_price_antithetic - res_call.bs_price) < 0.15

    # Put test
    res_put = monte_carlo_option_pricing(
        S, K, T, r, sigma, q, option_type="put", n_sims=50000, seed=42
    )
    assert res_put.ci_lower <= res_put.bs_price <= res_put.ci_upper
    assert abs(res_put.mc_price_antithetic - res_put.bs_price) < 0.15


def test_antithetic_variates_variance_reduction():
    """Verifies that antithetic variates estimator achieves standard error reduction."""
    S = 100.0
    K = 100.0
    T = 1.0
    r = 0.05
    sigma = 0.30

    res = monte_carlo_option_pricing(
        S, K, T, r, sigma, option_type="call", n_sims=20000, seed=123
    )
    # Antithetic SE should be noticeably lower than standard MC SE
    assert res.mc_se_antithetic < res.mc_se_standard
    assert res.variance_reduction_ratio > 1.0


def test_analytical_greeks_finite_difference():
    """Validates Black-Scholes analytical Greeks against numerical finite differences."""
    S = 100.0
    K = 100.0
    T = 1.0
    r = 0.05
    sigma = 0.20
    q = 0.0

    greeks = black_scholes_greeks(S, K, T, r, sigma, q, "call")

    # Finite difference Delta: (V(S + dS) - V(S - dS)) / (2 * dS)
    dS = 0.01
    price_up = black_scholes_price(S + dS, K, T, r, sigma, q, "call")
    price_down = black_scholes_price(S - dS, K, T, r, sigma, q, "call")
    num_delta = (price_up - price_down) / (2 * dS)
    assert np.isclose(greeks.delta, num_delta, atol=1e-4)

    # Finite difference Gamma: (V(S + dS) - 2*V(S) + V(S - dS)) / (dS^2)
    price_mid = black_scholes_price(S, K, T, r, sigma, q, "call")
    num_gamma = (price_up - 2 * price_mid + price_down) / (dS ** 2)
    assert np.isclose(greeks.gamma, num_gamma, atol=1e-4)

    # Finite difference Vega: (V(sigma + dvol) - V(sigma - dvol)) / (2 * dvol)
    dvol = 0.001
    price_vol_up = black_scholes_price(S, K, T, r, sigma + dvol, q, "call")
    price_vol_down = black_scholes_price(S, K, T, r, sigma - dvol, q, "call")
    num_vega = (price_vol_up - price_vol_down) / (2 * dvol)
    assert np.isclose(greeks.vega, num_vega, atol=1e-3)
