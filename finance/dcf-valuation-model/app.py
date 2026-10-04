"""
app.py - Interactive DCF valuation dashboard (Streamlit).

Run:  streamlit run app.py

Layout (page flow: inputs -> key results -> charts -> details -> export)
  Sidebar : company & data source, cost of capital, forecast drivers, terminal value
  Tabs    : Valuation | Forecast | Cost of capital | Sensitivity | Historicals | Methodology
All calculations live in dcf.py; the Excel export lives in excel_export.py; the look comes from
ui_theme.py (the shared design system of the finance portfolio, vendored into this project).
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import ui_theme as ui
from dcf import (
    DataUnavailableError,
    DCFAssumptions,
    WACCInputs,
    calculate_wacc,  # noqa: F401  (re-exported for notebooks that import from app)
    default_assumptions_from_history,
    fetch_company_data,
    fetch_risk_free_rate,
    get_fallback_company_data,
    load_offline_snapshots,
    run_dcf,
)
from excel_export import export_to_excel

ui.apply("DCF Valuation Model · Yamen Agha", icon=":material/account_balance:")


def fmt_money(x: float, cur: str = "$", unit: str = "") -> str:
    return ui.money(x, cur, 2, unit)


def fmt_pct(x: float, signed: bool = False) -> str:
    """x is already in percent (e.g. 12.5 = 12.5%)."""
    return ui.pct(x, 1, signed=signed, ratio=False)


# ==============================================================================
# Cached data access
# ==============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_company(sym: str, offline: bool):
    if offline:
        c = get_fallback_company_data(sym)
        return c, {"source": "offline_snapshot", "warnings": [f"Offline snapshot data as of {c.as_of}."]}
    return fetch_company_data(sym)


@st.cache_data(ttl=3600, show_spinner=False)
def live_risk_free() -> float:
    return fetch_risk_free_rate()


# ==============================================================================
# Sidebar: company & data source
# ==============================================================================

if "ticker" not in st.session_state:
    st.session_state["ticker"] = "AAPL"


def _set_ticker(sym: str) -> None:
    st.session_state["ticker"] = sym


with st.sidebar:
    ui.sidebar_brand("DCF Valuation Model")
    ui.sidebar_section("Company")
    st.text_input("Stock ticker (Yahoo Finance symbol)", key="ticker",
                  help="Any Yahoo Finance equity symbol, e.g. AAPL, MSFT, KO.")
    for row in (["AAPL", "MSFT", "KO"], ["NVDA", "GOOGL", "AMZN"]):
        qc = st.columns(3)
        for col, sym in zip(qc, row):
            col.button(sym, on_click=_set_ticker, args=(sym,), width="stretch", key=f"btn_{sym}")
    data_mode = st.radio("Data source", ["Live (Yahoo Finance)", "Offline snapshot"], horizontal=True,
                         help="Live data falls back to the bundled snapshot if Yahoo Finance is unreachable. "
                              "Offline snapshot tickers: " + ", ".join(sorted(load_offline_snapshots())))

ticker = st.session_state["ticker"].upper().strip()
try:
    with st.spinner(f"Loading financial statements for {ticker}..."):
        company, meta = load_company(ticker, data_mode == "Offline snapshot")
except DataUnavailableError as exc:
    ui.masthead("DCF Valuation Model", "Five-year discounted cash flow valuation of a listed company, "
                "with live market data, sensitivity analysis and an Excel model with live formulas.")
    st.error(str(exc))
    ui.footer()
    st.stop()

defaults = default_assumptions_from_history(company)
rf_default = live_risk_free()

# ==============================================================================
# Sidebar: assumptions (widget keys include the ticker so defaults reset on change)
# ==============================================================================

def pct_slider(label: str, lo: float, hi: float, value: float, step: float, key: str, help: str = None) -> float:
    """Slider shown in percent (e.g. 4.25) that returns a decimal (0.0425)."""
    v = min(hi, max(lo, round(value * 100, 2)))
    return st.slider(label, lo, hi, v, step, format="%.2f%%", key=f"{key}_{ticker}", help=help) / 100.0


with st.sidebar:
    ui.sidebar_section("Assumptions")
    with st.expander("Cost of capital (WACC)", expanded=True):
        rf = pct_slider("Risk-free rate (10Y Treasury)", 0.5, 8.0, rf_default, 0.05, "rf",
                        "Defaults to the latest US 10-year Treasury yield (^TNX).")
        beta = st.slider("Equity beta", 0.2, 3.0, float(min(3.0, max(0.2, round(company.beta, 2)))), 0.01,
                         key=f"beta_{ticker}", help="From Yahoo Finance (5-year monthly vs S&P 500).")
        erp = pct_slider("Equity risk premium", 3.0, 8.0, 0.05, 0.25, "erp",
                         "Extra return investors demand for holding stocks vs government bonds (typically 4-6%).")
        kd = pct_slider("Pre-tax cost of debt", 1.0, 12.0, rf_default + 0.01, 0.05, "kd",
                        "Rough estimate: risk-free rate + a credit spread.")
        tax_w = pct_slider("Tax rate (debt tax shield)", 0.0, 40.0, defaults.tax_rates[0], 0.5, "taxw",
                           "Interest is tax-deductible, so debt costs Kd x (1 - t).")
        weight_mode = st.radio("Capital structure weights", ["Market values", "Target weights"], horizontal=True,
                               key=f"wm_{ticker}", help="Market values use market cap and total debt.")
        we_override = None
        if weight_mode == "Target weights":
            we_override = pct_slider("Target equity weight", 0.0, 100.0, 0.85, 1.0, "we")

    with st.expander("Forecast drivers (Years 1-5)", expanded=True):
        g1 = pct_slider("Year-1 revenue growth", -20.0, 50.0, defaults.revenue_growth_rates[0], 0.25, "g1",
                        "Default = historical revenue CAGR.")
        fade = pct_slider("Growth fade per year", 0.0, 50.0, 0.10, 5.0, "fade",
                          "Each year growth = previous year's growth x (1 - fade).")
        margin = pct_slider("EBIT margin", -10.0, 70.0, defaults.ebit_margins[0], 0.25, "margin",
                            "Default = latest reported operating margin.")
        tax_p = pct_slider("Tax rate on EBIT", 0.0, 40.0, defaults.tax_rates[0], 0.5, "taxp",
                           "Default = latest effective tax rate.")
        da_pct = pct_slider("D&A (% of revenue)", 0.0, 30.0, defaults.da_pcts[0], 0.1, "da",
                            "Depreciation & amortisation, a non-cash charge added back.")
        capex_pct = pct_slider("Capex (% of revenue)", 0.0, 45.0, defaults.capex_pcts[0], 0.1, "capex",
                               "Capital expenditure as a share of revenue.")
        nwc_pct = pct_slider("Net working capital (% of revenue)", -20.0, 40.0, defaults.nwc_pcts[0], 0.5, "nwc",
                             "Only the CHANGE in NWC affects cash flow: growth x NWC% is reinvested each year.")

    with st.expander("Terminal value & conventions", expanded=True):
        g_term = pct_slider("Perpetual growth rate (g)", 0.0, 5.0, 0.025, 0.25, "gterm",
                            "Long-run growth after Year 5. Should not exceed long-run nominal GDP growth.")
        exit_mult = st.slider("Exit EV/EBITDA multiple", 3.0, 35.0, 12.0, 0.5, format="%.1fx", key=f"mult_{ticker}",
                              help="Multiple applied to Year-5 EBITDA for the exit-multiple terminal value.")
        mid_year = st.checkbox("Mid-year discounting convention", value=True, key=f"mid_{ticker}",
                               help="Cash flows arrive on average mid-year: Year t is discounted t - 0.5 years.")

growths = [g1 * (1 - fade) ** i for i in range(5)]
assumptions = DCFAssumptions(
    revenue_growth_rates=growths, ebit_margins=[margin] * 5, tax_rates=[tax_p] * 5,
    capex_pcts=[capex_pct] * 5, da_pcts=[da_pct] * 5, nwc_pcts=[nwc_pct] * 5,
    perpetual_growth_rate=g_term, exit_multiple=exit_mult, mid_year_convention=mid_year,
)
wacc_inputs = WACCInputs(
    risk_free_rate=rf, beta=beta, equity_risk_premium=erp, cost_of_debt=kd, tax_rate=tax_w,
    market_cap=company.market_cap, total_debt=company.total_debt,
    weight_equity_override=we_override,
)
result = run_dcf(company, assumptions, wacc_inputs)
wacc_res = result.wacc_result
proj = result.projections
ggm, ext = result.ggm_valuation, result.exit_valuation
cur_sym = "$" if company.currency == "USD" else f"{company.currency} "
B, M = 1e9, 1e6

# ==============================================================================
# Header
# ==============================================================================

src_label = "Live Yahoo Finance" if meta["source"] == "yfinance" else f"Offline snapshot ({company.as_of})"
ui.masthead(
    "DCF Valuation Model",
    "Five-year discounted cash flow valuation with live market data, two terminal-value methods, "
    "sensitivity analysis and an Excel model with live formulas.",
    kicker="Equity valuation",
    meta={"Company": f"{company.company_name} ({company.ticker})", "Sector": company.sector,
          "Price": fmt_money(company.current_price, cur_sym),
          "Market cap": fmt_money(company.market_cap / B, cur_sym, "B"),
          "History": f"FY{company.years[0]}-FY{company.years[-1]}", "Data": src_label},
)

for w in meta.get("warnings", []) + result.warnings:
    ui.callout(w, "warn", "Note")

tabs = st.tabs(["Valuation", "Forecast", "Cost of capital", "Sensitivity", "Historicals", "Methodology"])


def _tone_up(up: float) -> str:
    return "neutral" if not math.isfinite(up) else ("pos" if up >= 0 else "neg")


# --------------------------------------------------------------------------- tornado helper
@st.cache_data(show_spinner=False, max_entries=64)
def _tornado(inputs_key: tuple, method: str):
    """Value per share when one input moves at a time (all others at base). Uses run_dcf unchanged."""
    def price(a: DCFAssumptions, w: WACCInputs) -> float:
        r = run_dcf(company, a, w)
        return (r.ggm_valuation if method == "ggm" else r.exit_valuation).implied_share_price

    cases = [
        ("Risk-free rate ±1pp", lambda s: (assumptions, replace(wacc_inputs, risk_free_rate=rf + s * 0.01))),
        ("Equity beta ±0.20", lambda s: (assumptions, replace(wacc_inputs, beta=max(0.0, beta + s * 0.2)))),
        ("Year-1 growth ±5pp", lambda s: (replace(assumptions, revenue_growth_rates=[
            (g1 + s * 0.05) * (1 - fade) ** i for i in range(5)]), wacc_inputs)),
        ("EBIT margin ±2pp", lambda s: (replace(assumptions, ebit_margins=[margin + s * 0.02] * 5), wacc_inputs)),
        ("Capex ±1pp of revenue", lambda s: (replace(assumptions, capex_pcts=[max(0.0, capex_pct + s * 0.01)] * 5),
                                             wacc_inputs)),
    ]
    if method == "ggm":
        cases.append(("Perpetual growth ±0.5pp",
                      lambda s: (replace(assumptions, perpetual_growth_rate=g_term + s * 0.005), wacc_inputs)))
    else:
        cases.append(("Exit multiple ±2.0x",
                      lambda s: (replace(assumptions, exit_multiple=max(1.0, exit_mult + s * 2.0)), wacc_inputs)))
    rows = []
    for name, f in cases:
        lo, hi = price(*f(-1)), price(*f(+1))
        rows.append((name, lo, hi))
    return rows


def _key() -> tuple:
    return (ticker, data_mode, rf, beta, erp, kd, tax_w, we_override, g1, fade, margin, tax_p, da_pct, capex_pct,
            nwc_pct, g_term, exit_mult, mid_year)


# ==============================================================================
# Valuation
# ==============================================================================
with tabs[0]:
    method = st.radio("Terminal value method", ["Gordon Growth (perpetual growth)", "Exit multiple (EV/EBITDA)"],
                      horizontal=True, help="Both methods are always computed; this picks the headline figures.")
    val = ggm if method.startswith("Gordon") else ext
    up = val.upside_downside_pct
    if not math.isfinite(up):
        signal, s_tone = "n/a", "neutral"
    elif up > 15:
        signal, s_tone = "Above market by >15%", "pos"
    elif up < -15:
        signal, s_tone = "Below market by >15%", "neg"
    else:
        signal, s_tone = "Within ±15% of market", "neutral"

    ui.kpis([
        dict(label="Implied value per share", value=fmt_money(val.implied_share_price, cur_sym),
             delta=fmt_pct(up, True) + " vs price", tone=_tone_up(up), accent=ui.ACCENT),
        dict(label="Current share price", value=fmt_money(company.current_price, cur_sym),
             delta=signal, tone=s_tone),
        dict(label="Enterprise value", value=fmt_money(val.enterprise_value / B, cur_sym, "B"),
             note=f"Equity value {fmt_money(val.equity_value / B, cur_sym, 'B')}"),
        dict(label="WACC", value=f"{wacc_res.wacc:.2%}",
             note=f"Terminal value = {fmt_pct(val.terminal_value_pct_of_ev)} of EV"),
    ])

    ui.section("Two terminal-value methods", "Same five-year forecast, two ways to value the years after it.",
               kicker=f"{company.currency} billions")

    def method_table(v, title: str, extra: str) -> str:
        rows = [
            ("PV of FCFF, Years 1-5", ui.acct(v.pv_fcf_sum / B, 1), ""),
            ("PV of terminal value", ui.acct(v.pv_terminal_value / B, 1), ""),
            ("Enterprise value", ui.acct(v.enterprise_value / B, 1), "total"),
            ("Less: net debt (debt − cash)", ui.acct(-v.net_debt / B, 1), "neg" if v.net_debt > 0 else "pos"),
            ("Equity value", ui.acct(v.equity_value / B, 1), "total"),
            ("Shares outstanding (billions)", f"{v.shares_outstanding / B:,.3f}", ""),
            ("Implied value per share", fmt_money(v.implied_share_price, cur_sym), "grand"),
        ]
        body = "".join(
            f'<tr class="{c if c in ("total", "grand") else ""}"><td>{ui._e(a)}</td>'
            f'<td class="{c if c in ("pos", "neg") else ""}">{ui._e(b)}</td></tr>' for a, b, c in rows)
        u = v.upside_downside_pct
        chip = ui.chip(fmt_pct(u, True) + " vs market", _tone_up(u))
        return (f'<div class="ya-card"><div style="display:flex;justify-content:space-between;align-items:baseline;'
                f'gap:16px"><h4>{ui._e(title)}</h4>{chip}</div>'
                f'<table class="ya-table" style="margin-top:8px">{body}</table>'
                f'<div style="font-size:12px;color:{ui.MUTED};margin-top:12px">{ui._e(extra)}</div></div>')

    g_extra = (f"Implied EV/EBITDA exit multiple {ggm.implied_exit_multiple:.1f}x"
               if math.isfinite(ggm.implied_exit_multiple) else "")
    e_extra = (f"Implied perpetual growth {ext.implied_perpetual_growth:.2%}"
               if math.isfinite(ext.implied_perpetual_growth) else "")
    st.markdown('<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
                + method_table(ggm, f"Gordon Growth · g = {g_term:.2%}", g_extra)
                + method_table(ext, f"Exit multiple · {exit_mult:.1f}x EBITDA", e_extra) + "</div>",
                unsafe_allow_html=True)

    ui.section("Where the value comes from", "Bridge from discounted cash flows to equity value, and the range "
               "of values across the sensitivity grids.")
    c1, c2 = st.columns(2, gap="medium")
    if math.isfinite(val.enterprise_value):
        steps = [val.pv_fcf_sum / B, val.pv_terminal_value / B, val.enterprise_value / B,
                 -val.total_debt / B, val.total_cash / B, val.equity_value / B]
        fig = go.Figure(go.Waterfall(
            measure=["relative", "relative", "total", "relative", "relative", "total"],
            x=["PV of FCFF<br>Y1-5", "PV of<br>terminal value", "Enterprise<br>value", "Less<br>debt", "Plus<br>cash",
               "Equity<br>value"],
            y=[steps[0], steps[1], 0, steps[3], steps[4], 0],
            text=[ui.acct(s, 0) for s in steps], textposition="outside",
            textfont=dict(size=12, color=ui.INK),
            increasing=dict(marker=dict(color=ui.ACCENT)), decreasing=dict(marker=dict(color=ui.NEG)),
            totals=dict(marker=dict(color=ui.INK)),
            hovertemplate="%{x}<br>%{y:,.1f}B<extra></extra>",
        ))
        ui.style_fig(fig, "Enterprise value to equity value", f"{company.currency} billions, {val.method}",
                     height=420, legend=False, hovermode="closest")
        fig.update_yaxes(tickformat=",.0f", rangemode="tozero")
        fig.update_xaxes(showspikes=False)
        ui.chart(fig, container=c1)

    # football field: min-max of each sensitivity grid plus the tornado range, against the market price
    def _rng(tab):
        arr = np.array(tab, dtype=float)
        arr = arr[np.isfinite(arr)]
        return (float(arr.min()), float(arr.max())) if arr.size else (np.nan, np.nan)

    torn_g = _tornado(_key(), "ggm")
    torn_e = _tornado(_key(), "exit")
    ff = [("Gordon Growth grid<br><span style='font-size:11px'>WACC × g</span>", *_rng(result.ggm_sensitivity.table),
           ggm.implied_share_price, ui.ACCENT_2),
          ("Exit multiple grid<br><span style='font-size:11px'>WACC × multiple</span>",
           *_rng(result.exit_sensitivity.table), ext.implied_share_price, ui.PALETTE[1]),
          ("Gordon, one input<br><span style='font-size:11px'>at a time</span>",
           min(min(a, b) for _, a, b in torn_g), max(max(a, b) for _, a, b in torn_g), ggm.implied_share_price,
           ui.PALETTE[4]),
          ("Exit, one input<br><span style='font-size:11px'>at a time</span>",
           min(min(a, b) for _, a, b in torn_e), max(max(a, b) for _, a, b in torn_e), ext.implied_share_price,
           ui.PALETTE[2])]
    fig = go.Figure()
    for name, lo, hi, base, col in reversed(ff):
        if not (math.isfinite(lo) and math.isfinite(hi)):
            continue
        fig.add_bar(y=[name], x=[hi - lo], base=[lo], orientation="h", marker=dict(color=col, opacity=0.88),
                    width=0.56, showlegend=False,
                    customdata=[[lo, hi, base]],
                    hovertemplate=f"%{{y}}<br>Low {cur_sym}%{{customdata[0]:,.2f}} · High {cur_sym}%{{customdata[1]:,.2f}}"
                                  f"<br>Base {cur_sym}%{{customdata[2]:,.2f}}<extra></extra>")
        fig.add_scatter(y=[name], x=[base], mode="markers", marker=dict(symbol="line-ns", size=26,
                        line=dict(width=2.5, color=ui.SURFACE)), showlegend=False, hoverinfo="skip")
        for xv, anchor in ((lo, "right"), (hi, "left")):
            fig.add_annotation(y=name, x=xv, text=f"{xv:,.0f}", showarrow=False, xanchor=anchor,
                               xshift=-6 if anchor == "right" else 6, font=dict(size=11.5, color=ui.INK_2))
    fig.add_vline(x=company.current_price, line=dict(color=ui.NEG, width=1.5, dash="dash"))
    fig.add_annotation(x=company.current_price, y=1.0, yref="paper", yanchor="bottom", showarrow=False,
                       text=f"Market {fmt_money(company.current_price, cur_sym)}", font=dict(size=11.5, color=ui.NEG))
    ui.style_fig(fig, "Valuation range (football field)", f"Implied value per share, {company.currency}",
                 height=420, legend=False, hovermode="closest")
    fig.update_xaxes(showgrid=True, tickprefix=cur_sym.strip() if cur_sym == "$" else "", showspikes=False)
    fig.update_yaxes(showgrid=False, showspikes=False)
    fig.update_layout(margin=dict(l=8, r=40))
    ui.chart(fig, container=c2)

    ui.section("Export", "A workbook with every assumption as an input cell and every result as a live formula.")
    st.download_button(
        f"Download {company.ticker} Excel model (live formulas)",
        data=export_to_excel(result),
        file_name=f"{company.ticker}_DCF_{datetime.now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch", type="primary", icon=":material/download:",
    )

# ==============================================================================
# Forecast
# ==============================================================================
with tabs[1]:
    years = [f"FY{company.years[-1]}A"] + [f"Year {i}" for i in range(1, 6)]
    nan = float("nan")
    rows = {
        "Revenue": proj.revenue,
        "Revenue growth": [nan] + proj.revenue_growth[1:],
        "EBIT": [company.ebit[-1]] + proj.ebit[1:],
        "EBIT margin": [company.ebit[-1] / company.revenue[-1]] + proj.ebit_margin[1:],
        "NOPAT = EBIT × (1 − tax)": [nan] + proj.nopat[1:],
        "Plus: D&A": [company.da[-1]] + proj.da[1:],
        "Less: capex": [-company.capex[-1]] + [-c for c in proj.capex[1:]],
        "Less: increase in NWC": [nan] + [-c for c in proj.nwc_change[1:]],
        "Free cash flow to firm (FCFF)": [company.historical_fcff[-1]] + proj.fcff[1:],
        "Discount period (years)": [nan] + proj.discount_period[1:],
        "Discount factor": [nan] + proj.discount_factor[1:],
        "PV of FCFF": [nan] + proj.pv_fcff[1:],
    }
    df = pd.DataFrame(rows, index=years).T
    money_rows = [r for r in rows if r not in ("Revenue growth", "EBIT margin", "Discount period (years)",
                                                "Discount factor")]
    disp = df.copy().astype(object)
    for r in money_rows:
        disp.loc[r] = [v / M if math.isfinite(v) else None for v in df.loc[r]]
    for r in ("Revenue growth", "EBIT margin", "Discount period (years)", "Discount factor"):
        disp.loc[r] = [v if math.isfinite(v) else None for v in df.loc[r]]
    ui.kpis([
        dict(label="Year-5 revenue", value=fmt_money(proj.revenue[-1] / B, cur_sym, "B"),
             delta=f"{(proj.revenue[-1] / proj.revenue[0]) ** (1 / 5) - 1:+.1%} CAGR",
             tone=ui.tone(proj.revenue[-1] - proj.revenue[0])),
        dict(label="Year-1 FCFF", value=fmt_money(proj.fcff[1] / B, cur_sym, "B"),
             tone=ui.tone(proj.fcff[1]), value_tone="neg" if proj.fcff[1] < 0 else "",
             note=f"FCFF margin {proj.fcff[1] / proj.revenue[1]:.1%}"),
        dict(label="Year-5 FCFF", value=fmt_money(proj.fcff[-1] / B, cur_sym, "B"),
             value_tone="neg" if proj.fcff[-1] < 0 else "", note=f"FCFF margin {proj.fcff[-1] / proj.revenue[-1]:.1%}"),
        dict(label="Sum of PV of FCFF", value=fmt_money(proj.cumulative_pv_fcff / B, cur_sym, "B"),
             note="Years 1-5, discounted at WACC"),
    ])
    ui.section("Free cash flow forecast", "Year 0 shows reported figures; FCFF = NOPAT + D&A − capex − ΔNWC.",
               kicker=f"{company.currency} millions")
    ui.html_table(disp, fmt="acct0", row_fmt={"Revenue growth": "pct", "EBIT margin": "pct",
                                             "Discount period (years)": "num2", "Discount factor": "num4"},
                  row_styles={"NOPAT = EBIT × (1 − tax)": "total", "Plus: D&A": "sub", "Less: capex": "sub",
                              "Less: increase in NWC": "sub", "Free cash flow to firm (FCFF)": "grand",
                              "Revenue growth": "sub", "EBIT margin": "sub"})

    ui.section("Forecast charts")
    c1, c2 = st.columns(2, gap="medium")
    xs = [f"Year {i}" for i in range(1, 6)]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=xs, y=[v / B for v in proj.revenue[1:]], name="Revenue", marker_color=ui.ACCENT_2,
                hovertemplate="%{y:,.1f}B")
    fig.add_bar(x=xs, y=[v / B for v in proj.ebit[1:]], name="EBIT", marker_color=ui.PALETTE[1],
                hovertemplate="%{y:,.1f}B")
    fig.add_scatter(x=xs, y=[v / B for v in proj.fcff[1:]], name="FCFF", mode="lines+markers",
                    line=dict(color=ui.PALETTE[2], width=3), marker=dict(size=9), hovertemplate="%{y:,.1f}B")
    fig.add_scatter(x=xs, y=proj.ebit_margin[1:], name="EBIT margin (rhs)", mode="lines+markers",
                    line=dict(color=ui.INK_2, width=1.5, dash="dot"), secondary_y=True, hovertemplate="%{y:.1%}")
    ui.style_fig(fig, "Revenue, EBIT and free cash flow", f"{company.currency} billions; margin on the right axis",
                 height=440)
    fig.update_layout(barmode="group")
    fig.update_yaxes(tickformat=",.0f", secondary_y=False)
    fig.update_yaxes(tickformat=".0%", showgrid=False, secondary_y=True, rangemode="tozero")
    ui.chart(fig, container=c1)

    # FCFF build for Year 1 (cash-flow waterfall)
    i = 1
    vals = [proj.nopat[i] / B, proj.da[i] / B, -proj.capex[i] / B, -proj.nwc_change[i] / B]
    fig = go.Figure(go.Waterfall(
        measure=["relative", "relative", "relative", "relative", "total"],
        x=["NOPAT", "Plus D&A", "Less capex", "Less ΔNWC", "FCFF"],
        y=vals + [0], text=[ui.acct(v, 1) for v in vals + [proj.fcff[i] / B]], textposition="outside",
        textfont=dict(size=12, color=ui.INK),
        hovertemplate="%{x}<br>%{y:,.2f}B<extra></extra>",
    ))
    ui.style_fig(fig, "Year-1 free cash flow build", f"From NOPAT to FCFF, {company.currency} billions",
                 height=440, legend=False, hovermode="closest")
    fig.update_xaxes(showspikes=False)
    ui.chart(fig, container=c2)

# ==============================================================================
# WACC
# ==============================================================================
with tabs[2]:
    ui.kpis([
        dict(label="Cost of equity (Ke)", value=f"{wacc_res.cost_of_equity:.2%}", note="Rf + β × ERP"),
        dict(label="After-tax cost of debt", value=f"{wacc_res.after_tax_cost_of_debt:.2%}", note="Kd × (1 − t)"),
        dict(label="Equity weight", value=f"{wacc_res.weight_equity:.1%}", note="E / (E + D)"),
        dict(label="Debt weight", value=f"{wacc_res.weight_debt:.1%}", note="D / (E + D)"),
        dict(label="WACC", value=f"{wacc_res.wacc:.2%}", note="Discount rate", accent=ui.ACCENT),
    ])
    ui.section("How the discount rate is built", "CAPM for the cost of equity, then a market-value weighting.")
    c1, c2 = st.columns(2, gap="medium")
    ke_parts = [rf, beta * erp]
    fig = go.Figure(go.Waterfall(
        measure=["relative", "relative", "total", "relative", "relative", "total"],
        x=["Risk-free<br>rate", "β × ERP", "Cost of<br>equity", "Weighting<br>to WACC", "Debt<br>contribution", "WACC"],
        y=[rf, beta * erp, 0, wacc_res.weight_equity * wacc_res.cost_of_equity - wacc_res.cost_of_equity,
           wacc_res.weight_debt * wacc_res.after_tax_cost_of_debt, 0],
        text=[f"{v:.2%}" for v in (rf, beta * erp, wacc_res.cost_of_equity,
                                   wacc_res.weight_equity * wacc_res.cost_of_equity - wacc_res.cost_of_equity,
                                   wacc_res.weight_debt * wacc_res.after_tax_cost_of_debt, wacc_res.wacc)],
        textposition="outside", textfont=dict(size=12, color=ui.INK),
        increasing=dict(marker=dict(color=ui.ACCENT)), totals=dict(marker=dict(color=ui.INK)),
        hovertemplate="%{x}<br>%{y:.2%}<extra></extra>",
    ))
    ui.style_fig(fig, "From risk-free rate to WACC", "Percentage points", height=420, legend=False,
                 hovermode="closest")
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(showspikes=False)
    ui.chart(fig, container=c1)

    fig = go.Figure(go.Pie(labels=["Equity", "Debt"], values=[wacc_res.weight_equity, wacc_res.weight_debt],
                           hole=0.62, marker=dict(colors=[ui.ACCENT_2, ui.PALETTE[2]]), textinfo="label+percent",
                           textfont=dict(size=13), hovertemplate="%{label}: %{percent}<extra></extra>"))
    fig.add_annotation(text=f"<b>{wacc_res.wacc:.2%}</b><br><span style='font-size:12px;color:{ui.MUTED}'>WACC</span>",
                       showarrow=False, font=dict(size=22, family=ui.SERIF, color=ui.INK))
    ui.style_fig(fig, "Capital structure weights",
                 "Market values" if we_override is None else "Target weights (override)", height=420)
    fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05, yanchor="top"))
    ui.chart(fig, container=c2)

    ui.section("Formulae with your inputs")
    ui.callout(f"Cost of equity = {rf:.2%} + {beta:.2f} × {erp:.2%} = {wacc_res.cost_of_equity:.2%}", "info",
               "CAPM")
    ui.callout(f"After-tax cost of debt = {kd:.2%} × (1 − {tax_w:.1%}) = {wacc_res.after_tax_cost_of_debt:.2%}",
               "info", "Debt")
    ui.callout(f"WACC = {wacc_res.weight_equity:.1%} × {wacc_res.cost_of_equity:.2%} + {wacc_res.weight_debt:.1%} × "
               f"{wacc_res.after_tax_cost_of_debt:.2%} = {wacc_res.wacc:.2%}. Weights use market cap "
               f"({fmt_money(company.market_cap / B, cur_sym, 'B')}) and total debt "
               f"({fmt_money(company.total_debt / B, cur_sym, 'B')})"
               + (", overridden by target weights." if we_override is not None else "."), "info", "WACC")

# ==============================================================================
# Sensitivity
# ==============================================================================
with tabs[3]:
    choice = st.radio("Table", ["WACC vs perpetual growth (Gordon Growth)", "WACC vs exit multiple"], horizontal=True)
    sens = result.ggm_sensitivity if choice.startswith("WACC vs perpetual") else result.exit_sensitivity
    is_g = sens.method == "Gordon Growth"
    col_labels = [f"g {p:.2%}" for p in sens.param_values] if is_g else [f"{p:.1f}x" for p in sens.param_values]
    row_labels = [f"WACC {w:.2%}" for w in sens.wacc_values]
    df = pd.DataFrame(sens.table, index=row_labels, columns=col_labels)
    price = company.current_price
    base_val = ggm if is_g else ext

    arr = df.values.astype(float)
    finite = arr[np.isfinite(arr)]
    ui.kpis([
        dict(label="Base case", value=fmt_money(base_val.implied_share_price, cur_sym),
             delta=fmt_pct(base_val.upside_downside_pct, True), tone=_tone_up(base_val.upside_downside_pct)),
        dict(label="Lowest in grid", value=fmt_money(finite.min() if finite.size else nan, cur_sym),
             tone="neg", delta=fmt_pct((finite.min() / price - 1) * 100 if finite.size else nan, True)),
        dict(label="Highest in grid", value=fmt_money(finite.max() if finite.size else nan, cur_sym),
             tone="pos", delta=fmt_pct((finite.max() / price - 1) * 100 if finite.size else nan, True)),
        dict(label="Cells above market", value=f"{int((finite >= price).sum())} of {arr.size}",
             note=f"Market price {fmt_money(price, cur_sym)}"),
    ])

    ui.section("Sensitivity of value per share", "Colour shows upside (green) or downside (red) against the current "
               "share price; the outlined cell is the base case.")
    c1, c2 = st.columns(2, gap="medium")
    up_arr = (arr / price - 1.0)
    lim = float(np.nanpercentile(np.abs(up_arr), 85)) if np.isfinite(up_arr).any() else 1.0
    lim = min(max(lim, 0.10), 1.0)  # saturate outliers so the reds and greens both read clearly
    text = [[("n/a" if not math.isfinite(v) else f"{v:,.0f}") for v in r] for r in arr]
    fig = go.Figure(go.Heatmap(
        z=up_arr, x=col_labels, y=row_labels, text=text, texttemplate="%{text}", textfont=dict(size=12.5),
        colorscale=ui.DIVERGING, zmid=0, zmin=-lim, zmax=lim,
        customdata=arr, hovertemplate="%{y} · %{x}<br>Value/share " + cur_sym.strip()
                                      + "%{customdata:,.2f}<br>vs market %{z:+.1%}<extra></extra>",
        colorbar=dict(title=dict(text="vs price", font=dict(size=11)), tickformat="+.0%", len=0.85),
    ))
    bi = int(np.argmin(np.abs(np.array(sens.wacc_values) - sens.base_wacc)))
    bj = int(np.argmin(np.abs(np.array(sens.param_values) - sens.base_param)))
    fig.add_shape(type="rect", x0=bj - 0.5, x1=bj + 0.5, y0=bi - 0.5, y1=bi + 0.5,
                  line=dict(color=ui.INK, width=2))
    ui.style_fig(fig, f"WACC × {'perpetual growth' if is_g else 'exit multiple'}",
                 f"Implied value per share, {company.currency}", height=460, legend=False, hovermode="closest")
    fig.update_xaxes(side="bottom", showspikes=False, showgrid=False, ticks="")
    fig.update_yaxes(autorange="reversed", showspikes=False, showgrid=False, ticks="")
    ui.chart(fig, container=c1)

    rows_t = _tornado(_key(), "ggm" if is_g else "exit")
    base_p = base_val.implied_share_price
    rows_t = sorted(rows_t, key=lambda r: abs(r[2] - r[1]) if all(map(math.isfinite, r[1:])) else 0)
    fig = go.Figure()
    for label, sgn, idx, col in (("Input lowered", -1, 1, ui.ACCENT_2), ("Input raised", 1, 2, ui.PALETTE[2])):
        fig.add_bar(y=[r[0] for r in rows_t], x=[r[idx] - base_p for r in rows_t], orientation="h", name=label,
                    marker_color=col, customdata=[r[idx] for r in rows_t],
                    hovertemplate="%{y}<br>" + label + ": " + cur_sym.strip() + "%{customdata:,.2f} (%{x:+,.2f})"
                                  "<extra></extra>")
    fig.add_vline(x=0, line=dict(color=ui.INK, width=1))
    ui.style_fig(fig, "What moves the value most (tornado)",
                 f"Change in value per share vs base {fmt_money(base_p, cur_sym)}, one input at a time",
                 height=460, hovermode="closest")
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_xaxes(showgrid=True, tickformat="+,.0f", zeroline=False, showspikes=False,
                     title=dict(text=f"Change in value per share ({company.currency})", font=dict(size=12)))
    fig.update_yaxes(showgrid=False, showspikes=False)
    ui.chart(fig, container=c2)

    ui.section("Sensitivity table", kicker=f"Value per share, {company.currency}")
    ui.html_table(df, fmt="num2", index_label="", highlight=[(row_labels[bi], col_labels[bj])])
    st.caption("'n/a' = WACC not above g (Gordon formula undefined). Highlighted cell = base case.")

# ==============================================================================
# Historicals
# ==============================================================================
with tabs[4]:
    idx = [f"FY{y}" for y in company.years]
    hist = pd.DataFrame({
        "Revenue": company.revenue, "EBIT (operating income)": company.ebit, "D&A": company.da,
        "Capex": company.capex, "Increase in NWC": company.nwc_change, "FCFF": company.historical_fcff,
    }, index=idx).T / M
    ratios = pd.DataFrame({
        "EBIT margin": [e / r for e, r in zip(company.ebit, company.revenue)],
        "D&A % revenue": [d / r for d, r in zip(company.da, company.revenue)],
        "Capex % revenue": [c / r for c, r in zip(company.capex, company.revenue)],
        "Effective tax rate": company.effective_tax_rate,
    }, index=idx).T

    c1, c2 = st.columns(2, gap="medium")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=idx, y=[v / B for v in company.revenue], name="Revenue", marker_color=ui.ACCENT_2,
                hovertemplate="%{y:,.1f}B")
    fig.add_scatter(x=idx, y=ratios.loc["EBIT margin"], name="EBIT margin (rhs)", mode="lines+markers",
                    line=dict(color=ui.PALETTE[2], width=3), secondary_y=True, hovertemplate="%{y:.1%}")
    ui.style_fig(fig, "Reported revenue and margin", f"{company.currency} billions", height=400)
    fig.update_yaxes(tickformat=",.0f", secondary_y=False)
    fig.update_yaxes(tickformat=".0%", showgrid=False, secondary_y=True, rangemode="tozero")
    ui.chart(fig, container=c1)

    fcff_b = [v / B for v in company.historical_fcff]
    fig = go.Figure(go.Bar(x=idx, y=fcff_b, marker_color=ui.bar_colors(fcff_b), name="FCFF",
                           text=[ui.acct(v, 1) for v in fcff_b], textposition="outside", hovertemplate="%{y:,.2f}B"))
    ui.style_fig(fig, "Historical free cash flow to firm", f"{company.currency} billions; red = cash burn",
                 height=400, legend=False)
    ui.chart(fig, container=c2)

    ui.section("Reported history", kicker=f"{company.currency} millions")
    ui.html_table(hist, fmt="acct0", row_styles={"FCFF": "grand"})
    st.caption("Capex shown as a positive outflow. 'Increase in NWC' = minus Yahoo's 'Change In Working Capital' "
               "cash-flow line (positive = cash tied up). FCFF = EBIT × (1 − effective tax) + D&A − Capex − "
               "Increase in NWC.")
    ui.section("Margins and ratios")
    ui.html_table(ratios, fmt="pct")
    if company.description:
        with st.expander("Business description"):
            st.write(company.description)

# ==============================================================================
# Methodology
# ==============================================================================
with tabs[5]:
    period_txt = "t - 0.5 (mid-year convention)" if mid_year else "t (end-of-year convention)"
    st.markdown(f"""
