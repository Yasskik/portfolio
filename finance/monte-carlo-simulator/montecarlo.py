"""Monte Carlo simulation toolkit: portfolio risk, retirement planning and option pricing.

Conventions (also listed in the README):

* Returns. Daily **log** returns r = ln(P_t / P_{t-1}) are used for estimation and simulation.
  Simple returns are only formed when portfolio values are aggregated (exp(r) - 1).
* Annualisation uses 252 trading days: mean x 252, volatility x sqrt(252).
* GBM. If the arithmetic drift is mu and the volatility sigma, the log return per step is
  N((mu - sigma^2/2) dt, sigma^2 dt). The mean of historical *log* returns already equals
  (mu - sigma^2/2) dt, so it is used directly; `arithmetic_to_log_drift` converts if you start
  from an arithmetic mean.
* Correlation. Shocks are z @ L.T where L is the Cholesky factor of the daily covariance
  matrix of log returns (if the matrix is only positive *semi*-definite, e.g. a zero-volatility
  asset, an eigenvalue factor is used instead, which gives the same covariance).
* Rebalancing. "buy_and_hold" (default): units are bought once at t=0 and weights drift.
  "daily": weights are reset to target every day.
* VaR / CVaR are reported as **positive loss amounts** (dollars and % of the starting value)
  over the stated horizon. VaR_a = a-quantile of the loss distribution (linear interpolation,
  same as Excel PERCENTILE.INC); CVaR_a = average loss in the scenarios where loss >= VaR_a.
* Missing data is never invented: tickers without data are reported and dropped, and only
  dates on which every remaining ticker has a price are used (no forward/back filling).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import norm

TRADING_DAYS = 252
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "prices_snapshot.csv"
MIN_RETURN_OBS = 60          # fewer common daily returns than this is "too short to estimate"


# =====================================================================
# 1. Options: Black-Scholes, Greeks, Monte Carlo
# =====================================================================

@dataclass
class OptionGreeks:
    delta: float
    gamma: float
    vega: float     # per 1.00 change in volatility (divide by 100 for "per 1 vol point")
    theta: float    # per year (divide by 365 for "per calendar day")
    rho: float      # per 1.00 change in r (divide by 100 for "per 1%")


@dataclass
class OptionPricingResult:
    bs_price: float
    mc_price_standard: float
    mc_se_standard: float
    mc_price_antithetic: float
    mc_se_antithetic: float
    variance_reduction_ratio: float
    ci_lower: float
    ci_upper: float
    greeks: OptionGreeks
    convergence_steps: np.ndarray
    convergence_prices: np.ndarray
    convergence_ci_lower: np.ndarray
    convergence_ci_upper: np.ndarray
    payoffs: np.ndarray                  # discounted payoffs of all antithetic draws (z and -z)
    z: np.ndarray = field(default=None)  # the m standard-normal draws used for the antithetic pairs
    pair_payoffs: np.ndarray = field(default=None)
    n_pairs: int = 0
    mc_delta: float = float("nan")       # pathwise estimator, antithetic pairs
    mc_vega: float = float("nan")


def _check_type(option_type: str) -> str:
    t = option_type.lower()
    if t not in ("call", "put"):
        raise ValueError(f"Invalid option_type: {option_type}. Must be 'call' or 'put'.")
    return t


def black_scholes_d1_d2(S, K, T, r, sigma, q=0.0):
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)


def black_scholes_price(S: float, K: float, T: float, r: float, sigma: float,
                        q: float = 0.0, option_type: str = "call") -> float:
    """Black-Scholes-Merton price of a European option (continuous r and dividend yield q)."""
    t = _check_type(option_type)
    if S <= 0 or K <= 0:
        raise ValueError("S and K must be positive.")
    if sigma < 0:
        raise ValueError("Volatility cannot be negative.")
    if T <= 0:
        return max(S - K, 0.0) if t == "call" else max(K - S, 0.0)
    if sigma == 0:
        fwd = S * math.exp(-q * T) - K * math.exp(-r * T)
        return max(fwd, 0.0) if t == "call" else max(-fwd, 0.0)
    d1, d2 = black_scholes_d1_d2(S, K, T, r, sigma, q)
    if t == "call":
        return float(S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2))
    return float(K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1))


def black_scholes_greeks(S: float, K: float, T: float, r: float, sigma: float,
                         q: float = 0.0, option_type: str = "call") -> OptionGreeks:
    """Analytical Greeks. Units: vega per 1.00 vol, theta per year, rho per 1.00 rate.

    Limits: at expiry (T <= 0) or with zero volatility the option is a deterministic payoff,
    so delta is the exercise indicator (times e^{-qT}), gamma and vega are 0."""
    t = _check_type(option_type)
    if T <= 0:
        itm = (S > K) if t == "call" else (S < K)
        return OptionGreeks(delta=(1.0 if t == "call" else -1.0) * float(itm), gamma=0.0, vega=0.0, theta=0.0, rho=0.0)
    disc_q, disc_r = math.exp(-q * T), math.exp(-r * T)
    if sigma <= 0:
        fwd = S * disc_q - K * disc_r
        itm = fwd > 0 if t == "call" else fwd < 0
        if not itm:
            return OptionGreeks(0.0, 0.0, 0.0, 0.0, 0.0)
        sgn = 1.0 if t == "call" else -1.0
        return OptionGreeks(delta=sgn * disc_q, gamma=0.0, vega=0.0,
                            theta=sgn * (q * S * disc_q - r * K * disc_r),
                            rho=sgn * K * T * disc_r)
    d1, d2 = black_scholes_d1_d2(S, K, T, r, sigma, q)
    sqrt_t = math.sqrt(T)
    pdf = norm.pdf(d1)
    gamma = disc_q * pdf / (S * sigma * sqrt_t)
    vega = S * disc_q * pdf * sqrt_t
    if t == "call":
        delta = disc_q * norm.cdf(d1)
        theta = -S * disc_q * pdf * sigma / (2 * sqrt_t) - r * K * disc_r * norm.cdf(d2) + q * S * disc_q * norm.cdf(d1)
        rho = K * T * disc_r * norm.cdf(d2)
    else:
        delta = -disc_q * norm.cdf(-d1)
        theta = -S * disc_q * pdf * sigma / (2 * sqrt_t) + r * K * disc_r * norm.cdf(-d2) - q * S * disc_q * norm.cdf(-d1)
        rho = -K * T * disc_r * norm.cdf(-d2)
    return OptionGreeks(float(delta), float(gamma), float(vega), float(theta), float(rho))


def _discounted_payoff(ST, K, r, T, t):
    intrinsic = np.maximum(ST - K, 0.0) if t == "call" else np.maximum(K - ST, 0.0)
    return math.exp(-r * T) * intrinsic


def monte_carlo_option_pricing(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0,
                               option_type: str = "call", n_sims: int = 10000, seed: Optional[int] = None,
                               n_convergence_points: int = 100) -> OptionPricingResult:
    """European option by Monte Carlo under the risk-neutral measure.

    S_T = S exp((r - q - sigma^2/2) T + sigma sqrt(T) Z); price = e^{-rT} E[payoff].

    * Antithetic estimator: m = n_sims // 2 pairs (Z, -Z). The pair average
      Y_j = (f(Z_j) + f(-Z_j)) / 2 values are i.i.d., so the standard error and the 95% CI
      are computed on the m pair averages (not on the 2m correlated payoffs).
    * Standard estimator: an *independent* set of 2m draws from a separate random stream,
      so the two estimates and their standard errors can be compared fairly.
    * Variance-reduction ratio = Var(standard payoff) / (2 Var(pair average)): how many times
      fewer payoff evaluations the antithetic estimator needs for the same precision.
    """
    t = _check_type(option_type)
    if T <= 0:
        raise ValueError("Monte Carlo pricing needs T > 0.")
    n_sims = max(int(n_sims), 200)
    m = n_sims // 2
    ss = np.random.SeedSequence(seed)
    rng_anti, rng_std = [np.random.default_rng(s) for s in ss.spawn(2)]

    drift = (r - q - 0.5 * sigma ** 2) * T
    vol = sigma * math.sqrt(T)
    z = rng_anti.standard_normal(m)
    st_pos = S * np.exp(drift + vol * z)
    st_neg = S * np.exp(drift - vol * z)
    pay_pos = _discounted_payoff(st_pos, K, r, T, t)
    pay_neg = _discounted_payoff(st_neg, K, r, T, t)
    pairs = 0.5 * (pay_pos + pay_neg)
    price_anti = float(pairs.mean())
    se_anti = float(pairs.std(ddof=1) / math.sqrt(m))

    z_ind = rng_std.standard_normal(2 * m)
    pay_ind = _discounted_payoff(S * np.exp(drift + vol * z_ind), K, r, T, t)
    price_std = float(pay_ind.mean())
    se_std = float(pay_ind.std(ddof=1) / math.sqrt(2 * m))
    var_pair = float(pairs.var(ddof=1))
    vr = float(pay_ind.var(ddof=1) / (2 * var_pair)) if var_pair > 0 else float("inf")

    zc = float(norm.ppf(0.975))
    # Pathwise Greeks (antithetic): d payoff / dS and d payoff / d sigma
    def _pathwise(ST, zz):
        ind = (ST > K) if t == "call" else (ST < K)
        sgn = 1.0 if t == "call" else -1.0
        d_s = math.exp(-r * T) * sgn * ind * ST / S
        d_sig = math.exp(-r * T) * sgn * ind * ST * (math.sqrt(T) * zz - sigma * T)
        return d_s, d_sig
    ds1, dv1 = _pathwise(st_pos, z)
    ds2, dv2 = _pathwise(st_neg, -z)

    k = np.unique(np.linspace(1, m, num=max(2, min(n_convergence_points, m)), dtype=int))
    k = k[k >= 2]
    cs, cs2 = np.cumsum(pairs), np.cumsum(pairs ** 2)
    means = cs[k - 1] / k
    var = np.maximum((cs2[k - 1] - k * means ** 2) / (k - 1), 0.0)
    se = np.sqrt(var / k)

    return OptionPricingResult(
        bs_price=black_scholes_price(S, K, T, r, sigma, q, t),
        mc_price_standard=price_std, mc_se_standard=se_std,
        mc_price_antithetic=price_anti, mc_se_antithetic=se_anti,
        variance_reduction_ratio=vr,
        ci_lower=price_anti - zc * se_anti, ci_upper=price_anti + zc * se_anti,
        greeks=black_scholes_greeks(S, K, T, r, sigma, q, t),
        convergence_steps=2 * k, convergence_prices=means,
        convergence_ci_lower=means - zc * se, convergence_ci_upper=means + zc * se,
        payoffs=np.concatenate([pay_pos, pay_neg]), z=z, pair_payoffs=pairs, n_pairs=m,
        mc_delta=float(np.mean(0.5 * (ds1 + ds2))), mc_vega=float(np.mean(0.5 * (dv1 + dv2))),
    )


# =====================================================================
# 2. Market data (never invented)
# =====================================================================

@dataclass
class PriceData:
    prices: pd.DataFrame          # adjusted closes, common dates only
    log_returns: pd.DataFrame
    missing: List[str]            # requested tickers with no usable data
    source: str
    first_date: Optional[pd.Timestamp]
    last_date: Optional[pd.Timestamp]
    dropped_rows: int             # dates removed because at least one ticker had no price
    notes: List[str] = field(default_factory=list)


def clean_tickers(tickers: Sequence[str]) -> List[str]:
    out = []
    for t in tickers:
        t = str(t).strip().upper()
        if t and t not in out:
            out.append(t)
    return out


def _finish(prices: pd.DataFrame, requested: List[str], source: str, notes=None) -> PriceData:
    notes = list(notes or [])
    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()
    have = [t for t in requested if t in prices.columns and prices[t].notna().sum() > 0]
    missing = [t for t in requested if t not in have]
    prices = prices[have]
    before = len(prices)
    prices = prices.dropna(how="any")          # common dates only; nothing filled
    prices = prices[(prices > 0).all(axis=1)]
    dropped = before - len(prices)
    log_ret = np.log(prices / prices.shift(1)).dropna(how="any")
    if have and len(log_ret) < MIN_RETURN_OBS:
        notes.append(f"Only {len(log_ret)} common daily returns; at least {MIN_RETURN_OBS} are needed.")
    return PriceData(prices, log_ret, missing, source,
                     prices.index[0] if len(prices) else None, prices.index[-1] if len(prices) else None,
                     dropped, notes)


def _drop_incomplete_today(prices: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str]]:
    """Yahoo returns a live, still-changing bar for today while the US market is open."""
    if prices.empty:
        return prices, None
    try:
        now_ny = pd.Timestamp.now(tz="America/New_York")
    except Exception:
        return prices, None
    last = pd.Timestamp(prices.index[-1]).date()
    if last == now_ny.date() and (now_ny.hour, now_ny.minute) < (16, 30):
        return prices.iloc[:-1], f"Dropped today's incomplete bar ({last}); data ends at the last close."
    return prices, None


def _years_back(ts: pd.Timestamp, years: float) -> pd.Timestamp:
    """ts minus `years` (calendar years when whole, else 365.25-day years)."""
    if float(years) == int(years):
        return ts - pd.DateOffset(years=int(years))
    return ts - pd.Timedelta(days=round(float(years) * 365.25))


def load_snapshot(tickers: Sequence[str], years: Optional[float] = None,
                  end: Optional[str] = None, path: Path = SNAPSHOT_PATH) -> PriceData:
    """Offline snapshot of adjusted closes shipped in data/ (used by tests and the examples)."""
    req = clean_tickers(tickers)
    snap = pd.read_csv(path, index_col=0, parse_dates=True)
    if end is not None:
        snap = snap[snap.index <= pd.Timestamp(end)]
    if years is not None:
        start = _years_back(snap.index[-1], years)
        snap = snap[snap.index > start]
    sub = snap[[t for t in req if t in snap.columns]]
    return _finish(sub, req, f"offline snapshot ({path.name})")


def fetch_prices(tickers: Sequence[str], years: float = 5, end: Optional[str] = None) -> PriceData:
    """Adjusted daily closes from Yahoo Finance. Failed tickers are reported, never simulated."""
    import yfinance as yf
    req = clean_tickers(tickers)
    if not req:
        raise ValueError("Enter at least one ticker.")
    end_ts = pd.Timestamp(end) if end else pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    start_ts = _years_back(end_ts, years) - pd.Timedelta(days=1)
    notes = []
    try:
        data = yf.download(req, start=start_ts.strftime("%Y-%m-%d"), end=end_ts.strftime("%Y-%m-%d"),
                           auto_adjust=True, progress=False, threads=False)
    except Exception as exc:                     # network error etc.
        return PriceData(pd.DataFrame(), pd.DataFrame(), req, "Yahoo Finance", None, None, 0,
                         [f"Download failed: {exc}"])
    if data is None or len(data) == 0:
        return PriceData(pd.DataFrame(), pd.DataFrame(), req, "Yahoo Finance", None, None, 0,
                         ["Yahoo Finance returned no data."])
    close = data["Close"] if "Close" in data.columns.get_level_values(0) else data
    if isinstance(close, pd.Series):
        close = close.to_frame(req[0])
    close.index = pd.to_datetime(close.index).tz_localize(None) if getattr(close.index, "tz", None) else pd.to_datetime(close.index)
    if end is None:
        close, note = _drop_incomplete_today(close)
        if note:
            notes.append(note)
    return _finish(close, req, "Yahoo Finance (adjusted close)", notes)


# =====================================================================
# 3. Parameter estimation and correlated simulation
# =====================================================================

@dataclass
class AssetParameters:
    tickers: List[str]
    mean_log_daily: np.ndarray
    cov_daily: np.ndarray
    corr: np.ndarray
    vol_annual: np.ndarray
    mean_log_annual: np.ndarray          # 252 x mean daily log return (continuously compounded)
    mean_arith_annual: np.ndarray        # (mean_log + sigma^2/2) x 252: the GBM drift mu
    n_obs: int


def estimate_parameters(log_returns: pd.DataFrame) -> AssetParameters:
    if len(log_returns) < 2:
        raise ValueError("Not enough return observations.")
    x = log_returns.to_numpy(dtype=float)
    mean = x.mean(axis=0)
    cov = np.atleast_2d(np.cov(x, rowvar=False, ddof=1))
    sd = np.sqrt(np.diag(cov))
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = cov / np.outer(sd, sd)
    corr[~np.isfinite(corr)] = 0.0
    np.fill_diagonal(corr, 1.0)
    return AssetParameters(list(log_returns.columns), mean, cov, corr, sd * math.sqrt(TRADING_DAYS),
                           mean * TRADING_DAYS, (mean + 0.5 * np.diag(cov)) * TRADING_DAYS, len(x))


def arithmetic_to_log_drift(mu_arith: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """GBM: E[dS/S] = mu dt  ->  E[d ln S] = (mu - sigma^2/2) dt (the Ito correction)."""
    return np.asarray(mu_arith, dtype=float) - 0.5 * np.diag(np.atleast_2d(cov))


def normalize_weights(weights: Sequence[float]) -> np.ndarray:
    w = np.asarray(weights, dtype=float).ravel()
    if w.size == 0 or not np.all(np.isfinite(w)):
        raise ValueError("Weights must be finite numbers.")
    if np.any(w < 0):
        raise ValueError("Negative weights (short positions) are not supported.")
    s = w.sum()
    if s <= 0:
        raise ValueError("Weights must add up to more than zero.")
    return w / s


def make_positive_definite(cov: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Symmetrise and clip negative eigenvalues (repairs a matrix that is not a valid covariance)."""
    cov = 0.5 * (np.asarray(cov, float) + np.asarray(cov, float).T)
    vals, vecs = np.linalg.eigh(cov)
    if np.any(vals < eps):
        vals = np.maximum(vals, eps)
        cov = vecs @ np.diag(vals) @ vecs.T
        cov = 0.5 * (cov + cov.T)
    return cov


