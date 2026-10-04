"""Recalculate the exported workbooks in LibreOffice and compare them with the Python engine.

    python scripts/verify_excel.py

For every scenario: every value in the builder's cellmap (summary statistics, VaR/CVaR,
parametric and historical VaR, Black-Scholes prices and Greeks, MC price and CI ...) and every
row-level formula column (losses, returns, portfolio log returns, horizon windows, MC payoffs)
is compared with Python, and the whole workbook is scanned for error values.
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import excel_export as xe  # noqa: E402
import montecarlo as mc  # noqa: E402
from lo_recalc import recalc  # noqa: E402

import openpyxl  # noqa: E402

ERRORS = ("#VALUE!", "#REF!", "#NAME?", "#DIV/0!", "#N/A", "#NUM!", "Err:")


def _close(a, b, rel=1e-9, abs_=1e-7):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=abs_)


def _errors(wb):
    n = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            n += sum(1 for v in row if isinstance(v, str) and v.startswith(ERRORS))
    return n


def _recalc_load(wb, tmp: Path, name: str, save_as: Path | None = None):
    src = tmp / name
    wb.save(src)
    out = recalc(src, tmp / "out")
    if save_as is not None:
        save_as.parent.mkdir(parents=True, exist_ok=True)
        save_as.write_bytes(out.read_bytes())
    return openpyxl.load_workbook(out, data_only=True)


def check_cellmap(vals, cellmap):
    bad = []
    for k, (sh, ref, py) in cellmap.items():
        if py is None or (isinstance(py, float) and not math.isfinite(py)):
            continue
        xv = vals[sh][ref].value
        if not _close(xv, py):
            bad.append((k, sh, ref, xv, py))
    return bad


def portfolio_case(tickers, weights, years, H, n, seed, method="gbm", rebalance="buy_and_hold", block=1):
    pdata = mc.load_snapshot(tickers, years=years)
    par = mc.estimate_parameters(pdata.log_returns)
    hist = pdata.log_returns.to_numpy()
    if method == "gbm":
        paths = mc.simulate_gbm_portfolio(100_000, weights, par.mean_log_daily, par.cov_daily, H, n, seed, rebalance)
        label = "Correlated GBM (Cholesky)"
    else:
        paths = mc.simulate_bootstrapped_portfolio(100_000, weights, hist, H, n, seed, rebalance, block)
        label = f"Historical bootstrap (block {block})"
    met = mc.calculate_portfolio_risk_metrics(paths, 100_000, weights, hist, H)
    wb, cm = xe.build_portfolio_workbook(pdata, weights, paths, met, label, rebalance, seed)
    return pdata, paths, met, wb, cm


def check_portfolio(case, tmp: Path, save_as=None):
    pdata, paths, met, wb, cm = case
    vals = _recalc_load(wb, tmp, "portfolio.xlsx", save_as)
    bad = check_cellmap(vals, cm)
    n_checked = len(cm)
    sim = vals["Simulations"]
    for i in range(paths.shape[0]):
        loss = sim.cell(i + 2, 4).value
        if not _close(loss, 100_000 - paths[i, -1]):
            bad.append(("loss row", "Simulations", i + 2, loss, 100_000 - paths[i, -1]))
    n_checked += paths.shape[0]
    hs = vals["History"]
    na = pdata.prices.shape[1]
    pr = mc.portfolio_log_returns(pdata.log_returns.to_numpy(), [hs_w for hs_w in _weights(vals, na)])
    win = mc.historical_window_returns(pr, met.horizon_days)
    prc, pwc = 2 + 2 * na, 4 + 2 * na
    for i in range(len(pr)):
        if not _close(hs.cell(i + 3, prc).value, pr[i], rel=1e-9, abs_=1e-12):
            bad.append(("port log ret", "History", i + 3, hs.cell(i + 3, prc).value, pr[i]))
    for j in range(len(win)):
        r_ = met.horizon_days + 2 + j
        if not _close(hs.cell(r_, pwc).value, win[j], rel=1e-9, abs_=1e-10):
            bad.append(("window", "History", r_, hs.cell(r_, pwc).value, win[j]))
    n_checked += len(pr) + len(win)
    return n_checked, bad, _errors(vals)


def _weights(vals, na):
    return [vals["Summary"].cell(13 + j, 2).value for j in range(na)]


def retirement_case(P, C, yt, yr, W, inf, r, s, n, seed, today=False):
    res = mc.simulate_retirement_wealth(P, C, yt, yr, W, inf, r, s, n_sims=n, seed=seed, withdrawal_in_todays_dollars=today)
    swr = mc.safe_withdrawal_rate_sweep(P, C, yt, yr, inf, r, s, n_sims=2000, seed=seed)
    wb, cm = xe.build_retirement_workbook(res, swr, P, C, yt, yr, W, inf, r, s, today, seed)
    return res, wb, cm


def check_retirement(case, tmp: Path, save_as=None):
    res, wb, cm = case
    vals = _recalc_load(wb, tmp, "retirement.xlsx", save_as)
    bad = check_cellmap(vals, cm)
    return len(cm), bad, _errors(vals)


def options_case(S, K, T, r, sig, q, typ, n, seed):
    opt = mc.monte_carlo_option_pricing(S, K, T, r, sig, q, typ, n_sims=n, seed=seed)
    wb, cm = xe.build_options_workbook(opt, S, K, T, r, sig, q, typ, seed)
    return opt, wb, cm


def check_options(case, tmp: Path, save_as=None):
    opt, wb, cm = case
    vals = _recalc_load(wb, tmp, "options.xlsx", save_as)
    bad = check_cellmap(vals, cm)
    ws = vals["Monte Carlo"]
    for i in range(opt.n_pairs):
        v = ws.cell(12 + i, 6).value
        if not _close(v, opt.pair_payoffs[i], rel=1e-9, abs_=1e-9):
            bad.append(("pair payoff", "Monte Carlo", 12 + i, v, opt.pair_payoffs[i]))
    return len(cm) + opt.n_pairs, bad, _errors(vals)


PORTFOLIOS = {
    "60/40 SPY/AGG, GBM, 1y, 10k sims": (["SPY", "AGG"], [0.6, 0.4], 5, 252, 10_000, 42, "gbm", "buy_and_hold", 1),
    "4 assets, GBM, daily rebalanced, 63d": (["SPY", "QQQ", "TLT", "GLD"], [0.35, 0.25, 0.25, 0.15], 5, 63, 5_000, 7, "gbm", "daily", 1),
    "60/40, block bootstrap (21d), 1y": (["SPY", "AGG"], [0.6, 0.4], 10, 252, 5_000, 1, "boot", "buy_and_hold", 21),
    "single ticker SPY, iid bootstrap, 10d": (["SPY"], [1.0], 3, 10, 3_000, 3, "boot", "buy_and_hold", 1),
}
RETIREMENTS = {
    "50k + 1k/mo 25y, 60k/yr 30y": (50_000, 1_000, 25, 30, 60_000, 0.025, 0.07, 0.15, 10_000, 42, False),
    "same, 60k in today's money": (50_000, 1_000, 25, 30, 60_000, 0.025, 0.07, 0.15, 5_000, 42, True),
    "already retired, 4% rule": (1_000_000, 0, 0, 30, 40_000, 0.025, 0.07, 0.15, 5_000, 1, False),
}
OPTIONS = {
    "textbook call S=K=100": (100, 100, 1, 0.05, 0.20, 0.0, "call", 10_000, 42),
    "textbook put S=K=100": (100, 100, 1, 0.05, 0.20, 0.0, "put", 10_000, 42),
    "OTM call with dividend": (100, 120, 0.5, 0.03, 0.35, 0.02, "call", 6_000, 5),
}

if __name__ == "__main__":
    total_bad = 0
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for name, args in PORTFOLIOS.items():
            n, bad, err = check_portfolio(portfolio_case(*args), tmp)
            total_bad += len(bad) + err
            print(f"PORTFOLIO  {name:42s} {n:7,d} values compared, {len(bad)} mismatches, {err} error cells")
            for b in bad[:5]:
                print("   ", b)
        for name, args in RETIREMENTS.items():
            n, bad, err = check_retirement(retirement_case(*args), tmp)
            total_bad += len(bad) + err
            print(f"RETIRE     {name:42s} {n:7,d} values compared, {len(bad)} mismatches, {err} error cells")
            for b in bad[:5]:
                print("   ", b)
        for name, args in OPTIONS.items():
            n, bad, err = check_options(options_case(*args), tmp)
            total_bad += len(bad) + err
            print(f"OPTION     {name:42s} {n:7,d} values compared, {len(bad)} mismatches, {err} error cells")
            for b in bad[:5]:
                print("   ", b)
    print("TOTAL problems:", total_bad)
    sys.exit(1 if total_bad else 0)
