"""Three-Statement Financial Model - Streamlit app.

Run:  streamlit run app.py

Layout: sidebar (data, scenario, liquidity) -> header -> tabs: Dashboard | Drivers | Statements | Schedules |
Scenarios | Checks & data | Excel export. All calculations live in model.py; the look comes from ui_theme.py,
the shared design system of the finance portfolio (vendored into this project).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data_loader as dl
import excel_export as xe
import model as M
import ui_theme as ui

ui.apply("Three-Statement Financial Model · Yamen Agha", icon=":material/table_chart:")


def esc(s: str) -> str:
    """Escape $ so Streamlit markdown does not switch to LaTeX."""
    return str(s).replace("$", "\\$")


def f1(v) -> str:
    """One decimal with thousands separators; tiny values (incl. -0.0) shown as 0.0."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{(0.0 if abs(v) < 0.05 else v):,.1f}"


def fmt_m(x: float) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:,.1f}" if x >= 0 else f"({-x:,.1f})"


def acct1(v) -> str:
    """Accounting format used in the statements: 1,234.5 / (1,234.5) / 0.0."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return (f"{v:,.1f}" if v > -0.05 else f"({-v:,.1f})").replace("-0.0", "0.0")


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner=False)
def load_snapshot(t: str):
    return dl.load_snapshot(t)


@st.cache_data(show_spinner="Downloading from Yahoo Finance...", ttl=3600)
def load_live(t: str):
    return dl.fetch_yahoo(t)


@st.cache_data(show_spinner=False)
def load_upload(content: bytes, name: str):
    return dl.load_template(content, name)


ui.sidebar_brand("Three-Statement Model")
ui.sidebar_section("Data")
source = st.sidebar.radio("Data source", ["Offline snapshot", "Live Yahoo Finance", "Upload template", "Sample company"],
                          help="The offline snapshot (downloaded from Yahoo Finance) makes the app work without internet.")
hist = None
try:
    if source == "Offline snapshot":
        tick = st.sidebar.selectbox("Company", dl.snapshot_tickers(), index=0)
        hist = load_snapshot(tick)
    elif source == "Live Yahoo Finance":
        tick = st.sidebar.text_input("Ticker", "AAPL").strip().upper()
        if tick:
            hist = load_live(tick)
    elif source == "Upload template":
        up = st.sidebar.file_uploader("CSV or Excel in the template layout", type=["csv", "xlsx"])
        with open(dl.TEMPLATE_DIR / "three_statement_template.xlsx", "rb") as fh:
            st.sidebar.download_button("Download blank template", fh.read(), "three_statement_template.xlsx")
        if up is not None:
            hist = load_upload(up.getvalue(), up.name)
    else:
        hist = load_upload((dl.TEMPLATE_DIR / "sample_historical.csv").read_bytes(), "sample_company.csv")
except Exception as exc:  # show the reason instead of a traceback
    st.error(f"Could not load the data: {esc(exc)}")
    st.stop()

SUBTITLE = ("Linked income statement, balance sheet and cash-flow statement with a five-year forecast, revolver, "
            "interest circularity, scenarios and an Excel model with live formulas.")
if hist is None:
    ui.masthead("Three-Statement Financial Model", SUBTITLE, kicker="Financial modelling")
    ui.callout("Choose a data source in the sidebar (upload a template, or pick a company).", "info", "Start")
    ui.footer()
    st.stop()

key = f"{source}|{hist.ticker}|{hist.company}|{hist.years[-1].year}"
if st.session_state.get("data_key") != key:
    st.session_state.data_key = key
    notes: list = []
    st.session_state.base_drivers = M.baseline_drivers(hist.years, notes)
    st.session_state.driver_notes = notes
    st.session_state.editor_version = st.session_state.get("editor_version", 0) + 1

base: M.ForecastDrivers = st.session_state.base_drivers

ui.sidebar_section("Model settings")
scenario = st.sidebar.radio("Scenario", ["Base", "Bull", "Bear"], horizontal=True,
                            help="Bull and Bear add the scenario deltas (Scenarios tab) to every forecast year.")
method = st.sidebar.radio("Interest on", ["Average balances (circular)", "Beginning balances"],
                          help="Average balances create a circular reference that the model solves by iteration.")
breaker = st.sidebar.toggle("Circuit breaker", value=False,
                            help="Forces beginning balances (no circularity). Used automatically if iteration does not converge.")
ui.sidebar_section("Liquidity")
min_cash = st.sidebar.number_input("Minimum cash", min_value=0.0, value=float(base.min_cash_balance), step=100.0, format="%.1f",
                                   key=f"mc{st.session_state.editor_version}",
                                   help="The revolver draws whenever cash would fall below this level.")
capacity = st.sidebar.number_input("Revolver capacity", min_value=0.0, value=float(base.revolver_capacity), step=100.0, format="%.1f",
                                   key=f"cap{st.session_state.editor_version}",
                                   help="Maximum the revolving credit facility can lend.")
stress = st.sidebar.toggle("Revolver stress test", value=False,
                           help="Adds a one-off special buyback in year 1 that the company cannot pay from cash.")
special, stress_bb = 0.0, 0.80
if stress:
    special = st.sidebar.number_input("Special buyback in year 1", min_value=0.0,
                                      value=float(round(0.132 * hist.years[-1].revenue, -3)), step=1000.0,
                                      help="Default ≈ 13% of last revenue (55,000 for Apple, as in the example workbook).")
    stress_bb = st.sidebar.slider("Recurring buybacks during the stress (% of NI)", 0, 150, 80, 5) / 100
st.sidebar.caption("Figures in millions (as reported by the source). Educational model, not investment advice.")

# ------------------------------------------------------------------ drivers (editable)
labels_fc = M.ThreeStatementModel.__new__(M.ThreeStatementModel)
labels_fc.historical_years = hist.years
fc_labels = M.ThreeStatementModel.forecast_labels(labels_fc)


def drivers_frame(d: M.ForecastDrivers) -> pd.DataFrame:
    rows = {}
    for label, attr, kind, _ in M.DRIVER_SPECS:
        vals = getattr(d, attr)
        rows[label] = [v * 100 if kind == "pct" else v for v in vals]
    return pd.DataFrame(rows, index=fc_labels).T


def frame_to_drivers(df: pd.DataFrame, d: M.ForecastDrivers) -> M.ForecastDrivers:
    out = d.copy()
    for label, attr, kind, _ in M.DRIVER_SPECS:
        vals = [float(x) if pd.notna(x) else 0.0 for x in df.loc[label].values]
        setattr(out, attr, [v / 100 if kind == "pct" else v for v in vals])
    return out


def apply_edits(df: pd.DataFrame, state) -> pd.DataFrame:
    """Apply st.data_editor's edited_rows deltas so edits take effect in the same rerun."""
    df = df.copy()
    for r, changes in (state or {}).get("edited_rows", {}).items():
        for col, val in changes.items():
            if col in df.columns and val is not None:
                df.iloc[int(r), df.columns.get_loc(col)] = float(val)
    return df


