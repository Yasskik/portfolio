"""
Regression tests for the bugs found in review, plus the quant conventions the README states.
Each test names the bug or convention it pins down.
"""
import math
import time

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

import montecarlo as mc

# ---------------------------------------------------------------- GBM / correlation


def test_gbm_drift_not_double_ito_corrected():
    """Bug 1: mean of historical log returns was passed as drift and sigma^2/2 was subtracted again.
    The simulated daily log return must have the input mean."""
    m = np.array([0.0004, 0.0001])
    cov = np.array([[0.0004, 0.00006], [0.00006, 0.00005]])
    x = mc.simulate_asset_log_returns(m, cov, 400_000, seed=1)
    se = np.sqrt(np.diag(cov) / len(x))
    assert np.all(np.abs(x.mean(axis=0) - m) < 4 * se)
    # portfolio level: mean daily log growth of a single-asset GBM path equals m
    paths = mc.simulate_gbm_portfolio(1.0, [1.0], [0.0004], [[0.0004]], 252, 20_000, seed=2)
    lr = np.log(paths[:, -1]).mean() / 252
    assert abs(lr - 0.0004) < 4 * math.sqrt(0.0004 / 252 / 20_000)


def test_arithmetic_to_log_drift_is_ito_correction():
    mu = np.array([0.08 / 252])
    cov = np.array([[0.2 ** 2 / 252]])
    assert np.isclose(mc.arithmetic_to_log_drift(mu, cov)[0], (0.08 - 0.02) / 252)


def test_annualisation_uses_252_days():
    pdata = mc.load_snapshot(["SPY", "AGG"], years=5)
    par = mc.estimate_parameters(pdata.log_returns)
    x = pdata.log_returns.to_numpy()
    assert np.allclose(par.vol_annual, x.std(axis=0, ddof=1) * math.sqrt(252))
    assert np.allclose(par.mean_log_annual, x.mean(axis=0) * 252)
    assert np.allclose(par.mean_arith_annual, (x.mean(axis=0) + x.var(axis=0, ddof=1) / 2) * 252)


def test_cholesky_recovers_input_correlation():
    vols = np.array([0.012, 0.004, 0.02])
    corr = np.array([[1, 0.3, -0.4], [0.3, 1, 0.1], [-0.4, 0.1, 1]])
    cov = corr * np.outer(vols, vols)
    x = mc.simulate_asset_log_returns(np.zeros(3), cov, 200_000, seed=3)
    assert np.allclose(np.corrcoef(x, rowvar=False), corr, atol=0.01)
    assert np.allclose(x.std(axis=0), vols, rtol=0.01)
    A, how = mc.covariance_factor(cov)
    assert how == "cholesky" and np.allclose(A @ A.T, cov)


def test_zero_vol_asset_uses_exact_factor():
    """Edge case: a cash-like asset makes the covariance only semi-definite; Cholesky fails,
    the eigen factor must still reproduce the covariance and the asset must grow deterministically."""
    cov = np.array([[0.0001, 0.0], [0.0, 0.0]])
    A, how = mc.covariance_factor(cov)
    assert how == "eigen" and np.allclose(A @ A.T, cov)
    paths = mc.simulate_gbm_portfolio(100.0, [0.0, 1.0], [0.0003, 0.0001], cov, 10, 50, seed=4)
    assert np.allclose(paths[:, -1], 100 * math.exp(0.001))


def test_weights_are_normalised_and_negative_rejected():
    assert np.allclose(mc.normalize_weights([60, 40]), [0.6, 0.4])
    with pytest.raises(ValueError):
        mc.normalize_weights([1.2, -0.2])
    with pytest.raises(ValueError):
        mc.normalize_weights([0, 0])
    a = mc.simulate_gbm_portfolio(1e5, [60, 40], [0.0003, 0.0001], np.diag([1e-4, 1e-5]), 5, 100, seed=5)
    b = mc.simulate_gbm_portfolio(1e5, [0.6, 0.4], [0.0003, 0.0001], np.diag([1e-4, 1e-5]), 5, 100, seed=5)
    assert np.allclose(a, b)