def covariance_factor(cov: np.ndarray) -> Tuple[np.ndarray, str]:
    """Return (A, method) with A @ A.T == cov. Cholesky when cov is positive definite;
    otherwise (e.g. a zero-volatility asset) an eigenvalue square root, which reproduces the
    same covariance exactly."""
    cov = 0.5 * (np.atleast_2d(np.asarray(cov, float)) + np.atleast_2d(np.asarray(cov, float)).T)
    try:
        return np.linalg.cholesky(cov), "cholesky"
    except np.linalg.LinAlgError:
        vals, vecs = np.linalg.eigh(cov)
        if vals.min() < -1e-10 * max(1.0, vals.max()):
            raise ValueError("Covariance matrix is not positive semi-definite; repair it first.")
        return vecs @ np.diag(np.sqrt(np.clip(vals, 0, None))), "eigen"


def _aggregate(log_r_step: np.ndarray, state: np.ndarray, weights: np.ndarray, rebalance: str) -> np.ndarray:
    """Advance one step. buy_and_hold: state = per-asset value; daily: state = portfolio value."""
    if rebalance == "daily":
        return state * (np.expm1(log_r_step) @ weights + 1.0)
    return state * np.exp(log_r_step)


def _simulate_from_generator(initial_value, weights, horizon_days, n_sims, rebalance, step_fn):
    if rebalance not in ("buy_and_hold", "daily"):
        raise ValueError("rebalance must be 'buy_and_hold' or 'daily'.")
    w = normalize_weights(weights)
    paths = np.empty((n_sims, horizon_days + 1))
    paths[:, 0] = initial_value
    if rebalance == "daily":
        state = np.full(n_sims, float(initial_value))
    else:
        state = np.tile(initial_value * w, (n_sims, 1))
    for d in range(horizon_days):
        state = _aggregate(step_fn(d), state, w, rebalance)
        paths[:, d + 1] = state if rebalance == "daily" else state.sum(axis=1)
    return paths