EDITOR_KEY = f"editor{st.session_state.editor_version}"
edited = apply_edits(drivers_frame(base), st.session_state.get(EDITOR_KEY))
user = frame_to_drivers(edited, base)
user.min_cash_balance, user.revolver_capacity = float(min_cash), float(capacity)
user.interest_calc_method = "average" if method.startswith("Average") else "beginning"
user.circuit_breaker = bool(breaker)
if stress:
    user = M.revolver_stress(user, special_buyback=float(special), buyback_pct_ni=float(stress_bb))

try:
    models = M.run_scenarios(hist.years, user, hist.company, hist.ticker)
except ValueError as exc:
    st.error(f"Invalid driver: {esc(exc)}")
    st.stop()
for mm in models.values():
    mm.driver_notes = st.session_state.driver_notes
m = models[scenario]
fy = m.forecast_years
y5, h3 = fy[-1], hist.years[-1]
bc = m.verify_balance_checks()
SC_COL = {"Bear": ui.NEG, "Base": ui.ACCENT_2, "Bull": ui.POS}

# ------------------------------------------------------------------ header
ui.masthead("Three-Statement Financial Model", SUBTITLE, kicker="Financial modelling",
            meta={"Company": f"{hist.company} ({hist.ticker})", "Source": hist.source,
                  "Historical": f"{hist.years[0].year}–{hist.years[-1].year}", "Forecast": f"{fy[0].year}–{y5.year}",
                  "Scenario": scenario, "Units": f"{hist.currency} millions"})