def test_buy_and_hold_vs_daily_rebalancing():
    """Buy and hold: value = sum of each asset's own growth. Daily: value grows by w . simple return."""
    m, cov = np.array([0.0005, 0.0]), np.diag([1e-4, 1e-6])
    x = mc.simulate_asset_log_returns(m, cov, 30, seed=0)
    # same generator draws as simulate_gbm_portfolio with n_sims=1? Check the rules directly instead:
    bh = (0.6 * np.exp(x[:, 0].sum()) + 0.4 * np.exp(x[:, 1].sum()))
    daily = np.prod(1 + np.expm1(x) @ np.array([0.6, 0.4]))
    state = np.array([[0.6, 0.4]])
    for d in range(30):
        state = mc._aggregate(x[d][None, :], state, np.array([0.6, 0.4]), "buy_and_hold")
    assert np.isclose(state.sum(), bh)
    v = np.array([1.0])
    for d in range(30):
        v = mc._aggregate(x[d][None, :], v, np.array([0.6, 0.4]), "daily")
    assert np.isclose(v[0], daily)


def test_single_ticker_works():
    pdata = mc.load_snapshot(["SPY"], years=3)
    par = mc.estimate_parameters(pdata.log_returns)
    assert par.cov_daily.shape == (1, 1)
    paths = mc.simulate_gbm_portfolio(1e5, [1.0], par.mean_log_daily, par.cov_daily, 21, 500, seed=1)
    met = mc.calculate_portfolio_risk_metrics(paths, 1e5, [1.0], pdata.log_returns.to_numpy(), 21)
    assert met.var_95_dollar > 0 and met.cvar_95_dollar >= met.var_95_dollar
    boot = mc.simulate_bootstrapped_portfolio(1e5, [1.0], pdata.log_returns.to_numpy(), 21, 500, seed=1)
    assert boot.shape == (500, 22)


# ---------------------------------------------------------------- missing data


def test_unknown_ticker_is_reported_not_invented():
    """Bug 3: unknown tickers used to be filled with synthetic random prices."""
    pdata = mc.load_snapshot(["SPY", "NOTATICKER"], years=2)
    assert pdata.missing == ["NOTATICKER"]
    assert list(pdata.prices.columns) == ["SPY"]
    assert not hasattr(mc, "generate_synthetic_prices")


def test_fetch_prices_drops_failed_ticker_and_never_fills(monkeypatch):
    """Mocked Yahoo response: one good ticker, one with no data, one with a gap. Nothing is filled."""
    import yfinance as yf
    idx = pd.bdate_range("2024-01-01", periods=120)
    good = pd.Series(np.linspace(100, 120, 120), idx)
    gappy = good.copy() * 0.5
    gappy.iloc[[10, 11, 50]] = np.nan
    close = pd.DataFrame({"AAA": good, "BBB": gappy, "ZZZ": np.nan})
    data = pd.concat({"Close": close}, axis=1)
    monkeypatch.setattr(yf, "download", lambda *a, **k: data)
    pdata = mc.fetch_prices(["AAA", "BBB", "ZZZ"], years=1, end="2024-07-01")
    assert pdata.missing == ["ZZZ"]
    assert pdata.dropped_rows == 3                       # dates where BBB has no price are removed
    assert len(pdata.prices) == 117 and not pdata.prices.isna().any().any()
    assert pdata.prices.index[0] == idx[0]               # no back-filling of the first rows


def test_fetch_prices_network_error_returns_empty(monkeypatch):
    import yfinance as yf

    def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(yf, "download", boom)
    pdata = mc.fetch_prices(["SPY"], years=1)
    assert pdata.prices.empty and pdata.missing == ["SPY"] and "offline" in pdata.notes[0]


def test_short_history_is_flagged():
    pdata = mc.load_snapshot(["SPY", "AGG"], years=0.1)
    assert len(pdata.log_returns) < mc.MIN_RETURN_OBS
    assert any("needed" in n for n in pdata.notes)


def test_snapshot_has_no_gaps_and_correct_dates():
    pdata = mc.load_snapshot(["SPY", "AGG"], years=5)
    assert str(pdata.last_date.date()) == "2026-09-30"
    assert str(pdata.first_date.date()) == "2021-10-01"
    assert len(pdata.log_returns) == 1253


# ---------------------------------------------------------------- VaR / CVaR / drawdown


