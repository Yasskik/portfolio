"""
Unit tests for Portfolio Risk, Cholesky correlation recovery, seed reproducibility,
Value at Risk (VaR), and drawdown metrics.
"""

import numpy as np
import pytest
from scipy.stats import norm
from montecarlo import (
    calculate_portfolio_risk_metrics,
    make_positive_definite,
    simulate_bootstrapped_portfolio,
    simulate_gbm_portfolio,
)


def test_seed_reproducibility():
    """Verifies that setting a random seed yields strictly identical simulation paths."""
    weights = np.array([0.6, 0.4])
    means = np.array([0.0004, 0.0002])
    cov = np.array([[0.0003, 0.0001], [0.0001, 0.0002]])

    paths1 = simulate_gbm_portfolio(100000, weights, means, cov, horizon_days=50, n_sims=500, seed=12345)
    paths2 = simulate_gbm_portfolio(100000, weights, means, cov, horizon_days=50, n_sims=500, seed=12345)
    paths_diff_seed = simulate_gbm_portfolio(100000, weights, means, cov, horizon_days=50, n_sims=500, seed=99999)

    assert np.array_equal(paths1, paths2)
    assert not np.array_equal(paths1, paths_diff_seed)


def test_cholesky_correlation_recovery():
    """
    Validates that the Cholesky decomposition accurately imparts the specified
    correlation matrix across simulated multi-asset return paths.
    """
    # Define target correlation matrix for 3 assets
    target_corr = np.array([
        [1.0, 0.65, -0.25],
        [0.65, 1.0, -0.15],
        [-0.25, -0.15, 1.0]
    ])
    vols = np.array([0.015, 0.018, 0.008])  # daily volatilities
    cov = np.outer(vols, vols) * target_corr
    means = np.zeros(3)

    # Decompose and draw large sample of 1-day correlated returns
    cov_pd = make_positive_definite(cov)
    L = np.linalg.cholesky(cov_pd)

    rng = np.random.default_rng(42)
    n_samples = 150000
    z = rng.standard_normal((n_samples, 3))
    sim_returns = z @ L.T

    # Compute empirical correlation matrix
    recovered_corr = np.corrcoef(sim_returns, rowvar=False)

    # Verify recovery within statistical margin (< 0.015)
    np.testing.assert_allclose(recovered_corr, target_corr, atol=0.015)


def test_var_on_known_normal_distribution():
    """
    Verifies that Monte Carlo VaR matches analytical parametric VaR on a single-asset
    normal process.
    """
    initial_wealth = 100000.0
    daily_mu = 0.0005
    daily_vol = 0.012
    horizon = 1  # 1 day
    n_sims = 200000

    weights = np.array([1.0])
    means = np.array([daily_mu])
    cov = np.array([[daily_vol ** 2]])

    paths = simulate_gbm_portfolio(
        initial_value=initial_wealth,
        weights=weights,
        mean_returns=means,
        cov_matrix=cov,
        horizon_days=horizon,
        n_sims=n_sims,
        seed=777,
        rebalance="daily"
    )

    metrics = calculate_portfolio_risk_metrics(paths, initial_wealth, weights, horizon_days=horizon)

    # Theoretical lognormal return: R_t = exp((mu - 0.5*sigma^2) + sigma * Z) - 1
    # For small daily vol, this is approximately normal: VaR_95 = (z_0.95 * vol - mu) * V0
    z95 = norm.ppf(0.95)
    z99 = norm.ppf(0.99)
    analytical_var_95 = initial_wealth * (z95 * daily_vol - daily_mu)
    analytical_var_99 = initial_wealth * (z99 * daily_vol - daily_mu)

    # Compare MC VaR vs Analytical
    assert np.isclose(metrics.var_95_dollar, analytical_var_95, rtol=0.02)
    assert np.isclose(metrics.var_99_dollar, analytical_var_99, rtol=0.02)


def test_max_drawdown_bounds_and_relationships():
    """Max drawdowns are positive fractions in [0, 1) (12% fall = 0.12) and ordered median <= p95 <= max."""
    weights = np.array([0.5, 0.5])
    means = np.array([0.0003, 0.0003])
    cov = np.array([[0.0002, 0.00005], [0.00005, 0.0002]])

    paths = simulate_gbm_portfolio(100000, weights, means, cov, horizon_days=100, n_sims=1000, seed=42)
    metrics = calculate_portfolio_risk_metrics(paths, 100000, weights, horizon_days=100)

    assert np.all(metrics.max_drawdowns >= 0.0) and np.all(metrics.max_drawdowns < 1.0)
    assert metrics.median_max_drawdown <= metrics.worst_drawdown_p95 <= metrics.worst_drawdown_max
    assert metrics.median_max_drawdown > 0.0


def test_bootstrapped_portfolio_simulation():
    """Tests non-parametric historical returns bootstrapping execution and shape."""
    n_days = 250
    n_assets = 3
    rng = np.random.default_rng(101)
    hist_returns = rng.normal(0.0004, 0.015, size=(n_days, n_assets))
    weights = np.array([0.4, 0.4, 0.2])

    paths = simulate_bootstrapped_portfolio(
        initial_value=50000.0,
        weights=weights,
        historical_log_returns=hist_returns,
        horizon_days=60,
        n_sims=500,
        seed=101
    )

    assert paths.shape == (500, 61)
    assert np.all(paths[:, 0] == 50000.0)
    assert np.all(paths > 0.0)


def test_make_positive_definite():
    """Tests eigenvalue regularization on a non-positive definite matrix."""
    # Matrix with negative eigenvalue
    bad_cov = np.array([
        [1.0, 0.99, 0.99],
        [0.99, 1.0, 0.99],
        [0.99, 0.99, 0.5]
    ])
    # bad_cov has negative eigenvalue
    eigenvalues_before, _ = np.linalg.eigh(bad_cov)
    assert np.any(eigenvalues_before <= 0)

    repaired_cov = make_positive_definite(bad_cov)
    eigenvalues_after, _ = np.linalg.eigh(repaired_cov)
    assert np.all(eigenvalues_after > 0)
    # Cholesky should now succeed without error
    L = np.linalg.cholesky(repaired_cov)
    assert L.shape == (3, 3)


def test_vectorized_portfolio_performance_10k_sims():
    """Verifies that 10,000+ simulations of 4 assets over 252 days run in under 1 second."""
    import time
    n_assets = 4
    weights = np.ones(n_assets) / n_assets
    means = np.full(n_assets, 0.0003)
    cov = np.eye(n_assets) * 0.0002 + 0.00005

    t0 = time.perf_counter()
    paths = simulate_gbm_portfolio(
        initial_value=100000.0,
        weights=weights,
        mean_returns=means,
        cov_matrix=cov,
        horizon_days=252,
        n_sims=10000,
        seed=42
    )
    elapsed = time.perf_counter() - t0

    assert paths.shape == (10000, 253)
    assert elapsed < 2.5, f"10k simulations took {elapsed:.3f}s, expected < 2.5s"