def simulate_gbm_portfolio(initial_value: float, weights: Sequence[float], mean_returns: Sequence[float],
                           cov_matrix: np.ndarray, horizon_days: int = 252, n_sims: int = 10000,
                           seed: Optional[int] = None, rebalance: str = "buy_and_hold") -> np.ndarray:
    """Correlated GBM paths of the portfolio value, shape (n_sims, horizon_days + 1).

    mean_returns: daily mean **log** returns (= (mu - sigma^2/2) per day, already Ito-corrected).
    cov_matrix:   daily covariance of log returns.
    Each day: r = m + A z, z ~ N(0, I), A A^T = cov (Cholesky). Memory is O(n_sims x horizon)."""
    if horizon_days < 1 or n_sims < 1:
        raise ValueError("horizon_days and n_sims must be at least 1.")
    m = np.asarray(mean_returns, dtype=float).ravel()
    A, _ = covariance_factor(cov_matrix)
    if A.shape[0] != m.size or m.size != len(np.asarray(weights).ravel()):
        raise ValueError("weights, mean_returns and cov_matrix must have matching sizes.")
    rng = np.random.default_rng(seed)
    return _simulate_from_generator(initial_value, weights, horizon_days, n_sims, rebalance,
                                    lambda d: m + rng.standard_normal((n_sims, m.size)) @ A.T)