tabs = st.tabs(["Dashboard", "Drivers", "Statements", "Schedules", "Scenarios", "Checks & data", "Excel export"])


def year_table(data: dict, index, row_styles=None, fmt="acct1", container=None):
    ui.html_table(pd.DataFrame(data, index=index).T, fmt=fmt, row_styles=row_styles, container=container)


# ================================================================== Dashboard
with tabs[0]:
    hb = max(abs(y.balance_check) for y in hist.years)
    if bc["forecast_balanced"]:
        ui.callout(f"Balance sheet balances in every forecast year (largest difference {bc['max_error']:.6f}). "
                   f"Cash comes only from the cash-flow statement; there is no plug.", "pos", "Balanced")
    else:
        st.error(f"Balance check failed: largest difference {bc['max_error']:,.4f}.")
    if hb > 0.5:
        ui.callout(f"The reported historical balance sheet does not balance (difference up to {hb:,.1f}); "
                   "it is shown, not plugged.", "warn", "Historical data")
    for w in m.warnings():
        ui.callout(w, "warn", "Note")
    cagr = (y5.revenue / h3.revenue) ** (1 / 5) - 1
    peak_rev = max(y.revolver_debt for y in fy)
    bal = 0.0 if abs(y5.balance_check) < 5e-7 else y5.balance_check
    ui.kpis([
        dict(label=f"Revenue {y5.year}", value=fmt_m(y5.revenue), delta=f"{cagr:+.1%} CAGR", tone=ui.tone(cagr)),
        dict(label=f"Net income {y5.year}", value=fmt_m(y5.ni_common), delta=f"{y5.ni_common / y5.revenue:.1%} margin",
             tone=ui.tone(y5.ni_common), value_tone="neg" if y5.ni_common < 0 else ""),
        dict(label=f"Ending cash {y5.year}", value=fmt_m(y5.cash), note=f"min {fmt_m(user.min_cash_balance)}",
             tone="pos" if y5.cash >= user.min_cash_balance - 1e-6 else "warn",
             delta="above minimum" if y5.cash >= user.min_cash_balance - 1e-6 else "at minimum"),
        dict(label=f"Revolver {y5.year}", value=fmt_m(y5.revolver_debt), delta=f"peak {fmt_m(peak_rev)}",
             tone="warn" if peak_rev > 0.05 else "neutral", note=f"capacity {fmt_m(user.revolver_capacity)}"),
        dict(label=f"Balance check {y5.year}", value=f"{bal:.6f}", delta="A − L − E", tone="pos" if abs(bal) < 1e-3
             else "neg", accent=ui.POS if abs(bal) < 1e-3 else ui.NEG),
    ])

    yrs = [str(y.year) for y in m.all_years]
    n_hist = len(hist.years)
    ui.section("Performance and liquidity", "Shaded area = forecast years.", kicker=f"{hist.currency} millions")
    g1, g2 = st.columns(2, gap="medium")
    fig = go.Figure()
    fig.add_vrect(x0=n_hist - 0.5, x1=len(yrs) - 0.5, fillcolor=ui.SURFACE_2, opacity=0.7, line_width=0, layer="below",
                  annotation_text="Forecast", annotation_position="top left",
                  annotation_font=dict(size=11, color=ui.MUTED))
    fig.add_bar(x=yrs, y=[y.revenue for y in m.all_years], name="Revenue", marker_color=ui.ACCENT_2,
                hovertemplate="%{y:,.0f}")
    fig.add_scatter(x=yrs, y=[y.ebit for y in m.all_years], name="EBIT", mode="lines+markers",
                    line=dict(color=ui.PALETTE[2], width=3), hovertemplate="%{y:,.0f}")
    fig.add_scatter(x=yrs, y=[y.ni_common for y in m.all_years], name="Net income", mode="lines+markers",
                    line=dict(color=ui.POS, width=3), hovertemplate="%{y:,.0f}")
    ui.style_fig(fig, "Revenue, EBIT and net income", f"{scenario} case, historical and forecast", height=420)
    fig.update_yaxes(tickformat=",.0f")
    ui.chart(fig, container=g1)

    fig = go.Figure()
    fig.add_vrect(x0=n_hist - 0.5, x1=len(yrs) - 0.5, fillcolor=ui.SURFACE_2, opacity=0.7, line_width=0, layer="below")
    fig.add_bar(x=yrs, y=[y.cash for y in m.all_years], name="Cash", marker_color=ui.PALETTE[1],
                hovertemplate="%{y:,.0f}")
    fig.add_bar(x=yrs, y=[y.revolver_debt for y in m.all_years], name="Revolver", marker_color=ui.NEG,
                hovertemplate="%{y:,.0f}")
    fig.add_scatter(x=yrs, y=[y.senior_debt for y in m.all_years], name="Term debt", mode="lines+markers",
                    line=dict(color=ui.PALETTE[4], width=3), hovertemplate="%{y:,.0f}")
    fig.add_hline(y=user.min_cash_balance, line_dash="dot", line_color=ui.WARN, line_width=1.3,
                  annotation_text="minimum cash", annotation_font=dict(color=ui.WARN, size=11))
    ui.style_fig(fig, "Cash, revolver and term debt", "Revolver draws when cash would fall below the minimum",
                 height=420)
    fig.update_layout(barmode="group")
    fig.update_yaxes(tickformat=",.0f")
    ui.chart(fig, container=g2)

    ui.section("How the money flows", f"Income statement for {y5.year} and the five-year cash bridge.",
               kicker=f"{hist.currency} millions")
    g1, g2 = st.columns(2, gap="medium")
    isf = M.statement_frame(m, M.IS_ROWS)[y5.year]
    meas, xs, ys = [], [], []
    for label, attr, sign, style in M.IS_ROWS:
        v = isf.get(label)
        v = 0.0 if v is None or pd.isna(v) else float(v)
        if style in ("total", "grand") and label != "Revenue":
            if label in ("EBITDA", "Pre-tax income (EBT)", "Net income (consolidated)"):
                continue
            meas.append("total"); xs.append(label); ys.append(0.0)
        elif abs(v) >= 0.05 or label == "Revenue":
            meas.append("relative"); xs.append(label); ys.append(v)
    short = {"Revenue": "Revenue", "Cost of goods sold": "COGS", "Gross profit": "Gross profit", "SG&A": "SG&A",
             "R&D": "R&D", "Other operating items / D&A reclassification": "Other opex",
             "Depreciation & amortization": "D&A", "Operating income (EBIT, as reported)": "EBIT",
             "Interest expense - term debt": "Interest (term)", "Interest expense - revolver": "Interest (revolver)",
             "Interest income": "Interest income", "Other non-operating income / (expense)": "Other non-op",
             "Income tax": "Tax", "Discontinued operations & other (after tax)": "Disc. ops",
             "Attributable to NCI & preferred": "NCI", "Net income to common shareholders": "Net income"}
    tot_vals = {"Gross profit": y5.gross_profit, "Operating income (EBIT, as reported)": y5.ebit,
                "Net income to common shareholders": y5.ni_common}
    fig = go.Figure(go.Waterfall(
        measure=meas, x=[short.get(x, x) for x in xs], y=ys,
        text=[ui.acct(tot_vals.get(x, v), 0) if (mm_ == "total" or x == "Revenue") else
              (ui.acct(v, 0) if abs(v) >= 0.08 * abs(y5.revenue) else "") for x, v, mm_ in zip(xs, ys, meas)],
        textposition="outside", textfont=dict(size=11.5, color=ui.INK),
        increasing=dict(marker=dict(color=ui.ACCENT_2)), totals=dict(marker=dict(color=ui.INK)),
        hovertemplate="%{x}<br>%{y:,.1f}<extra></extra>"))
    ui.style_fig(fig, f"From revenue to net income, {y5.year}", "Costs in red; subtotals in ink; hover for every line",
                 height=460, legend=False, hovermode="closest")
    fig.update_layout(uniformtext=dict(minsize=11, mode="show"))
    fig.update_yaxes(tickformat=",.0f")
    fig.update_xaxes(showspikes=False, tickangle=-35)
    ui.chart(fig, container=g1)

    flows = [("CFO", sum(y.cfo for y in fy)), ("Capex", sum(y.cfi_capex for y in fy)),
             ("Other investing", sum(y.cfi_other for y in fy)), ("Dividends", sum(y.cff_dividends_paid for y in fy)),
             ("Buybacks", sum(y.cff_share_buybacks for y in fy)),
             ("Term debt", sum(y.cff_debt_issued + y.cff_debt_repaid for y in fy)),
             ("Revolver", sum(y.cff_revolver_change for y in fy)),
             ("NCI", sum(y.cff_nci_distributions for y in fy)), ("Other financing", sum(y.cff_other for y in fy))]
    beg, end = fy[0].beginning_cash, y5.cash
    resid = end - beg - sum(v for _, v in flows)
    if abs(resid) >= 0.05:
        flows.append(("FX & other", resid))
    flows = [(n, v) for n, v in flows if abs(v) >= 0.05]
    fig = go.Figure(go.Waterfall(
        measure=["absolute"] + ["relative"] * len(flows) + ["total"],
        x=["Opening cash"] + [n for n, _ in flows]
          + [f"Cash {y5.year}"],
        y=[beg] + [v for _, v in flows] + [0.0],
        text=[ui.acct(beg, 0)] + [ui.acct(v, 0) for _, v in flows] + [ui.acct(end, 0)], textposition="outside",
        textfont=dict(size=11, color=ui.INK),
        increasing=dict(marker=dict(color=ui.POS)), decreasing=dict(marker=dict(color=ui.NEG)),
        totals=dict(marker=dict(color=ui.PALETTE[1])),
        hovertemplate="%{x}<br>%{y:,.1f}<extra></extra>"))
    ui.style_fig(fig, f"Cash bridge, {fy[0].year}–{y5.year}", "Five-year totals: green adds cash, red uses it",
                 height=460, legend=False, hovermode="closest")
    fig.update_yaxes(tickformat=",.0f")
    fig.update_xaxes(showspikes=False, tickangle=-35)
    fig.update_layout(uniformtext=dict(minsize=11, mode="show"))
    ui.chart(fig, container=g2)

    # Sankey of where the revenue goes (only when the flows are all positive)
    opex = y5.sga + y5.rd + y5.other_opex
    net_int = y5.interest_expense - y5.interest_income
    divs, bbs = -y5.cff_dividends_paid, -y5.cff_share_buybacks
    retained = y5.ni_common - divs - bbs
    parts = [y5.cogs, y5.gross_profit, opex, y5.da, y5.ebit, y5.tax_expense, y5.ni_common]
    if all(v > 0 for v in parts) and y5.ebit - y5.tax_expense - max(net_int, 0) > 0:
        nodes = ["Revenue", "Cost of goods sold", "Gross profit", "Operating expenses", "D&A", "EBIT",
                 "Net interest & other", "Tax", "Net income", "Dividends", "Buybacks", "Retained / other"]
        ncol = [ui.ACCENT_2, ui.NEG, ui.ACCENT_2, ui.NEG, ui.NEG, ui.ACCENT_2, ui.NEG, ui.NEG, ui.POS,
                ui.PALETTE[2], ui.PALETTE[4], ui.PALETTE[1]]
        other_below = y5.ebit - y5.tax_expense - y5.ni_common   # interest, other non-op, disc. ops, NCI
        links = [(0, 1, y5.cogs), (0, 2, y5.gross_profit), (2, 3, opex), (2, 4, y5.da), (2, 5, y5.ebit),
                 (5, 6, max(other_below, 0)), (5, 7, y5.tax_expense), (5, 8, y5.ni_common)]
        if divs > 0:
            links.append((8, 9, min(divs, y5.ni_common)))
        if bbs > 0:
            links.append((8, 10, min(bbs, max(y5.ni_common - max(divs, 0), 0))))
        if retained > 0:
            links.append((8, 11, retained))
        links = [l for l in links if l[2] > 0.05]
        fig = go.Figure(go.Sankey(
            arrangement="snap", valueformat=",.0f",
            node=dict(label=nodes, color=ncol, pad=22, thickness=16, line=dict(width=0),
                      hovertemplate="%{label}: %{value:,.0f}<extra></extra>"),
            link=dict(source=[l[0] for l in links], target=[l[1] for l in links], value=[l[2] for l in links],
                      color=[ui.rgba(ncol[l[1]], 0.22) for l in links],
                      hovertemplate="%{source.label} → %{target.label}: %{value:,.0f}<extra></extra>")))
        ui.style_fig(fig, f"Where each dollar of {y5.year} revenue goes",
                     "Revenue to costs, profit, tax and payouts (buybacks above net income are funded by cash)",
                     height=440, legend=False, hovermode="closest")
        fig.update_layout(font=dict(size=12.5))
        ui.chart(fig)

    ui.section("Cash bridge by year", kicker=f"{hist.currency} millions")
    year_table({
        "Beginning cash": [y.beginning_cash for y in fy], "CFO": [y.cfo for y in fy], "Capex": [y.cfi_capex for y in fy],
        "Dividends": [y.cff_dividends_paid for y in fy], "Buybacks": [y.cff_share_buybacks for y in fy],
        "Term debt": [y.cff_debt_issued + y.cff_debt_repaid for y in fy], "Revolver": [y.cff_revolver_change for y in fy],
        "NCI distributions": [y.cff_nci_distributions for y in fy], "Ending cash": [y.cash for y in fy],
    }, [y.year for y in fy], row_styles={"Ending cash": "grand"})

