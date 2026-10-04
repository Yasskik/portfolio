"""Monte Carlo Simulation Toolkit: portfolio risk, retirement planning and option pricing (Streamlit).

Layout: sidebar (module, simulation settings) -> inputs panel -> key results -> charts in tabs -> Excel export.
The look comes from ui_theme.py, the shared design system of the finance portfolio (vendored into this project).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import excel_export as xe
import montecarlo as mc
import ui_theme as ui

ui.apply("Monte Carlo Simulation Toolkit · Yamen Agha", icon=":material/scatter_plot:")

MAX_CELLS = 15_000_000          # n_sims x (horizon + 1) cap for the portfolio paths (~120 MB)
MODULES = ["Portfolio risk (VaR)", "Retirement plan", "Option pricing"]


def money(x):
    return "n/a" if x is None or not np.isfinite(x) else f"${x:,.0f}"


def esc(text):
    """Escape $ for st.markdown / st.caption (a pair of $ signs would be rendered as LaTeX)."""
    return text.replace("$", "\\$")


def pct(x, d=1):
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:.{d}f}%"


def fan(x, pctl, title, subtitle, xlab, ylab, sample=None, ref=None, vline=None, cap=None, color=ui.ACCENT_2,
        rangeslider=False):
    """Fan chart: 5-95 and 25-75 percentile bands, the median, optional sample paths and reference lines."""
    fig = go.Figure()
    if sample is not None:
        for p in sample:
            fig.add_trace(go.Scatter(x=x, y=p, mode="lines", line=dict(color=ui.rgba(ui.MUTED, 0.16), width=1),
                                     showlegend=False, hoverinfo="skip"))
    for lo, hi, a, name in (("p5", "p95", 0.14, "5th-95th percentile"), ("p25", "p75", 0.30, "25th-75th percentile")):
        fig.add_trace(go.Scatter(x=x, y=pctl[hi], mode="lines", line=dict(width=0.6, color=ui.rgba(color, 0.5)),
                                 name=f"{hi[1:]}th", showlegend=False, legendgroup=name,
                                 hovertemplate="%{y:$,.0f}"))
        fig.add_trace(go.Scatter(x=x, y=pctl[lo], mode="lines", line=dict(width=0.6, color=ui.rgba(color, 0.5)),
                                 fill="tonexty", fillcolor=ui.rgba(color, a), name=name, legendgroup=name,
                                 hovertemplate="%{y:$,.0f}"))
    fig.add_trace(go.Scatter(x=x, y=pctl["p50"], mode="lines", line=dict(color=color, width=2.8), name="Median",
                             hovertemplate="%{y:$,.0f}"))
    if ref is not None:
        fig.add_hline(y=ref, line_dash="dash", line_color=ui.NEG, line_width=1.2,
                      annotation_text=f"Start {money(ref)}", annotation_position="bottom right",
                      annotation_font=dict(color=ui.NEG, size=11.5))
    if vline is not None:
        fig.add_vline(x=vline[0], line_dash="dash", line_color=ui.WARN, line_width=1.2, annotation_text=vline[1],
                      annotation_font=dict(color=ui.WARN, size=11.5))
    ui.style_fig(fig, title, subtitle, height=500, xtitle=xlab, ytitle=ylab)
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    if cap is not None:
        fig.update_yaxes(range=[0, cap])
    if rangeslider:
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.06, bgcolor=ui.SURFACE_2, bordercolor=ui.HAIRLINE))
    return fig


def str_table(df, index_col, container=None, row_styles=None):
    ui.html_table(df.set_index(index_col), fmt="plain", container=container, row_styles=row_styles)


# ------------------------------------------------------------------ cached computations
@st.cache_data(ttl=3600, show_spinner=False)
def get_prices(tickers: tuple, years: float, source: str):
    if source == "snapshot":
        return mc.load_snapshot(list(tickers), years=years)
    return mc.fetch_prices(list(tickers), years=years)


@st.cache_data(show_spinner=False, max_entries=8)
def run_portfolio(_pdata, key, weights, method, block, drift, rebalance, V0, H, n, seed):
    hist = _pdata.log_returns.to_numpy()
    par = mc.estimate_parameters(_pdata.log_returns)
    if method == "gbm":
        m = par.mean_log_daily if drift == "historical" else -0.5 * np.diag(par.cov_daily)
        paths = mc.simulate_gbm_portfolio(V0, weights, m, par.cov_daily, H, n, seed, rebalance)
    else:
        paths = mc.simulate_bootstrapped_portfolio(V0, weights, hist, H, n, seed, rebalance,
                                                   block if method == "block" else 1)
    met = mc.calculate_portfolio_risk_metrics(paths, V0, weights, hist, H)
    return paths, met, par


@st.cache_data(show_spinner=False, max_entries=8)
def run_retirement(P, C, yt, yr, W, inf, r, s, n, seed, today):
    res = mc.simulate_retirement_wealth(P, C, yt, yr, W, inf, r, s, n_sims=n, seed=seed, withdrawal_in_todays_dollars=today)
    swr = mc.safe_withdrawal_rate_sweep(P, C, yt, yr, inf, r, s, rate_min=0.02, rate_max=0.08, num_rates=13,
                                        n_sims=min(n, 5000), seed=seed, nest_egg=res.median_retirement_nest_egg)
    return res, swr


@st.cache_data(show_spinner=False, max_entries=4)
def excel_bytes(kind, key, _args):
    """Workbook bytes, cached on `key` (the inputs) so a rerun does not rebuild the file."""
    builder = {"portfolio": xe.build_portfolio_workbook, "retirement": xe.build_retirement_workbook,
               "options": xe.build_options_workbook}[kind]
    wb, _ = builder(*_args)
    return xe.to_bytes(wb)


def export(label_note: str, data: bytes, file_name: str, caption: str = "") -> None:
    ui.section("Export", label_note)
    st.download_button("Download Excel workbook (live formulas)", data, file_name=file_name, type="primary",
                       icon=":material/download:", width="stretch",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if caption:
        st.caption(caption)


# ------------------------------------------------------------------ sidebar
ui.sidebar_brand("Monte Carlo Toolkit")
ui.sidebar_section("Module")
module = st.sidebar.radio("Module", MODULES, label_visibility="collapsed",
                          help="Three independent simulators that share the settings below.")
ui.sidebar_section("Simulation")
n_sims = st.sidebar.select_slider("Number of simulations", options=[1_000, 2_500, 5_000, 10_000, 25_000, 50_000],
                                  value=10_000, help="More simulations = smaller Monte Carlo error (it shrinks like 1/√N).")
use_seed = st.sidebar.checkbox("Fixed random seed (reproducible)", value=True,
                               help="The same seed gives the same simulated paths every run.")
seed = int(st.sidebar.number_input("Seed", min_value=0, max_value=2**31 - 1, value=42)) if use_seed else None
st.sidebar.caption("Python, NumPy, SciPy, Streamlit, Plotly, openpyxl. Educational tool, not investment advice.")

ui.masthead("Monte Carlo Simulation Toolkit",
            "Simulate thousands of possible futures to measure portfolio risk, test a retirement plan and price options, "
            "with every result reproducible in Excel.",
            kicker="Risk & simulation",
            meta={"Module": module, "Simulations": f"{n_sims:,}", "Seed": str(seed) if seed is not None else "random"})

# =================================================================== PORTFOLIO
if module == MODULES[0]:
    ui.section("Portfolio risk: VaR, CVaR and drawdown",
               "Correlated GBM (Cholesky) or historical bootstrap. VaR and CVaR are shown as positive losses over the "
               "chosen horizon.", kicker="Inputs")
    presets = {
        "60/40 stocks / bonds (SPY, AGG)": ("SPY, AGG", "60, 40"),
        "Growth + gold (SPY, QQQ, GLD)": ("SPY, QQQ, GLD", "40, 40, 20"),
        "Diversified (SPY, VEA, TLT, IEF, GLD)": ("SPY, VEA, TLT, IEF, GLD", "30, 15, 25, 15, 15"),
        "100% S&P 500 (SPY)": ("SPY", "100"),
        "Custom": ("SPY, QQQ, TLT, GLD", "35, 25, 25, 15"),
    }
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4, gap="medium")
        preset = c1.selectbox("Portfolio", list(presets), help="Pick a preset, then edit tickers and weights freely.")
        source = c2.radio("Data source", ["Yahoo Finance (live)", "Offline snapshot (to 2026-09-30)"], horizontal=False)
        years = c3.selectbox("History used", [1, 2, 3, 5, 10], index=3, format_func=lambda y: f"{y} years",
                             help="Length of the price history used to estimate returns and correlations.")
        rebalance = c4.selectbox("Rebalancing", ["buy_and_hold", "daily"],
                                 format_func=lambda r: "Buy and hold" if r == "buy_and_hold" else "Daily to target")
        c1, c2, c3, c4 = st.columns(4, gap="medium")
        t_in = c1.text_input("Tickers (comma-separated)", presets[preset][0], key=f"t_{preset}")
        w_in = c2.text_input("Weights (any scale, normalised to 100%)", presets[preset][1], key=f"w_{preset}")
        V0 = c3.number_input("Starting value ($)", 1_000.0, 1e9, 100_000.0, 10_000.0, format="%.0f")
        H = c4.number_input("Horizon (trading days)", 1, 756, 252,
                            help="252 trading days ≈ 1 year, 21 ≈ 1 month, 5 ≈ 1 week.")
        c1, c2, c3 = st.columns([2, 1, 1], gap="medium")
        method_label = c1.radio("Simulation method", ["Correlated GBM (Cholesky)", "Historical bootstrap (i.i.d. days)",
                                                      "Historical block bootstrap"], horizontal=True)
        method = {"C": "gbm", "H": "boot"}[method_label[0]] if "block" not in method_label else "block"
        block = c2.slider("Block length (days)", 5, 63, 21, disabled=method != "block",
                          help="Consecutive days resampled together, which keeps volatility clustering.")
        drift = c3.selectbox("Expected return (GBM)", ["historical", "zero"], disabled=method != "gbm",
                             format_func=lambda d: "Historical mean" if d == "historical" else "Zero (risk only)")

    tickers = mc.clean_tickers(t_in.split(","))
    try:
        raw_w = [float(x) for x in w_in.split(",") if x.strip()]
    except ValueError:
        st.error("Weights must be numbers separated by commas.")
        st.stop()
    if len(raw_w) != len(tickers):
        st.error(f"{len(tickers)} tickers but {len(raw_w)} weights. Enter one weight per ticker.")
        st.stop()
    try:
        weights_all = mc.normalize_weights(raw_w)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    with st.spinner("Loading prices..."):
        pdata = get_prices(tuple(tickers), float(years), "snapshot" if source.startswith("Offline") else "yahoo")
    for note in pdata.notes:
        ui.callout(note, "info", "Data")
    if pdata.missing:
        ui.callout(f"No price data for: {', '.join(pdata.missing)}. These tickers are left out and the remaining "
                   "weights are rescaled. Nothing is filled in or simulated for them.", "warn", "Missing")
    keep = [t for t in tickers if t in pdata.prices.columns]
    if not keep or len(pdata.log_returns) < mc.MIN_RETURN_OBS:
        st.error("Not enough price history to estimate risk (need at least "
                 f"{mc.MIN_RETURN_OBS} common daily returns). Try other tickers, a longer history or the offline snapshot.")
        st.stop()
    weights = mc.normalize_weights([weights_all[tickers.index(t)] for t in keep])
    n_eff = n_sims
    if n_sims * (H + 1) > MAX_CELLS:
        n_eff = int(MAX_CELLS // (H + 1))
        ui.callout(f"{n_sims:,} paths × {H} days would need too much memory; using {n_eff:,} simulations.", "info")
    with st.spinner(f"Simulating {n_eff:,} paths..."):
        key = (tuple(keep), str(pdata.last_date), len(pdata.prices), pdata.source)
        paths, met, par = run_portfolio(pdata, key, tuple(weights), method, block, drift, rebalance,
                                        float(V0), int(H), n_eff, seed)
    st.caption(f"Data: {', '.join(keep)} adjusted closes, {pdata.source}, {pdata.first_date:%Y-%m-%d} to "
               f"{pdata.last_date:%Y-%m-%d} ({len(pdata.log_returns):,} daily log returns, common dates only). "
               f"Weights: {', '.join(f'{t} {w:.0%}' for t, w in zip(keep, weights))}. Horizon {H} trading days ≈ {H / 252:.2f} years.")

    ui.section("Key results", f"Over {H} trading days on a {money(V0)} portfolio.", kicker=f"{n_eff:,} paths")
    med_ret = met.median_final_value / V0 - 1
    ui.kpis([
        dict(label="VaR 95%", value=money(met.var_95_dollar), delta=f"{pct(met.var_95_pct)} of start", tone="neg",
             note="1 in 20 is worse"),
        dict(label="CVaR 95%", value=money(met.cvar_95_dollar), delta=pct(met.cvar_95_pct), tone="neg",
             note="expected shortfall: avg of worst 5%"),
        dict(label="VaR 99% / CVaR 99%", value=money(met.var_99_dollar), delta=pct(met.var_99_pct), tone="neg",
             note=f"CVaR {money(met.cvar_99_dollar)}"),
        dict(label="Probability of a loss", value=pct(met.prob_of_loss), tone="warn",
             delta=f"below {money(V0)}", note=f"after {H} days"),
        dict(label="Median value", value=money(met.median_final_value), delta=pct(med_ret, 1) + " return",
             tone=ui.tone(med_ret), note=f"mean {money(met.mean_final_value)}"),
    ])
    st.caption(esc(f"Median max drawdown {pct(met.median_max_drawdown)}. VaR 95% = start value − 5th percentile; "
                   "CVaR 95% = start value − average of the values at or below that percentile."))

    tab_fan, tab_dist, tab_var, tab_dd, tab_par = st.tabs(
        ["Fan chart", "Distribution & VaR", "VaR methods compared", "Max drawdown", "Inputs: returns & correlation"])
    with tab_fan:
        pq = {f"p{p}": v for p, v in zip([5, 25, 50, 75, 95], np.percentile(paths, [5, 25, 50, 75, 95], axis=0))}
        ui.chart(fan(np.arange(H + 1), pq, f"{n_eff:,} simulated paths of a {money(V0)} portfolio",
                     "Percentile bands across all simulations on each day; grey lines are 40 individual paths. "
                     "Drag the slider to zoom.", "Trading days", "Portfolio value", sample=paths[:40], ref=V0,
                     rangeslider=True))
    with tab_dist:
        a, b = st.columns(2, gap="medium")
        fv = met.final_values
        var95, var99 = V0 - met.var_95_dollar, V0 - met.var_99_dollar
        cvar95 = V0 - met.cvar_95_dollar
        edges = np.histogram_bin_edges(fv, bins=80)
        counts, _ = np.histogram(fv, bins=edges)
        mids = (edges[:-1] + edges[1:]) / 2
        cols = [ui.NEG if m <= var99 else (ui.rgba(ui.NEG, 0.6) if m <= var95 else
                                           (ui.ACCENT_2 if m < V0 else ui.PALETTE[1])) for m in mids]
        fig = go.Figure(go.Bar(x=mids, y=counts, width=np.diff(edges) * 0.96, marker_color=cols, name="Simulations",
                               customdata=np.c_[edges[:-1], edges[1:]],
                               hovertemplate="$%{customdata[0]:,.0f} – $%{customdata[1]:,.0f}<br>%{y:,} paths"
                                             "<extra></extra>"))
        marks = sorted(((var99, "VaR 99%", ui.NEG), (cvar95, "CVaR 95%", ui.WARN), (var95, "VaR 95%", ui.NEG),
                        (V0, "Start", ui.INK)), key=lambda m: m[0])
        for i, (v, lab, colr) in enumerate(marks):
            fig.add_vline(x=v, line_dash="dash" if lab != "Start" else "solid", line_color=colr, line_width=1.3)
            fig.add_annotation(x=v, y=1.0 - 0.075 * i, yref="paper", xanchor="right" if lab != "Start" else "left",
                               xshift=-4 if lab != "Start" else 4, showarrow=False, text=f"<b>{lab}</b> {money(v)}",
                               font=dict(size=11, color=colr), bgcolor="rgba(255,255,255,0.85)")
        ui.style_fig(fig, f"Portfolio value after {H} trading days",
                     "Red tail = outcomes beyond VaR; blue = losses inside VaR; teal = gains", height=460,
                     legend=False, xtitle="Value ($)", ytitle="Number of simulations", hovermode="closest")
        fig.update_xaxes(tickprefix="$", tickformat=",.0f", showspikes=False)
        fig.update_layout(bargap=0)
        ui.chart(fig, container=a)
        with b:
            ui.subhead("Percentiles of the final value", f"After {H} trading days")
            str_table(pd.DataFrame({
                "Percentile": ["5th", "25th", "50th (median)", "75th", "95th", "Mean", "Std. deviation"],
                "Value": [money(x) for x in (met.p5_value, met.p25_value, met.p50_value, met.p75_value, met.p95_value,
                                             met.mean_final_value, met.std_final_value)],
                "Return": [pct(x / V0 - 1, 2) for x in (met.p5_value, met.p25_value, met.p50_value, met.p75_value,
                                                        met.p95_value, met.mean_final_value)]
                + [pct(met.std_final_value / V0, 2)],
            }), "Percentile", row_styles={"50th (median)": "total"})
            st.caption("VaR 95% = start value − 5th percentile. CVaR 95% = start value − average of the values at or "
                       "below that percentile.")
    with tab_var:
        def both(x):
            return "n/a" if not np.isfinite(x) else f"{money(x * V0)} ({pct(x, 2)})"

        def row(name, v95, c95, v99, c99):
            return [name, both(v95), both(c95), both(v99), both(c99)]
        nan = float("nan")
        methods = [(f"Monte Carlo ({method_label})", met.var_95_pct, met.cvar_95_pct, met.var_99_pct, met.cvar_99_pct),
                   ("Parametric (lognormal; μ·H and σ·√H)", met.parametric_var_95_pct, met.parametric_cvar_95_pct,
                    met.parametric_var_99_pct, met.parametric_cvar_99_pct),
                   (f"Historical ({met.hist_windows:,} overlapping {H}-day windows)", met.historical_var_95_pct,
                    met.historical_cvar_95_pct, met.historical_var_99_pct, met.historical_cvar_99_pct),
                   ("Historical 1-day × √H (ignores drift)", met.hist_sqrt_t_var_95_pct, nan,
                    met.hist_sqrt_t_var_99_pct, nan)]
        short = ["Monte Carlo", "Parametric", "Historical windows", "1-day × √H"]
        fig = go.Figure()
        for j, (lab, colr) in enumerate((("VaR 95%", ui.rgba(ui.NEG, 0.55)), ("CVaR 95%", ui.NEG),
                                         ("VaR 99%", ui.rgba(ui.ACCENT_2, 0.6)), ("CVaR 99%", ui.ACCENT_2))):
            ys = [m[j + 1] * V0 if np.isfinite(m[j + 1]) else None for m in methods]
            fig.add_bar(x=short, y=ys, name=lab, marker_color=colr,
                        text=[money(v) if v is not None else "" for v in ys], textposition="outside",
                        textfont=dict(size=11), hovertemplate=lab + ": %{y:$,.0f}<extra></extra>")
        ui.style_fig(fig, f"Loss estimates by method over {H} trading days",
                     f"Dollar loss on {money(V0)}; click legend items to compare", height=440, hovermode="closest")
        fig.update_layout(barmode="group")
        fig.update_yaxes(tickprefix="$", tickformat=",.0f", rangemode="tozero")
        fig.update_xaxes(showspikes=False)
        ui.chart(fig)
        str_table(pd.DataFrame([row(*m) for m in methods], columns=["Method", "VaR 95%", "CVaR 95%", "VaR 99%",
                                                                    "CVaR 99%"]), "Method")
        st.markdown(esc(f"""