def test_var_matches_analytic_lognormal():
    """A single-asset GBM over H days has a lognormal final value: VaR is known in closed form."""
    mu, sd, H = 0.0003, 0.01, 252
    paths = mc.simulate_gbm_portfolio(1.0, [1.0], [mu], [[sd ** 2]], H, 200_000, seed=11)
    met = mc.calculate_portfolio_risk_metrics(paths, 1.0, [1.0], horizon_days=H)
    var_exact, cvar_exact = mc.parametric_var(mu, sd, H, 0.95)
    assert abs(met.var_95_pct - var_exact) < 0.003
    assert abs(met.cvar_95_pct - cvar_exact) < 0.003
    assert np.isclose(var_exact, 1 - math.exp(mu * H - norm.ppf(0.95) * sd * math.sqrt(H)))


def test_var_sign_convention_and_ordering():
    pdata = mc.load_snapshot(["SPY", "AGG"], years=5)
    par = mc.estimate_parameters(pdata.log_returns)
    paths = mc.simulate_gbm_portfolio(1e5, [0.6, 0.4], par.mean_log_daily, par.cov_daily, 252, 5000, seed=42)
    met = mc.calculate_portfolio_risk_metrics(paths, 1e5, [0.6, 0.4], pdata.log_returns.to_numpy(), 252)
    assert met.var_95_dollar > 0                                   # positive loss
    assert np.isclose(met.var_95_dollar, 1e5 - np.quantile(met.final_values, 0.05))
    assert np.isclose(met.var_95_pct, met.var_95_dollar / 1e5)
    assert met.var_95_dollar <= met.cvar_95_dollar <= met.cvar_99_dollar
    assert met.var_95_dollar <= met.var_99_dollar <= met.cvar_99_dollar


def test_var_cvar_hand_example():
    losses = np.arange(1, 101, dtype=float)               # 1..100
    v, c = mc.var_cvar(losses, 0.95)
    assert np.isclose(v, 95.05)                           # PERCENTILE.INC(1..100, 0.95)
    assert np.isclose(c, np.mean([96, 97, 98, 99, 100]))


def test_parametric_var_scales_with_horizon():
    """Bug 6: the horizon log return has mean H*mu and sd sqrt(H)*sigma."""
    v1, _ = mc.parametric_var(0.0, 0.01, 1, 0.99)
    v25, _ = mc.parametric_var(0.0, 0.01, 25, 0.99)
    assert np.isclose(1 - v25, math.exp(-norm.ppf(0.99) * 0.05))
    assert np.isclose(math.log(1 - v25), 5 * math.log(1 - v1))     # sqrt(25) = 5 in log space


def test_historical_windows_count_and_values():
    r = np.array([0.01, -0.02, 0.03, 0.0, 0.01])
    w = mc.historical_window_returns(r, 3)
    assert len(w) == 3
    assert np.allclose(w, np.expm1([0.02, 0.01, 0.04]))
    assert mc.historical_window_returns(r, 10).size == 0


def test_historical_var_needs_enough_windows():
    pdata = mc.load_snapshot(["SPY"], years=1)
    paths = np.full((10, 253), 1e5)
    met = mc.calculate_portfolio_risk_metrics(paths, 1e5, [1.0], pdata.log_returns.to_numpy(), 252)
    assert met.hist_windows < 100 and math.isnan(met.historical_var_95_pct)
    assert not math.isnan(met.parametric_var_95_pct)


def test_max_drawdown_per_path_hand_example():
    paths = np.array([[100, 120, 90, 130, 104],     # peak 120 -> 90 (25%); 130 -> 104 (20%)
                      [100, 101, 102, 103, 104],    # never falls
                      [100, 50, 200, 100, 150]])    # 50% twice
    assert np.allclose(mc.max_drawdowns(paths), [0.25, 0.0, 0.5])


def test_horizon_mismatch_raises():
    with pytest.raises(ValueError):
        mc.calculate_portfolio_risk_metrics(np.ones((5, 11)), 1.0, [1.0], horizon_days=20)


def test_bootstrap_iid_and_block():
    hist = np.array([[0.01, 0.0], [-0.01, 0.002], [0.02, -0.001], [0.0, 0.0]] * 10)
    p1 = mc.simulate_bootstrapped_portfolio(1.0, [0.5, 0.5], hist, 8, 300, seed=1, block_size=1)
    p2 = mc.simulate_bootstrapped_portfolio(1.0, [0.5, 0.5], hist, 8, 300, seed=1, block_size=4)
    assert p1.shape == p2.shape == (300, 9)
    # block bootstrap keeps 4 consecutive historical days: with this periodic history, every
    # 4-day block has the same total, so the final values take very few distinct values
    assert len(np.unique(np.round(p2[:, -1], 12))) <= 4 * 4
    # resampled days are always historical rows (no new returns invented)
    step = np.log(p1[:, 1] / p1[:, 0])
    possible = np.log(np.exp(hist) @ [0.5, 0.5])
    assert all(np.isclose(possible, s).any() for s in step)