# ================================================================== Drivers
with tabs[1]:
    ui.section("Forecast drivers", "Edit any driver (percentages in %). Defaults come from the 3 historical years; "
               "the scenario deltas are added on top for Bull and Bear.", kicker="Editable")
    st.data_editor(drivers_frame(base), width="stretch", height=870, key=EDITOR_KEY, disabled=["_index"])
    if st.button("Reset drivers to the historical baseline", icon=":material/restart_alt:"):
        st.session_state.data_key = None
        st.rerun()
    ui.section("How the defaults were set")
    for n in st.session_state.driver_notes:
        st.markdown(f"- {esc(n)}")
    st.markdown(esc("- Growth: average historical growth, faded ×1.0, 0.9, 0.8, 0.75, 0.75. Margins and opex: "
                    "3-year averages of % of revenue. D&A: D&A ÷ beginning net PP&E. DSO on revenue; DIO and DPO on "
                    "COGS (365 days). Payout and buybacks: % of net income to common."))


# ================================================================== Statements
def show_statement(rows, title, caption):
    df = M.statement_frame(m, rows)
    styles = {label: {"total": "total", "grand": "grand", "memo": "sub"}.get(style, "") for label, _, _, style in rows}
    ui.section(title, caption, kicker=f"{hist.currency} millions")
    ui.html_table(df, fmt=acct1, row_styles=styles, max_height=1400)