def simulate_asset_log_returns(mean_returns, cov_matrix, n_steps: int, seed=None) -> np.ndarray:
    """Draw (n_steps, n_assets) correlated log returns with the same generator (used in tests)."""
    m = np.asarray(mean_returns, float).ravel()
    A, _ = covariance_factor(cov_matrix)
    return m + np.random.default_rng(seed).standard_normal((n_steps, m.size)) @ A.T


def simulate_bootstrapped_portfolio(initial_value: float, weights: Sequence[float],
                                    historical_log_returns: np.ndarray, horizon_days: int = 252,
                                    n_sims: int = 10000, seed: Optional[int] = None,
                                    rebalance: str = "buy_and_hold", block_size: int = 1) -> np.ndarray:
    """Historical bootstrap. Whole rows (all assets on the same date) are resampled with
    replacement, which keeps the cross-asset correlation and the fat tails of the data.

    block_size = 1: i.i.d. days (destroys volatility clustering / autocorrelation).
    block_size > 1: circular block bootstrap with fixed blocks of consecutive days, which keeps
    short-term dependence (e.g. 21 = about one month)."""
    h = np.atleast_2d(np.asarray(historical_log_returns, dtype=float))
    if h.shape[0] == 1 and len(np.asarray(weights).ravel()) != 1:
        h = h.T
    n_hist = h.shape[0]
    if n_hist < 2:
        raise ValueError("Need at least two historical returns to bootstrap.")
    block = max(1, int(block_size))
    rng = np.random.default_rng(seed)
    if block == 1:
        idx = rng.integers(0, n_hist, size=(n_sims, horizon_days))
    else:
        n_blocks = -(-horizon_days // block)
        starts = rng.integers(0, n_hist, size=(n_sims, n_blocks))
        idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % n_hist).reshape(n_sims, -1)[:, :horizon_days]
    return _simulate_from_generator(initial_value, weights, horizon_days, n_sims, rebalance,
                                    lambda d: h[idx[:, d]])