* All figures are **losses over {H} trading days**, as dollars and % of the {money(V0)} start. A negative number means
  even the bad-case scenario is a gain.
* **Parametric** assumes the portfolio's {H}-day log return is normal with mean {H}·μ and volatility √{H}·σ, using the
  daily μ = {met.param_mu_daily:.5f} and σ = {met.param_sigma_daily:.5f} of the historical portfolio.
* **Historical windows** use every run of {H} consecutive past days. Neighbouring windows overlap almost completely, so
  there are far fewer independent observations than windows{' (shown as n/a when there are fewer than 100)' if met.hist_windows < 100 else ''}.
* The **√H rule** scales a 1-day loss by √{H}. Regulators use it for short horizons; over a year it ignores the drift."""))
    with tab_dd:
        a, b = st.columns(2, gap="medium")
        fig = go.Figure(go.Histogram(x=met.max_drawdowns * 100, nbinsx=60, marker_color=ui.rgba(ui.NEG, 0.8),
                                     hovertemplate="Drawdown %{x:.1f}%<br>%{y:,} paths<extra></extra>"))
        fig.add_vline(x=met.median_max_drawdown * 100, line_dash="dash", line_color=ui.ACCENT_2,
                      annotation_text=f"Median {pct(met.median_max_drawdown)}",
                      annotation_font=dict(color=ui.ACCENT_2, size=11.5))
        fig.add_vline(x=met.worst_drawdown_p95 * 100, line_dash="dash", line_color=ui.WARN,
                      annotation_text=f"95th pct {pct(met.worst_drawdown_p95)}", annotation_position="top left",
                      annotation_font=dict(color=ui.WARN, size=11.5))
        ui.style_fig(fig, "Largest peak-to-trough fall in each path", "Computed per path, then summarised",
                     height=440, legend=False, xtitle="Max drawdown (%)", ytitle="Number of simulations",
                     hovermode="closest")
        fig.update_xaxes(ticksuffix="%", showspikes=False)
        ui.chart(fig, container=a)
        with b:
            ui.kpis([dict(label="Median max drawdown", value=pct(met.median_max_drawdown, 2), tone="neg",
                          accent=ui.ACCENT_2),
                     dict(label="1 path in 20 falls more than", value=pct(met.worst_drawdown_p95, 2), accent=ui.WARN)],
                    cols=2)
            ui.kpis([dict(label="Worst simulated", value=pct(met.worst_drawdown_max, 2), accent=ui.NEG),
                     dict(label="Paths ending with a loss", value=pct(met.prob_of_loss), accent=ui.INK)], cols=2)
            st.caption("Max drawdown is computed on each path separately (running peak to later low), then summarised. "
                       "It can be large even when the final value is a gain.")
    with tab_par:
        a, b = st.columns(2, gap="medium")
        with a:
            ui.subhead("Estimated from history", "Annualised, 252 trading days per year")
            str_table(pd.DataFrame({"Ticker": par.tickers, "Weight": [pct(w, 0) for w in weights],
                                    "Mean log return / yr": [pct(x) for x in par.mean_log_annual],
                                    "Volatility / yr": [pct(x) for x in par.vol_annual],
                                    "GBM drift μ / yr": [pct(x) for x in par.mean_arith_annual]}), "Ticker")
            st.caption("GBM drift μ = mean log return + σ²/2. The simulation uses the mean log return per day directly, "
                       "which already includes the −σ²/2 correction.")
        if len(keep) > 1:
            sim_r = mc.simulate_asset_log_returns(par.mean_log_daily, par.cov_daily, 200_000, seed=0)
            sim_corr = np.corrcoef(sim_r, rowvar=False)
            corr_scale = [[0.0, ui.NEG], [0.5, "#F6F3EC"], [1.0, ui.ACCENT_2]]
            fig = go.Figure(go.Heatmap(z=par.corr, x=keep, y=keep, zmin=-1, zmax=1, colorscale=corr_scale,
                                       text=[[f"{v:.2f}" for v in r] for r in par.corr], texttemplate="%{text}",
                                       textfont=dict(size=13),
                                       hovertemplate="%{y} vs %{x}: %{z:.3f}<extra></extra>"))
            ui.style_fig(fig, "Historical correlation", "Input to the Cholesky factorisation", height=400,
                         legend=False, hovermode="closest")
            fig.update_yaxes(autorange="reversed", showspikes=False, showgrid=False, ticks="")
            fig.update_xaxes(showspikes=False, ticks="")
            ui.chart(fig, container=b)
            b.caption(f"Check: correlations of 200,000 simulated days differ from the input by at most "
                      f"{np.abs(sim_corr - par.corr).max():.3f}.")
        norm_p = pdata.prices / pdata.prices.iloc[0] * 100
        fig = go.Figure([go.Scatter(x=norm_p.index, y=norm_p[c], name=c, mode="lines", line=dict(width=2),
                                    hovertemplate="%{y:.1f}") for c in norm_p.columns])
        fig.add_hline(y=100, line_color=ui.MUTED, line_width=1, line_dash="dot")
        ui.style_fig(fig, "Price history used", "Rebased to 100 at the start; drag the slider to zoom", height=440)
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.06, bgcolor=ui.SURFACE_2),
                         rangeselector=dict(buttons=[dict(count=1, label="1Y", step="year", stepmode="backward"),
                                                     dict(count=3, label="3Y", step="year", stepmode="backward"),
                                                     dict(step="all", label="All")],
                                            bgcolor=ui.SURFACE_2, activecolor=ui.ACCENT_BG, x=1, xanchor="right", y=1.08))
        ui.chart(fig)

    xbytes = excel_bytes("portfolio", (key, tuple(weights), method, block, drift, rebalance, V0, H, n_eff, seed),
                         (pdata, weights, paths, met, method_label, rebalance, seed))
    export("Every simulated final value and drawdown, with the statistics as live Excel formulas.", xbytes,
           f"MonteCarlo_Portfolio_{'_'.join(keep)}_{H}d.xlsx",
           "The percentiles, VaR, CVaR, probability of loss, parametric and historical VaR are Excel formulas "
           "(PERCENTILE.INC, AVERAGEIF, STDEV.S, NORM.S.INV ...).")

# =================================================================== RETIREMENT
elif module == MODULES[1]:
    ui.section("Retirement plan: probability of success",
               "Monthly Monte Carlo of saving then spending, with inflation-adjusted withdrawals and a "
               "safe-withdrawal-rate sweep.", kicker="Inputs")
    with st.container(border=True):
        c = st.columns(4, gap="medium")
        P = c[0].number_input("Savings today ($)", 0.0, 1e9, 50_000.0, 5_000.0, format="%.0f")
        C = c[0].number_input("Monthly contribution ($)", 0.0, 1e7, 1_000.0, 100.0, format="%.0f")
        yt = c[1].slider("Years until retirement", 0, 50, 25)
        yr = c[1].slider("Years in retirement", 1, 50, 30)
        W = c[2].number_input("Annual withdrawal ($)", 0.0, 1e8, 60_000.0, 5_000.0, format="%.0f")
        inf = c[2].slider("Inflation (%/yr)", 0.0, 10.0, 2.5, 0.1) / 100
        r = c[3].slider("Expected return (%/yr)", -5.0, 15.0, 7.0, 0.25) / 100
        s = c[3].slider("Volatility (%/yr)", 0.0, 40.0, 15.0, 0.5) / 100
        today = st.checkbox("Withdrawal is in today's money", value=False,
                            help="Off: the first retirement year withdraws exactly this amount. On: the amount is grown "
                                 "by inflation until retirement first, so it keeps today's purchasing power.")
    with st.spinner("Simulating..."):
        res, swr = run_retirement(P, C, yt, yr, W, inf, r, s, n_sims, seed, today)
    sp = res.success_probability
    wr = res.first_withdrawal / res.median_retirement_nest_egg if res.median_retirement_nest_egg > 0 else float("nan")
    sp_tone = "pos" if sp >= 0.9 else ("warn" if sp >= 0.75 else "neg")
    ui.section("Key results", f"{n_sims:,} simulated lifetimes, monthly steps.")
    ui.kpis([
        dict(label="Probability of success", value=pct(sp), tone=sp_tone,
             delta={"pos": "On track", "warn": "Marginal", "neg": "At risk"}[sp_tone],
             note=f"{res.failed_sim_count:,} of {res.total_sim_count:,} ran out"),
        dict(label="Median nest egg at retirement", value=money(res.median_retirement_nest_egg),
             note=f"after {yt} yrs · no-volatility plan {money(mc.deterministic_nest_egg(P, C, yt, r))}"),
        dict(label="First-year withdrawal", value=money(res.first_withdrawal),
             note=f"{pct(wr, 2)} of the median nest egg, then +{inf:.1%}/yr"),
        dict(label="Median wealth at the end", value=money(res.median_terminal_wealth),
             tone=ui.tone(res.median_terminal_wealth), note=f"after {yt + yr} years (nominal)"),
        dict(label="Safe withdrawal rate", value=pct(swr.rate_at_90pct_success, 1) if swr.rate_at_90pct_success else "< 2%",
             note=f"≥ 90% success over {yr} yrs (95%: "
                  f"{pct(swr.rate_at_95pct_success, 1) if swr.rate_at_95pct_success else '< 2%'})"),
    ])
    st.caption(f"Return model: monthly lognormal returns with expected annual return {r:.2%} and volatility {s:.1%}; the typical "
               f"(median) year returns {res.median_annual_return:.2%} because of volatility drag. Contributions at the end of each month; "
               "withdrawals at the start of each month, raised by inflation once a year. Success = every withdrawal paid in full.")
    t1, t2, t3 = st.tabs(["Wealth fan chart", "Safe withdrawal rate", "When money runs out"])
    with t1:
        real = st.toggle("Show in today's money (inflation-adjusted)", value=False)
        pq = res.real_percentile_paths if real else res.percentile_paths
        cap = float(np.max(pq["p75"])) * 1.35
        ui.chart(fan(res.timeline_years, pq, "Wealth over time" + (" (today's money)" if real else " (nominal)"),
                     "Saving until the dashed line, spending after it; bands are percentiles in each month",
                     "Years from today", "Wealth", vline=(yt, "Retirement"), cap=cap, color=ui.ACCENT))
        st.caption(esc(f"The axis stops at {money(cap)}; the luckiest "
                       f"5% of paths go higher (95th percentile peak {money(float(np.max(pq['p95'])))})."))
    with t2:
        a, b = st.columns(2, gap="medium")
        rates, succ = swr.withdrawal_rates * 100, swr.success_probabilities * 100
        mcol = [ui.POS if v >= 95 else (ui.WARN if v >= 90 else ui.NEG) for v in succ]
        fig = go.Figure()
        fig.add_hrect(y0=95, y1=100, fillcolor=ui.rgba(ui.POS, 0.07), line_width=0)
        fig.add_hrect(y0=90, y1=95, fillcolor=ui.rgba(ui.WARN, 0.08), line_width=0)
        fig.add_trace(go.Scatter(x=rates, y=succ, mode="lines+markers", name="Success probability",
                                 line=dict(color=ui.INK_2, width=2), marker=dict(size=11, color=mcol),
                                 hovertemplate="Withdraw %{x:.1f}% → %{y:.1f}% success<extra></extra>"))
        for y, colr in ((95, ui.POS), (90, ui.WARN)):
            fig.add_hline(y=y, line_dash="dash", line_color=colr, line_width=1, annotation_text=f"{y}%",
                          annotation_font=dict(color=colr, size=11))
        fig.add_vline(x=4, line_dash="dot", line_color=ui.PALETTE[4], annotation_text="4% rule",
                      annotation_font=dict(color=ui.PALETTE[4], size=11))
        ui.style_fig(fig, "Success vs initial withdrawal rate",
                     f"{yr} years, nest egg {money(swr.nest_egg_base)}; first-year % then raised with inflation",
                     height=460, legend=False, xtitle="First-year withdrawal (% of nest egg)",
                     ytitle="Probability of success (%)", hovermode="closest")
        fig.update_xaxes(ticksuffix="%", showspikes=False)
        fig.update_yaxes(ticksuffix="%", range=[max(0, float(np.min(succ)) - 5), 101], showspikes=False)
        ui.chart(fig, container=a)
        succ_tbl = pd.DataFrame({"Rate": [f"{x:.1%}" for x in swr.withdrawal_rates],
                                 "First-year withdrawal": [money(x) for x in swr.annual_withdrawal_amounts],
                                 "Success": [pct(p) for p in swr.success_probabilities]}).set_index("Rate")
        ui.html_table(succ_tbl, fmt="plain", max_height=470, container=b)
    with t3:
        if res.failed_sim_count:
            fig = go.Figure(go.Histogram(x=res.depletion_years, nbinsx=30, marker_color=ui.rgba(ui.NEG, 0.82),
                                         hovertemplate="Year %{x}<br>%{y:,} simulations<extra></extra>"))
            fig.add_vline(x=yt, line_dash="dash", line_color=ui.WARN, annotation_text="Retirement",
                          annotation_font=dict(color=ui.WARN, size=11.5))
            ui.style_fig(fig, "Year the money runs out", "Failed simulations only", height=440, legend=False,
                         xtitle="Years from today", ytitle="Simulations", hovermode="closest")
            fig.update_xaxes(showspikes=False)
            ui.chart(fig)
            st.caption(f"Median: {np.median(res.depletion_years):.1f} years from today. Bad returns early in retirement "
                       "(sequence-of-returns risk) do the most damage, because withdrawals lock in the losses.")
        else:
            st.success("No simulation ran out of money.")
    xbytes = excel_bytes("retirement", (P, C, yt, yr, W, inf, r, s, n_sims, seed, today),
                         (res, swr, P, C, yt, yr, W, inf, r, s, today, seed))
    export("The plan, every simulated path summary and the withdrawal-rate sweep, with live formulas.", xbytes,
           f"MonteCarlo_Retirement_{yt}y_{yr}y.xlsx")

# =================================================================== OPTIONS
else:
    ui.section("European option pricing: Monte Carlo vs Black-Scholes",
               "Risk-neutral GBM with antithetic variates, a 95% confidence interval, and analytical and pathwise Greeks.",
               kicker="Inputs")
    with st.container(border=True):
        c = st.columns(4, gap="medium")
        S = c[0].number_input("Spot price S", 0.01, 1e6, 100.0, 1.0)
        K = c[0].number_input("Strike K", 0.01, 1e6, 100.0, 1.0)
        T = c[1].number_input("Years to expiry T", 0.01, 30.0, 1.0, 0.25)
        typ = c[1].selectbox("Type", ["call", "put"], format_func=str.title)
        r = c[2].number_input("Risk-free rate r (%, continuous)", -5.0, 25.0, 5.0, 0.25) / 100
        q = c[2].number_input("Dividend yield q (%, continuous)", 0.0, 20.0, 0.0, 0.25) / 100
        sig = c[3].number_input("Volatility σ (%)", 0.1, 300.0, 20.0, 1.0) / 100
        pts = c[3].slider("Convergence points", 20, 200, 100, 10, help="Points on the convergence chart.")
    opt = mc.monte_carlo_option_pricing(S, K, T, r, sig, q, typ, n_sims=n_sims, seed=seed, n_convergence_points=pts)
    inside = opt.ci_lower <= opt.bs_price <= opt.ci_upper
    g = opt.greeks
    ui.section("Key results", f"{opt.n_pairs:,} antithetic pairs.")
    ui.kpis([
        dict(label="Black-Scholes price", value=f"${opt.bs_price:.4f}", note="closed-form benchmark", accent=ui.ACCENT),
        dict(label="Monte Carlo (antithetic)", value=f"${opt.mc_price_antithetic:.4f}",
             delta=f"± {opt.mc_se_antithetic:.4f} s.e.", tone="pos" if inside else "warn"),
        dict(label="95% confidence interval", value=f"{opt.ci_lower:.3f} – {opt.ci_upper:.3f}",
             delta="BS inside" if inside else "BS outside", tone="pos" if inside else "warn",
             note="" if inside else "happens 5% of the time"),
        dict(label="Plain Monte Carlo", value=f"${opt.mc_price_standard:.4f}",
             note=f"± {opt.mc_se_standard:.4f} with the same payoffs"),
        dict(label="Variance reduction", value=f"{opt.variance_reduction_ratio:.2f}×",
             note="fewer payoffs for the same precision"),
    ])
    t1, t2, t3 = st.tabs(["Convergence", "Greeks", "Payoff distribution"])
    with t1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=opt.convergence_steps, y=opt.convergence_ci_upper, mode="lines",
                                 line=dict(width=0.6, color=ui.rgba(ui.ACCENT_2, 0.5)), showlegend=False,
                                 hovertemplate="Upper %{y:.4f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=opt.convergence_steps, y=opt.convergence_ci_lower, mode="lines",
                                 line=dict(width=0.6, color=ui.rgba(ui.ACCENT_2, 0.5)), fill="tonexty",
                                 fillcolor=ui.rgba(ui.ACCENT_2, 0.16), name="95% confidence interval",
                                 hovertemplate="Lower %{y:.4f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=opt.convergence_steps, y=opt.convergence_prices, mode="lines",
                                 line=dict(color=ui.ACCENT_2, width=2.5), name="Monte Carlo estimate",
                                 hovertemplate="MC %{y:.4f}<extra></extra>"))
        fig.add_hline(y=opt.bs_price, line_dash="dash", line_color=ui.POS, line_width=1.5,
                      annotation_text=f"Black-Scholes {opt.bs_price:.4f}", annotation_position="bottom right",
                      annotation_font=dict(color=ui.POS, size=11.5))
        ui.style_fig(fig, "Monte Carlo estimate as simulations are added",
                     "The interval shrinks like 1/√N: four times as many simulations halve its width", height=480,
                     xtitle="Payoffs simulated (2 per antithetic pair)", ytitle="Option price ($)")
        fig.update_xaxes(tickformat=",.0f", rangeslider=dict(visible=True, thickness=0.06, bgcolor=ui.SURFACE_2))
        ui.chart(fig)
        st.caption("The CI uses the standard deviation of the pair averages, because the two payoffs in a pair are "
                   "not independent.")
    with t2:
        grid = np.linspace(S * 0.5, S * 1.5, 81)
        vals = [mc.black_scholes_price(x, K, T, r, sig, q, typ) for x in grid]
        dels = [mc.black_scholes_greeks(x, K, T, r, sig, q, typ).delta for x in grid]
        a, b = st.columns(2, gap="medium")
        fig = go.Figure([go.Scatter(x=grid, y=vals, name="Option value today", line=dict(color=ui.ACCENT_2, width=3),
                                    hovertemplate="%{y:$.2f}"),
                         go.Scatter(x=grid, y=np.maximum(grid - K, 0) if typ == "call" else np.maximum(K - grid, 0),
                                    name="Payoff at expiry", line=dict(color=ui.PALETTE[2], dash="dot", width=2),
                                    hovertemplate="%{y:$.2f}")])
        fig.add_vline(x=S, line_color=ui.MUTED, line_dash="dot", annotation_text=f"Spot {S:g}",
                      annotation_font=dict(color=ui.MUTED, size=11))
        ui.style_fig(fig, "Value today vs value at expiry", f"{typ.title()}, strike {K:g}", height=420,
                     xtitle="Spot price", ytitle="Value ($)")
        ui.chart(fig, container=a)
        fig = go.Figure(go.Scatter(x=grid, y=dels, name="Delta", line=dict(color=ui.PALETTE[1], width=3),
                                   fill="tozeroy", fillcolor=ui.rgba(ui.PALETTE[1], 0.10), hovertemplate="%{y:+.3f}"))
        fig.add_vline(x=S, line_color=ui.MUTED, line_dash="dot")
        ui.style_fig(fig, "Delta across spot prices", "Sensitivity of the option value to a $1 move in S",
                     height=420, legend=False, xtitle="Spot price", ytitle="Delta")
        ui.chart(fig, container=b)
        ui.section("Greeks", "Black-Scholes closed form vs Monte Carlo pathwise estimates.")
        str_table(pd.DataFrame({
            "Greek": ["Delta", "Gamma", "Vega", "Theta", "Rho"],
            "Black-Scholes": [f"{g.delta:+.4f}", f"{g.gamma:.4f}", f"{g.vega / 100:.4f}", f"{g.theta / 365:+.4f}", f"{g.rho / 100:+.4f}"],
            "Monte Carlo (pathwise)": [f"{opt.mc_delta:+.4f}", "–", f"{opt.mc_vega / 100:.4f}", "–", "–"],
            "Unit": ["per $1 of S", "per $1 of S, change in delta", "per 1 vol point", "per calendar day", "per 1% rate"],
            "Annual / raw": [f"{g.delta:+.4f}", f"{g.gamma:.6f}", f"{g.vega:.4f} per 1.00 σ", f"{g.theta:+.4f} per year", f"{g.rho:+.4f} per 1.00 r"],
        }), "Greek")
    with t3:
        zero_share = float(np.mean(opt.payoffs == 0))
        pos_pay = opt.payoffs[opt.payoffs > 0]
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=pos_pay, nbinsx=60, marker_color=ui.rgba(ui.PALETTE[4], 0.85),
                                   name="Paths that pay out", hovertemplate="%{x}<br>%{y:,} paths<extra></extra>"))
        fig.add_vline(x=opt.mc_price_antithetic, line_dash="dash", line_color=ui.POS, line_width=1.5,
                      annotation_text=f"Mean discounted payoff = MC price {opt.mc_price_antithetic:.2f}",
                      annotation_font=dict(color=ui.POS, size=11.5))
        ui.style_fig(fig, "Discounted payoffs of all simulated paths",
                     f"{zero_share:.1%} of paths expire worthless (not shown); the price averages all of them",
                     height=460, legend=False, xtitle="Discounted payoff ($)", ytitle="Paths", hovermode="closest")
        fig.update_xaxes(tickprefix="$", showspikes=False)
        ui.chart(fig)
        st.caption(f"{zero_share:.1%} of paths expire worthless. The price is the average of all discounted payoffs.")
    xbytes = excel_bytes("options", (S, K, T, r, sig, q, typ, n_sims, seed, pts), (opt, S, K, T, r, sig, q, typ, seed))
    export("Black-Scholes and the Monte Carlo re-run as live formulas on the exported random draws.", xbytes,
           f"MonteCarlo_Option_{typ}_S{S:g}_K{K:g}.xlsx")

ui.footer("Educational tool, not investment advice.")
