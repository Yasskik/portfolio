"""
Unit tests for Retirement & Wealth Planning lifecycle simulation and SWR sweep.
"""

import numpy as np
import pytest
from montecarlo import deterministic_nest_egg, safe_withdrawal_rate_sweep, simulate_retirement_wealth


def test_zero_volatility_deterministic_accumulation():
    """
    Verifies that when volatility is zero, the simulated accumulation matches
    exact deterministic discrete monthly compounding.

    Convention: the expected annual return r is an effective annual rate, so the monthly
    growth factor is (1 + r)^(1/12) (the original code used exp(r/12), i.e. a continuous rate).
    """
    initial_savings = 10000.0
    monthly_contrib = 500.0
    years_acc = 2
    years_ret = 1
    r_ann = 0.06
    vol_ann = 0.0
    annual_withdrawal = 0.0

    res = simulate_retirement_wealth(
        initial_savings=initial_savings,
        monthly_contribution=monthly_contrib,
        years_to_retirement=years_acc,
        years_in_retirement=years_ret,
        annual_withdrawal=annual_withdrawal,
        inflation_rate=0.0,
        expected_annual_return=r_ann,
        annual_volatility=vol_ann,
        n_sims=50,
        seed=42
    )

    # Calculate exact deterministic balance after 24 months
    monthly_growth = (1 + r_ann) ** (1 / 12)
    expected_wealth = initial_savings
    for _ in range(24):
        expected_wealth = expected_wealth * monthly_growth + monthly_contrib

    simulated_nest_egg = res.median_retirement_nest_egg
    assert np.isclose(simulated_nest_egg, expected_wealth, rtol=1e-10)
    assert np.isclose(deterministic_nest_egg(initial_savings, monthly_contrib, years_acc, r_ann), expected_wealth)


def test_safe_withdrawal_rate_monotonicity():
    """Verifies that higher withdrawal rates produce monotonically decreasing (or equal) success rates."""
    swr = safe_withdrawal_rate_sweep(
        initial_savings=200000.0,
        monthly_contribution=1000.0,
        years_to_retirement=10,
        years_in_retirement=25,
        inflation_rate=0.02,
        expected_annual_return=0.07,
        annual_volatility=0.14,
        rate_min=0.03,
        rate_max=0.08,
        num_rates=6,
        n_sims=1000,
        seed=42
    )

    # Success probability should be non-increasing as withdrawal rate rises
    diffs = np.diff(swr.success_probabilities)
    # Allowing small statistical fluctuations within <= 0.02
    assert np.all(diffs <= 0.02)
    assert swr.success_probabilities[0] >= swr.success_probabilities[-1]


def test_extreme_withdrawal_guarantees_ruin():
    """Tests that an unsustainably high withdrawal rate rapidly depletes portfolio."""
    res = simulate_retirement_wealth(
        initial_savings=50000.0,
        monthly_contribution=0.0,
        years_to_retirement=0,
        years_in_retirement=20,
        annual_withdrawal=200000.0,  # 400% of portfolio
        inflation_rate=0.02,
        expected_annual_return=0.05,
        annual_volatility=0.15,
        n_sims=500,
        seed=42
    )

    assert res.success_probability == 0.0
    assert len(res.depletion_years) == 500
    assert np.all(res.depletion_years < 2.0)  # depleted within 2 years