with tabs[2]:
    s = st.radio("Statement", ["Income statement", "Balance sheet", "Cash flow"], horizontal=True,
                 label_visibility="collapsed")
    if s == "Income statement":
        show_statement(M.IS_ROWS, "Income statement", "Costs shown negative, in red parentheses.")
    elif s == "Balance sheet":
        show_statement(M.BS_ROWS, "Balance sheet", "Treasury stock deducted; the balance check must be 0.")
    else:
        show_statement(M.CFS_ROWS, "Cash-flow statement", "Indirect method.")
        st.caption("Historical 'other' lines are the residual between the reported total and the lines shown, "
                   "so every subtotal equals the reported figure.")

# ================================================================== Schedules
with tabs[3]:
    p = [hist.years[-1]] + fy[:-1]
    idx = [y.year for y in fy]
    xs_ = [str(i) for i in idx]
    g1, g2 = st.columns(2, gap="medium")
    fig = go.Figure()
    fig.add_bar(x=xs_, y=[y.cash_pre_revolver for y in fy], name="Cash before revolver",
                marker_color=[ui.PALETTE[1] if y.cash_pre_revolver >= user.min_cash_balance else ui.WARN for y in fy],
                hovertemplate="%{y:,.0f}")
    fig.add_bar(x=xs_, y=[y.revolver_debt for y in fy], name="Ending revolver", marker_color=ui.NEG,
                hovertemplate="%{y:,.0f}")
    fig.add_hline(y=user.min_cash_balance, line_dash="dot", line_color=ui.WARN,
                  annotation_text="minimum cash", annotation_font=dict(color=ui.WARN, size=11))
    ui.style_fig(fig, "Liquidity test", "Amber = cash would fall below the minimum, so the revolver draws",
                 height=420)
    fig.update_layout(barmode="group")
    fig.update_yaxes(tickformat=",.0f")
    ui.chart(fig, container=g1)
    fig = go.Figure()
    fig.add_scatter(x=xs_, y=[y.senior_debt for y in fy], name="Term debt", mode="lines", stackgroup="debt",
                    line=dict(color=ui.PALETTE[4], width=1.5), fillcolor=ui.rgba(ui.PALETTE[4], 0.45),
                    hovertemplate="%{y:,.0f}")
    fig.add_scatter(x=xs_, y=[y.revolver_debt for y in fy], name="Revolver", mode="lines", stackgroup="debt",
                    line=dict(color=ui.NEG, width=1.5), fillcolor=ui.rgba(ui.NEG, 0.45), hovertemplate="%{y:,.0f}")
    fig.add_scatter(x=xs_, y=[y.interest_expense for y in fy], name="Interest expense (rhs)", mode="lines+markers",
                    line=dict(color=ui.INK, width=2, dash="dot"), yaxis="y2", hovertemplate="%{y:,.1f}")
    ui.style_fig(fig, "Debt and interest", "Stacked debt balances; interest on the right axis", height=420)
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, tickformat=",.0f",
                                  tickfont=dict(size=12, color=ui.MUTED), rangemode="tozero", automargin=True), margin=dict(r=84))
    fig.update_layout(yaxis=dict(tickformat=",.0f"))
    ui.chart(fig, container=g2)

    ui.section("Term debt and revolver", "The revolver tops cash up to the minimum, within capacity.",
               kicker=f"{hist.currency} millions")
    year_table({
        "Beginning term debt": [x.senior_debt for x in p], "+ Issuance": [y.cff_debt_issued for y in fy],
        "− Repayment": [y.cff_debt_repaid for y in fy], "Ending term debt": [y.senior_debt for y in fy],
        "Cash before revolver": [y.cash_pre_revolver for y in fy], "Minimum cash": [user.min_cash_balance] * 5,
        "Revolver draw": [y.revolver_draw for y in fy], "Revolver repayment": [-y.revolver_repayment for y in fy],
        "Ending revolver": [y.revolver_debt for y in fy], "Capacity": [user.revolver_capacity] * 5}, idx,
        row_styles={"Ending term debt": "total", "Ending revolver": "total"})
    ui.section("PP&E roll-forward", "Capex adds, depreciation reduces.")
    year_table({"Beginning net PP&E": [x.net_ppe for x in p], "+ Capex": [-y.cfi_capex for y in fy],
                "− D&A": [-y.da for y in fy], "Ending net PP&E": [y.net_ppe for y in fy]}, idx,
               row_styles={"Ending net PP&E": "total"})
    ui.section("Working capital", "365-day year.")
    year_table({"AR = DSO/365 × revenue": [y.accounts_receivable for y in fy],
                "Inventory = DIO/365 × COGS": [y.inventory for y in fy],
                "AP = DPO/365 × COGS": [y.accounts_payable for y in fy],
                "Change in NWC (cash effect)": [y.cfo_change_nwc for y in fy]}, idx,
               row_styles={"Change in NWC (cash effect)": "total"})
    ui.section("Interest and the circularity", "Interest on average or beginning balances.")
    year_table({"Interest - term debt": [y.interest_expense_term for y in fy],
                "Interest - revolver": [y.interest_expense_revolver for y in fy],
                "Interest income": [y.interest_income for y in fy]}, idx)
    circ = "beginning balances (no circularity)" if (user.interest_calc_method == "beginning" or user.circuit_breaker) \
        else ", ".join(f"{y.year}: {y.circularity_iterations} iterations" + (" (breaker tripped)" if y.breaker_tripped else "")
                       for y in fy)
    st.caption(esc(f"Interest solved on {circ}."))