# ---------------------------------------------------------------- options


def test_black_scholes_textbook_values():
    """Hull's textbook case: S=K=100, r=5%, sigma=20%, T=1."""
    assert round(mc.black_scholes_price(100, 100, 1, 0.05, 0.2, 0, "call"), 4) == 10.4506
    assert round(mc.black_scholes_price(100, 100, 1, 0.05, 0.2, 0, "put"), 4) == 5.5735
    g = mc.black_scholes_greeks(100, 100, 1, 0.05, 0.2, 0, "call")
    assert round(g.delta, 4) == 0.6368 and round(g.gamma, 5) == 0.01876
    assert round(g.vega, 3) == 37.524 and round(g.theta, 3) == -6.414 and round(g.rho, 3) == 53.232
    gp = mc.black_scholes_greeks(100, 100, 1, 0.05, 0.2, 0, "put")
    assert round(gp.delta, 4) == -0.3632 and round(gp.theta, 4) == -1.6579 and round(gp.rho, 3) == -41.890


def test_greeks_match_finite_differences():
    S, K, T, r, s, q = 105, 95, 0.75, 0.03, 0.3, 0.01
    for t in ("call", "put"):
        g = mc.black_scholes_greeks(S, K, T, r, s, q, t)
        f = lambda **kw: mc.black_scholes_price(**{**dict(S=S, K=K, T=T, r=r, sigma=s, q=q, option_type=t), **kw})
        h = 1e-4
        assert np.isclose(g.delta, (f(S=S + h) - f(S=S - h)) / (2 * h), atol=1e-6)
        assert np.isclose(g.gamma, (f(S=S + 1e-2) - 2 * f() + f(S=S - 1e-2)) / 1e-4, atol=1e-5)
        assert np.isclose(g.vega, (f(sigma=s + h) - f(sigma=s - h)) / (2 * h), atol=1e-4)
        assert np.isclose(g.rho, (f(r=r + h) - f(r=r - h)) / (2 * h), atol=1e-4)
        assert np.isclose(g.theta, -(f(T=T + h) - f(T=T - h)) / (2 * h), atol=1e-4)


def test_put_call_parity():
    for (S, K, T, r, s, q) in [(100, 100, 1, 0.05, 0.2, 0), (80, 100, 2, 0.01, 0.5, 0.03), (120, 90, 0.1, 0.0, 0.1, 0)]:
        c = mc.black_scholes_price(S, K, T, r, s, q, "call")
        p = mc.black_scholes_price(S, K, T, r, s, q, "put")
        assert np.isclose(c - p, S * math.exp(-q * T) - K * math.exp(-r * T))


def test_zero_vol_and_expiry_limits():
    """Bug 4: Greeks were all zero at sigma = 0 or T = 0."""
    assert np.isclose(mc.black_scholes_price(100, 90, 1, 0.05, 0.0), 100 - 90 * math.exp(-0.05))
    g = mc.black_scholes_greeks(100, 90, 1, 0.05, 0.0, 0, "call")
    assert g.delta == 1.0 and g.gamma == 0.0 and np.isclose(g.rho, 90 * math.exp(-0.05))
    assert mc.black_scholes_greeks(100, 90, 0, 0.05, 0.2, 0, "call").delta == 1.0
    assert mc.black_scholes_greeks(100, 90, 0, 0.05, 0.2, 0, "put").delta == 0.0
    assert mc.black_scholes_greeks(80, 90, 0, 0.05, 0.2, 0, "put").delta == -1.0
    assert mc.black_scholes_price(100, 90, 0, 0.05, 0.2, 0, "call") == 10.0
    # near-zero vol converges to the zero-vol limit
    assert np.isclose(mc.black_scholes_greeks(100, 90, 1, 0.05, 1e-6).delta, 1.0)