**1. Free cash flow to firm (FCFF)**: cash the business generates for *all* investors (debt and equity):

$$FCFF_t = EBIT_t (1 - tax_t) + D\\&A_t - Capex_t - \\Delta NWC_t$$

**2. Discount rate (WACC)**, with the cost of equity from CAPM:

$$K_e = R_f + \\beta \\times ERP \\qquad WACC = \\frac{{E}}{{E+D}} K_e + \\frac{{D}}{{E+D}} K_d (1 - t)$$

**3. Present value of forecast cash flows**, currently discounted with period = {period_txt}:

$$PV_t = \\frac{{FCFF_t}}{{(1 + WACC)^{{period_t}}}}$$

**4. Terminal value** at the end of Year 5, discounted 5 full years:

$$TV_{{Gordon}} = \\frac{{FCFF_5 (1+g)}}{{WACC - g}} \\qquad TV_{{Exit}} = EBITDA_5 \\times Multiple \\qquad PV(TV) = \\frac{{TV}}{{(1+WACC)^5}}$$

**5. Bridge to value per share**

$$EV = \\sum PV_t + PV(TV) \\qquad Equity = EV - (Debt - Cash) \\qquad Value/share = \\frac{{Equity}}{{Shares}}$$

Simplifications: basic (not diluted) shares; total debt includes leases as reported by Yahoo Finance;
Year-0 NWC is set to base revenue × NWC %, so only growth drives NWC investment; no minority interests,
pensions or non-operating assets are adjusted for.
""")

ui.footer("Educational project, not investment advice. The output is only as good as the assumptions.")