# ================================================================== Scenarios
with tabs[4]:
    comp = M.scenario_comparison(models)
    pct_cols = ["Revenue CAGR (5y)", "Year-5 EBIT margin"]
    ui.kpis([dict(label=f"{n} case · revenue {mm.forecast_years[-1].year}", value=fmt_m(mm.forecast_years[-1].revenue),
                  delta=f"{(mm.forecast_years[-1].revenue / h3.revenue) ** (1 / 5) - 1:+.1%} CAGR",
                  tone=ui.tone((mm.forecast_years[-1].revenue / h3.revenue) - 1), accent=SC_COL[n],
                  note=f"NI {fmt_m(mm.forecast_years[-1].ni_common)}") for n, mm in models.items()], cols=3)
    g1, g2 = st.columns(2, gap="medium")
    fig = go.Figure()
    for n, mm in models.items():
        fig.add_scatter(x=[str(y.year) for y in mm.all_years], y=[y.revenue for y in mm.all_years], name=n,
                        mode="lines+markers", line=dict(color=SC_COL[n], width=3 if n == scenario else 2,
                                                        dash="solid" if n == "Base" else "dash" if n == "Bear" else "dot"),
                        hovertemplate="%{y:,.0f}")
    ui.style_fig(fig, "Revenue by scenario", "Historical years are shared; forecasts diverge", height=420)
    fig.update_yaxes(tickformat=",.0f")
    ui.chart(fig, container=g1)
    metrics = [("Net income", lambda y: y.ni_common), ("Ending cash", lambda y: y.cash),
               ("Free cash flow", lambda y: y.fcf), ("Revolver", lambda y: y.revolver_debt)]
    fig = go.Figure()
    for n, mm in models.items():
        yy = mm.forecast_years[-1]
        fig.add_bar(x=[k for k, _ in metrics], y=[f(yy) for _, f in metrics], name=n, marker_color=SC_COL[n],
                    hovertemplate=n + ": %{y:,.0f}<extra></extra>")
    ui.style_fig(fig, f"Year-5 outcomes by scenario", f"{y5.year}, {hist.currency} millions", height=420,
                 hovermode="closest")
    fig.update_layout(barmode="group")
    fig.update_yaxes(tickformat=",.0f")
    fig.update_xaxes(showspikes=False)
    ui.chart(fig, container=g2)
    ui.section("Scenario comparison", kicker=f"{hist.currency} millions")
    row_fmt = {c: ("pct" if c in pct_cols else ("num6" if "error" in c else acct1)) for c in comp.columns}
    ui.html_table(comp.T, fmt=acct1, row_fmt=row_fmt)
    ui.section("Scenario deltas", "Added to the base drivers in every forecast year.")
    ui.html_table(pd.DataFrame(M.SCENARIO_DELTAS).fillna(0.0).T, fmt="num3")