def test_antithetic_ci_uses_pair_averages():
    """The SE must come from the m i.i.d. pair averages, not from 2m correlated payoffs."""
    res = mc.monte_carlo_option_pricing(100, 100, 1, 0.05, 0.2, n_sims=10_000, seed=42)
    m = res.n_pairs
    assert m == 5000 and res.pair_payoffs.size == m
    se = res.pair_payoffs.std(ddof=1) / math.sqrt(m)
    assert np.isclose(res.mc_se_antithetic, se)
    assert np.isclose(res.ci_upper - res.ci_lower, 2 * norm.ppf(0.975) * se)
    assert res.ci_lower <= res.bs_price <= res.ci_upper
    assert np.isclose(res.pair_payoffs, 0.5 * (res.payoffs[:m] + res.payoffs[m:])).all()


def test_standard_estimator_is_independent_of_antithetic():
    """Bug 2: the 'standard' estimate reused the antithetic draws and was identical."""
    res = mc.monte_carlo_option_pricing(100, 100, 1, 0.05, 0.2, n_sims=10_000, seed=42)
    assert res.mc_price_standard != res.mc_price_antithetic
    assert abs(res.mc_price_standard - res.bs_price) < 4 * res.mc_se_standard
    assert res.variance_reduction_ratio > 1.0


def test_mc_discounting_and_coverage():
    """Prices are discounted at e^{-rT}: across 200 seeds the 95% CI covers BS about 95% of the time."""
    hits = 0
    for sd in range(200):
        r = mc.monte_carlo_option_pricing(100, 110, 2, 0.08, 0.25, 0, "put", n_sims=2000, seed=sd,
                                          n_convergence_points=5)
        hits += r.ci_lower <= r.bs_price <= r.ci_upper
    assert 180 <= hits <= 200


def test_mc_pathwise_greeks_close_to_bs():
    res = mc.monte_carlo_option_pricing(100, 100, 1, 0.05, 0.2, n_sims=200_000, seed=7, n_convergence_points=5)
    assert abs(res.mc_delta - res.greeks.delta) < 0.005
    assert abs(res.mc_vega - res.greeks.vega) / res.greeks.vega < 0.02