# =====================================================================
# 4. Risk metrics
# =====================================================================

@dataclass
class PortfolioRiskMetrics:
    initial_value: float
    horizon_days: int
    mean_final_value: float
    median_final_value: float
    std_final_value: float
    p5_value: float
    p25_value: float
    p50_value: float
    p75_value: float
    p95_value: float
    prob_of_loss: float
    var_95_dollar: float
    var_99_dollar: float
    cvar_95_dollar: float
    cvar_99_dollar: float
    var_95_pct: float
    var_99_pct: float
    cvar_95_pct: float
    cvar_99_pct: float
    parametric_var_95_dollar: float
    parametric_var_99_dollar: float
    parametric_cvar_95_dollar: float
    parametric_cvar_99_dollar: float
    parametric_var_95_pct: float
    parametric_var_99_pct: float
    parametric_cvar_95_pct: float
    parametric_cvar_99_pct: float
    historical_var_95_dollar: float          # overlapping horizon-length windows (nan if too few)
    historical_var_99_dollar: float
    historical_cvar_95_dollar: float
    historical_cvar_99_dollar: float
    historical_var_95_pct: float
    historical_var_99_pct: float
    historical_cvar_95_pct: float
    historical_cvar_99_pct: float
    median_max_drawdown: float               # positive fraction, e.g. 0.12 = 12% peak-to-trough
    worst_drawdown_p95: float                # 95th percentile of max drawdown (1 path in 20 is worse)
    worst_drawdown_max: float
    max_drawdowns: np.ndarray
    final_values: np.ndarray
    final_returns: np.ndarray
    hist_sqrt_t_var_95_pct: float = float("nan")   # 1-day historical VaR x sqrt(H) (ignores drift)
    hist_sqrt_t_var_99_pct: float = float("nan")
    hist_windows: int = 0
    param_mu_daily: float = float("nan")
    param_sigma_daily: float = float("nan")


def var_cvar(losses: np.ndarray, level: float) -> Tuple[float, float]:
    """VaR = level-quantile of losses (linear interpolation = Excel PERCENTILE.INC);
    CVaR = mean of losses >= VaR."""
    losses = np.asarray(losses, float)
    v = float(np.quantile(losses, level))
    tail = losses[losses >= v]
    return v, float(tail.mean()) if tail.size else v