# ================================================================== Checks & data
with tabs[5]:
    ui.section("Integrity checks", "Every value must be 0.", kicker="Controls")
    ui.html_table(m.integrity_checks().T, fmt="num6")
    ui.section("Historical balance check", "Reported totals, never plugged.")
    year_table({"Total assets": [y.total_assets for y in hist.years],
                "Total liabilities": [y.total_liabilities for y in hist.years],
                "Total equity (incl. NCI)": [y.total_equity for y in hist.years],
                "Difference": [y.balance_check for y in hist.years]}, [y.year for y in hist.years],
               row_styles={"Difference": "total"}, fmt=f1)
    if hist.warnings:
        ui.section("Data warnings")
        for w in hist.warnings:
            st.markdown(f"- {esc(w)}")
    if hist.mapping is not None:
        ui.section("Which source line fed each model line")
        st.dataframe(hist.mapping, width="stretch")

# ================================================================== Excel
with tabs[6]:
    ui.section("Excel model", "Live formulas: every forecast cell is linked to the Assumptions sheet.", kicker="Export")
    ui.callout("Iterative calculation is switched on for the interest circularity; set the circuit breaker on the "
               "Assumptions sheet to 1 if the file ever shows errors. The Checks sheet must show 0.", "info", "Tip")
    wb, _ = xe.build_workbook(m, hist.source, hist.warnings, hist.mapping)
    st.download_button("Download Excel model", xe.to_bytes(wb),
                       f"{hist.ticker}_{scenario}_three_statement_model.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary",
                       icon=":material/download:", width="stretch")

ui.footer("Educational model, not investment advice.")