def test_convergence_ci_shrinks():
    res = mc.monte_carlo_option_pricing(100, 100, 1, 0.05, 0.2, n_sims=20_000, seed=1)
    w = res.convergence_ci_upper - res.convergence_ci_lower
    assert w[-1] < w[len(w) // 10] and res.convergence_steps[-1] == 20_000
    assert np.isclose(res.convergence_prices[-1], res.mc_price_antithetic)


# ---------------------------------------------------------------- reproducibility / performance


def test_seed_reproducibility_everywhere():
    a = mc.monte_carlo_option_pricing(100, 100, 1, 0.05, 0.2, n_sims=4000, seed=9)
    b = mc.monte_carlo_option_pricing(100, 100, 1, 0.05, 0.2, n_sims=4000, seed=9)
    assert a.mc_price_antithetic == b.mc_price_antithetic and a.mc_price_standard == b.mc_price_standard
    r1 = mc.simulate_retirement_wealth(5e4, 1e3, 5, 5, 3e4, n_sims=500, seed=3)
    r2 = mc.simulate_retirement_wealth(5e4, 1e3, 5, 5, 3e4, n_sims=500, seed=3)
    assert np.array_equal(r1.paths, r2.paths)
    h = np.random.default_rng(0).normal(0, 0.01, (300, 2))
    assert np.array_equal(mc.simulate_bootstrapped_portfolio(1, [1, 1], h, 20, 100, seed=4, block_size=5),
                          mc.simulate_bootstrapped_portfolio(1, [1, 1], h, 20, 100, seed=4, block_size=5))


def test_performance_10k_sims():
    pdata = mc.load_snapshot(["SPY", "AGG", "QQQ", "GLD"], years=5)
    par = mc.estimate_parameters(pdata.log_returns)
    t0 = time.perf_counter()
    paths = mc.simulate_gbm_portfolio(1e5, [0.4, 0.3, 0.2, 0.1], par.mean_log_daily, par.cov_daily, 252, 10_000, seed=1)
    mc.calculate_portfolio_risk_metrics(paths, 1e5, [0.4, 0.3, 0.2, 0.1], pdata.log_returns.to_numpy(), 252)
    mc.simulate_retirement_wealth(5e4, 1e3, 25, 30, 6e4, n_sims=10_000, seed=1)
    mc.monte_carlo_option_pricing(100, 100, 1, 0.05, 0.2, n_sims=100_000, seed=1)
    assert time.perf_counter() - t0 < 6.0


# ---------------------------------------------------------------- retirement


def test_retirement_return_convention():
    """Bug 5: 7% must be the expected annual growth (mean factor 1.07), not a continuous drift."""
    mu_m, sd_m = mc.monthly_log_params(0.07, 0.15)
    assert np.isclose(math.exp(12 * mu_m + 0.5 * 12 * sd_m ** 2), 1.07)
    assert np.isclose(sd_m * math.sqrt(12), 0.15)
    res = mc.simulate_retirement_wealth(1.0, 0, 1, 1, 0.0, 0.0, 0.07, 0.15, n_sims=200_000, seed=1)
    assert abs(res.nest_eggs.mean() - 1.07) < 0.002
    assert np.isclose(res.median_annual_return, math.exp(math.log(1.07) - 0.15 ** 2 / 2) - 1)


def test_withdrawal_schedule_inflation_steps_yearly():
    w = mc.withdrawal_schedule(60_000, 25, 3, 0.025)
    assert np.allclose(w[:12], 5000) and np.allclose(w[12:24], 5125) and np.isclose(w[24], 5000 * 1.025 ** 2)
    wt = mc.withdrawal_schedule(60_000, 25, 1, 0.025, in_todays_dollars=True)
    assert np.isclose(wt[0] * 12, 60_000 * 1.025 ** 25)


def test_success_definition_zero_vol():
    """With zero volatility the plan either always succeeds or always fails, exactly when a hand loop says."""
    def hand(P, W, r, years):
        g = (1 + r) ** (1 / 12)
        for mth in range(years * 12):
            w = W / 12 * 1.02 ** (mth // 12)
            if P < w - 1e-9:
                return False, mth
            P = (P - w) * g
        return True, None
    for W in (40_000, 70_000, 90_000):
        ok, mth = hand(1e6, W, 0.05, 30)
        res = mc.simulate_retirement_wealth(1e6, 0, 0, 30, W, 0.02, 0.05, 0.0, n_sims=20, seed=0)
        assert res.success_probability == (1.0 if ok else 0.0)
        if not ok:
            assert np.allclose(res.depletion_years, mth / 12)


def test_failed_paths_stay_at_zero():
    res = mc.simulate_retirement_wealth(1e5, 0, 0, 10, 50_000, n_sims=200, seed=1)
    assert res.success_probability == 0.0
    assert np.all(res.paths[:, -1] == 0) and np.all(res.paths >= 0)


def test_requested_sample_and_independent_loop():
    """The report's sample: $50k + $1k/month for 25y, then $60k/yr (+2.5%/yr) for 30y; 7%/15%."""
    res = mc.simulate_retirement_wealth(50_000, 1_000, 25, 30, 60_000, 0.025, 0.07, 0.15, n_sims=10_000, seed=42)
    assert round(res.success_probability, 4) == 0.3433
    assert np.isclose(mc.deterministic_nest_egg(50_000, 1_000, 25, 0.07), 1_054_413.51, atol=0.01)
    # the zero-vol run equals the Excel FV formula
    det = mc.simulate_retirement_wealth(50_000, 1_000, 25, 1, 0, 0.0, 0.07, 0.0, n_sims=2, seed=0)
    assert np.isclose(det.nest_eggs[0], 1_054_413.51, atol=0.01)


def test_swr_sweep_common_random_numbers_monotone():
    """Bug 7: rates must be compared on the same nest egg and the same random numbers."""
    swr = mc.safe_withdrawal_rate_sweep(0, 0, 0, 30, 0.025, 0.07, 0.15, n_sims=3000, seed=1, nest_egg=1e6)
    assert np.all(np.diff(swr.success_probabilities) <= 0)
    assert swr.nest_egg_base == 1e6
    i4 = int(np.argmin(np.abs(swr.withdrawal_rates - 0.04)))
    direct = mc.simulate_retirement_wealth(1e6, 0, 0, 30, 40_000, 0.025, 0.07, 0.15, n_sims=3000, seed=2)
    assert swr.success_probabilities[i4] == direct.success_probability


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        mc.simulate_retirement_wealth(-1, 0, 1, 1, 0)
    with pytest.raises(ValueError):
        mc.monthly_log_params(-1.5, 0.1)
    with pytest.raises(ValueError):
        mc.black_scholes_price(100, 100, 1, 0.05, 0.2, 0, "straddle")
    with pytest.raises(ValueError):
        mc.monte_carlo_option_pricing(100, 100, 0, 0.05, 0.2)