def max_drawdowns(paths: np.ndarray) -> np.ndarray:
    """Per path: largest peak-to-trough fall, as a positive fraction of the running peak."""
    paths = np.atleast_2d(paths)
    peak = np.maximum.accumulate(paths, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        dd = np.where(peak > 0, 1.0 - paths / peak, 0.0)
    return dd.max(axis=1)


def portfolio_log_returns(asset_log_returns: np.ndarray, weights: Sequence[float]) -> np.ndarray:
    """Daily log return of a portfolio rebalanced to `weights` each day: ln(sum w_i e^{r_i})."""
    x = np.atleast_2d(np.asarray(asset_log_returns, float))
    w = normalize_weights(weights)
    if x.shape[1] != w.size:
        x = x.reshape(-1, w.size)
    return np.log(np.exp(x) @ w)


def parametric_var(mu_daily: float, sigma_daily: float, horizon_days: int, level: float) -> Tuple[float, float]:
    """Lognormal variance-covariance VaR/CVaR as a fraction of the starting value.

    Horizon log return X ~ N(mu_H, sigma_H) with mu_H = H mu, sigma_H = sqrt(H) sigma.
    VaR = 1 - exp(mu_H - z sigma_H); CVaR = 1 - E[e^X | X <= mu_H - z sigma_H]
        = 1 - exp(mu_H + sigma_H^2/2) Phi(-z - sigma_H) / (1 - level)."""
    z = float(norm.ppf(level))
    mu_h, sd_h = mu_daily * horizon_days, sigma_daily * math.sqrt(horizon_days)
    var = 1.0 - math.exp(mu_h - z * sd_h)
    cvar = 1.0 - math.exp(mu_h + 0.5 * sd_h ** 2) * norm.cdf(-z - sd_h) / (1.0 - level)
    return var, cvar


def historical_window_returns(port_log_returns: np.ndarray, horizon_days: int) -> np.ndarray:
    """Simple returns over every overlapping window of `horizon_days` consecutive days."""
    x = np.asarray(port_log_returns, float)
    if len(x) < horizon_days:
        return np.array([])
    c = np.concatenate([[0.0], np.cumsum(x)])
    return np.expm1(c[horizon_days:] - c[:-horizon_days])


def calculate_portfolio_risk_metrics(paths: np.ndarray, initial_value: float, weights: Sequence[float],
                                     historical_daily_returns: Optional[np.ndarray] = None,
                                     horizon_days: Optional[int] = None,
                                     min_hist_windows: int = 100) -> PortfolioRiskMetrics:
    """Risk statistics over the horizon of the simulated paths. All VaR/CVaR are positive losses."""
    paths = np.atleast_2d(paths)
    H = paths.shape[1] - 1 if horizon_days is None else int(horizon_days)
    if H != paths.shape[1] - 1:
        raise ValueError("horizon_days does not match the simulated paths.")
    final = paths[:, -1]
    losses = initial_value - final
    q = np.quantile(final, [0.05, 0.25, 0.5, 0.75, 0.95])
    v95, c95 = var_cvar(losses, 0.95)
    v99, c99 = var_cvar(losses, 0.99)
    mdd = max_drawdowns(paths)
    nan = float("nan")
    p = dict(pv95=nan, pc95=nan, pv99=nan, pc99=nan, hv95=nan, hc95=nan, hv99=nan, hc99=nan,
             s95=nan, s99=nan, nw=0, mu=nan, sd=nan)
    if historical_daily_returns is not None and len(historical_daily_returns) > 5:
        pr = portfolio_log_returns(historical_daily_returns, weights)
        p["mu"], p["sd"] = float(pr.mean()), float(pr.std(ddof=1))
        p["pv95"], p["pc95"] = parametric_var(p["mu"], p["sd"], H, 0.95)
        p["pv99"], p["pc99"] = parametric_var(p["mu"], p["sd"], H, 0.99)
        one_day_loss = -np.expm1(pr)
        p["s95"] = float(np.quantile(one_day_loss, 0.95)) * math.sqrt(H)
        p["s99"] = float(np.quantile(one_day_loss, 0.99)) * math.sqrt(H)
        win = historical_window_returns(pr, H)
        p["nw"] = int(win.size)
        if win.size >= min_hist_windows:
            p["hv95"], p["hc95"] = var_cvar(-win, 0.95)
            p["hv99"], p["hc99"] = var_cvar(-win, 0.99)
    V = initial_value
    return PortfolioRiskMetrics(
        initial_value=V, horizon_days=H,
        mean_final_value=float(final.mean()), median_final_value=float(q[2]),
        std_final_value=float(final.std(ddof=1)) if final.size > 1 else 0.0,
        p5_value=float(q[0]), p25_value=float(q[1]), p50_value=float(q[2]), p75_value=float(q[3]), p95_value=float(q[4]),
        prob_of_loss=float(np.mean(final < V)),
        var_95_dollar=v95, var_99_dollar=v99, cvar_95_dollar=c95, cvar_99_dollar=c99,
        var_95_pct=v95 / V, var_99_pct=v99 / V, cvar_95_pct=c95 / V, cvar_99_pct=c99 / V,
        parametric_var_95_dollar=p["pv95"] * V, parametric_var_99_dollar=p["pv99"] * V,
        parametric_cvar_95_dollar=p["pc95"] * V, parametric_cvar_99_dollar=p["pc99"] * V,
        parametric_var_95_pct=p["pv95"], parametric_var_99_pct=p["pv99"],
        parametric_cvar_95_pct=p["pc95"], parametric_cvar_99_pct=p["pc99"],
        historical_var_95_dollar=p["hv95"] * V, historical_var_99_dollar=p["hv99"] * V,
        historical_cvar_95_dollar=p["hc95"] * V, historical_cvar_99_dollar=p["hc99"] * V,
        historical_var_95_pct=p["hv95"], historical_var_99_pct=p["hv99"],
        historical_cvar_95_pct=p["hc95"], historical_cvar_99_pct=p["hc99"],
        median_max_drawdown=float(np.median(mdd)), worst_drawdown_p95=float(np.quantile(mdd, 0.95)),
        worst_drawdown_max=float(mdd.max()), max_drawdowns=mdd,
        final_values=final, final_returns=final / V - 1.0,
        hist_sqrt_t_var_95_pct=p["s95"], hist_sqrt_t_var_99_pct=p["s99"], hist_windows=p["nw"],
        param_mu_daily=p["mu"], param_sigma_daily=p["sd"],
    )


# =====================================================================
# 5. Retirement
# =====================================================================

@dataclass
class RetirementSimulationResult:
    total_months: int
    accumulation_months: int
    retirement_months: int
    timeline_years: np.ndarray
    paths: np.ndarray                    # nominal wealth, shape (n_sims, total_months + 1)
    percentile_paths: Dict[str, np.ndarray]
    success_probability: float
    median_retirement_nest_egg: float
    median_terminal_wealth: float
    depletion_years: np.ndarray          # years from today at which failed paths ran out
    failed_sim_count: int
    total_sim_count: int
    success: np.ndarray = None           # bool per path
    nest_eggs: np.ndarray = None         # wealth at retirement per path
    first_withdrawal: float = 0.0        # nominal annual withdrawal in retirement year 1
    real_percentile_paths: Dict[str, np.ndarray] = None
    monthly_log_drift: float = 0.0
    monthly_log_vol: float = 0.0
    median_annual_return: float = 0.0    # exp(12 x drift) - 1


def monthly_log_params(expected_annual_return: float, annual_volatility: float) -> Tuple[float, float]:
    """Monthly log-return mean and sd so that the *expected* annual growth factor is 1 + r.

    Annual log return ~ N(ln(1+r) - sigma^2/2, sigma^2); split evenly over 12 months."""
    if expected_annual_return <= -1:
        raise ValueError("Expected return must be above -100%.")
    if annual_volatility < 0:
        raise ValueError("Volatility cannot be negative.")
    mu_log = math.log1p(expected_annual_return) - 0.5 * annual_volatility ** 2
    return mu_log / 12.0, annual_volatility / math.sqrt(12.0)


def withdrawal_schedule(annual_withdrawal: float, years_to_retirement: int, years_in_retirement: int,
                        inflation_rate: float, in_todays_dollars: bool = False) -> np.ndarray:
    """Monthly withdrawal for each retirement month. The annual amount is paid in 12 equal
    parts at the start of each month and raised by inflation once a year.
    in_todays_dollars=True: the amount is in today's money, so it is first grown by inflation
    over the accumulation years."""
    base = annual_withdrawal * ((1 + inflation_rate) ** years_to_retirement if in_todays_dollars else 1.0)
    yrs = np.arange(years_in_retirement * 12) // 12
    return base / 12.0 * (1 + inflation_rate) ** yrs


def simulate_retirement_wealth(initial_savings: float, monthly_contribution: float, years_to_retirement: int,
                               years_in_retirement: int, annual_withdrawal: float, inflation_rate: float = 0.025,
                               expected_annual_return: float = 0.07, annual_volatility: float = 0.15,
                               n_sims: int = 10000, seed: Optional[int] = None,
                               withdrawal_in_todays_dollars: bool = False,
                               contribution_growth: float = 0.0) -> RetirementSimulationResult:
    """Monthly simulation of saving, then spending.

    * Returns: i.i.d. lognormal monthly returns; `expected_annual_return` is the expected
      (arithmetic) annual return, `annual_volatility` the volatility of annual log returns.
    * Accumulation: each month the balance grows, then the contribution is added (end of month).
      Contributions can rise by `contribution_growth` once a year.
    * Retirement: the monthly withdrawal is taken at the start of the month, then the rest grows.
    * Success = every withdrawal in the plan is paid in full. A path fails in the first month
      its balance is smaller than the withdrawal due (that month is its depletion date)."""
    yt, yr = int(years_to_retirement), int(years_in_retirement)
    if yt < 0 or yr < 1:
        raise ValueError("Years to retirement must be >= 0 and years in retirement >= 1.")
    if min(initial_savings, monthly_contribution, annual_withdrawal) < 0:
        raise ValueError("Amounts cannot be negative.")
    acc, ret = yt * 12, yr * 12
    total = acc + ret
    mu_m, sd_m = monthly_log_params(expected_annual_return, annual_volatility)
    rng = np.random.default_rng(seed)
    w_sched = withdrawal_schedule(annual_withdrawal, yt, yr, inflation_rate, withdrawal_in_todays_dollars)
    contrib = monthly_contribution * (1 + contribution_growth) ** (np.arange(acc) // 12)

    paths = np.empty((n_sims, total + 1))
    paths[:, 0] = initial_savings
    wealth = np.full(n_sims, float(initial_savings))
    failed = np.zeros(n_sims, bool)
    dep_month = np.full(n_sims, -1)
    for mth in range(total):
        g = np.exp(mu_m + sd_m * rng.standard_normal(n_sims))
        if mth < acc:
            wealth = wealth * g + contrib[mth]
        else:
            w = w_sched[mth - acc]
            short = (~failed) & (wealth < w - 1e-9)
            failed |= short
            dep_month[short] = mth
            wealth = np.maximum(wealth - w, 0.0) * g
            wealth[failed] = 0.0
        paths[:, mth + 1] = wealth

    pcts = [5, 25, 50, 75, 95]
    pq = np.percentile(paths, pcts, axis=0)
    deflator = (1 + inflation_rate) ** (np.arange(total + 1) / 12.0)
    rq = np.percentile(paths / deflator, pcts, axis=0)
    nest = paths[:, acc]
    return RetirementSimulationResult(
        total_months=total, accumulation_months=acc, retirement_months=ret,
        timeline_years=np.arange(total + 1) / 12.0, paths=paths,
        percentile_paths={f"p{p}": pq[i] for i, p in enumerate(pcts)},
        success_probability=float(1.0 - failed.mean()),
        median_retirement_nest_egg=float(np.median(nest)), median_terminal_wealth=float(np.median(paths[:, -1])),
        depletion_years=dep_month[failed] / 12.0, failed_sim_count=int(failed.sum()), total_sim_count=n_sims,
        success=~failed, nest_eggs=nest, first_withdrawal=float(w_sched[0] * 12),
        real_percentile_paths={f"p{p}": rq[i] for i, p in enumerate(pcts)},
        monthly_log_drift=mu_m, monthly_log_vol=sd_m, median_annual_return=math.expm1(12 * mu_m),
    )


@dataclass
class SafeWithdrawalRateSweepResult:
    withdrawal_rates: np.ndarray
    success_probabilities: np.ndarray
    annual_withdrawal_amounts: np.ndarray    # rate x median nest egg (for display)
    nest_egg_base: float
    rate_at_90pct_success: Optional[float]
    rate_at_95pct_success: Optional[float]
    years_in_retirement: int = 30


def safe_withdrawal_rate_sweep(initial_savings: float, monthly_contribution: float, years_to_retirement: int,
                               years_in_retirement: int, inflation_rate: float = 0.025,
                               expected_annual_return: float = 0.07, annual_volatility: float = 0.15,
                               rate_min: float = 0.02, rate_max: float = 0.08, num_rates: int = 13,
                               n_sims: int = 5000, seed: Optional[int] = None,
                               nest_egg: Optional[float] = None) -> SafeWithdrawalRateSweepResult:
    """Success probability of the "x% rule" for a grid of initial withdrawal rates.

    As in the 4% rule (Bengen 1994; Trinity study): year-1 withdrawal = rate x portfolio value
    at retirement, then raised by inflation every year, for `years_in_retirement` years. Only the
    retirement phase is simulated, starting from `nest_egg` (default: the median nest egg of the
    accumulation phase). The same random numbers are reused for every rate (common random
    numbers), so the curve is smooth and never rises with the rate."""
    if nest_egg is None:
        acc = simulate_retirement_wealth(initial_savings, monthly_contribution, years_to_retirement, 1, 0.0,
                                         inflation_rate, expected_annual_return, annual_volatility,
                                         n_sims=n_sims, seed=seed)
        nest_egg = acc.median_retirement_nest_egg
    if nest_egg <= 0:
        raise ValueError("The nest egg at retirement must be positive.")
    rates = np.linspace(rate_min, rate_max, num_rates)
    probs = np.array([
        simulate_retirement_wealth(nest_egg, 0.0, 0, years_in_retirement, nest_egg * r, inflation_rate,
                                   expected_annual_return, annual_volatility, n_sims=n_sims,
                                   seed=None if seed is None else seed + 1).success_probability
        for r in rates])
    ok90, ok95 = np.where(probs >= 0.90)[0], np.where(probs >= 0.95)[0]
    return SafeWithdrawalRateSweepResult(rates, probs, rates * nest_egg, float(nest_egg),
                                         float(rates[ok90[-1]]) if ok90.size else None,
                                         float(rates[ok95[-1]]) if ok95.size else None, years_in_retirement)


def deterministic_nest_egg(initial_savings, monthly_contribution, years_to_retirement, expected_annual_return):
    """Zero-volatility check value: FV at the monthly rate (1+r)^(1/12)-1, contributions at month end
    (Excel: =FV((1+r)^(1/12)-1, 12*years, -contribution, -initial))."""
    i = (1 + expected_annual_return) ** (1 / 12) - 1
    n = 12 * years_to_retirement
    if i == 0:
        return initial_savings + monthly_contribution * n
    return initial_savings * (1 + i) ** n + monthly_contribution * ((1 + i) ** n - 1) / i
