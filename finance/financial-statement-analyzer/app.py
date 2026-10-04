"""
Financial Statement Analyzer - Streamlit Application (app.py)
--------------------------------------------------------------
Ratio analysis of annual statements for one company or a peer group.
Features:
- Multi-ticker Yahoo Finance statement extraction (4-year annual data), offline snapshot fallback
- Custom statement Excel & CSV upload with template support
- 6 key ratio categories with benchmarks & explanations
- 3-step and 5-step DuPont decomposition models
- Altman Z-Score & 9-criterion Piotroski F-Score
- Common-size (vertical) and horizontal (trend/indexed) statements
- Rule-based plain-English financial health diagnostic report
- Interactive Plotly charts (scorecard bullets, Z-zones, F-score grid, peer radar)
- Exports: live-formula Excel (.xlsx), PDF and Markdown health reports

All calculations live in analyzer.py; the look comes from ui_theme.py, the shared design system of
the finance portfolio (vendored into this project).
"""

from __future__ import annotations
import json
import os
from typing import List, Dict, Optional, Tuple

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import ui_theme as ui
from analyzer import FinancialData, FinancialAnalyzer, _safe_float
from excel_export import export_analysis_to_excel
from report_export import generate_markdown_report, generate_pdf_report, fmt_value

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_FILE = os.path.join(HERE, "data", "snapshots.json")

ui.apply("Financial Statement Analyzer · Yamen Agha", icon=":material/query_stats:")


def show_table(df: pd.DataFrame, currency: str = "USD", row_styles=None):
    """Ratio table with per-row formatting (fmt_value); missing values show as n/a, negatives in red."""
    if df is None or df.empty:
        st.caption("No data.")
        return
    out = pd.DataFrame({c: [fmt_value(str(i), df.loc[i, c], currency) for i in df.index] for c in df.columns},
                       index=[str(i) for i in df.index])
    out.columns = [f"FY {c}" for c in out.columns]
    ui.html_table(out, fmt="plain", row_styles=row_styles)


def num_row(df: pd.DataFrame, row: str) -> List[Optional[float]]:
    return [_safe_float(v) for v in df.loc[row]] if row in df.index else []


# =====================================================================
# Caching Data Loader
# =====================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def load_ticker_data(ticker_symbol: str) -> Tuple[Optional[FinancialData], Optional[str]]:
    """Loads financial statements via yfinance (cached); falls back to the offline snapshot."""
    err = "offline mode"
    try:
        if os.environ.get("FSA_OFFLINE"):  # tests / no internet: use data/snapshots.json only
            raise RuntimeError("offline mode (FSA_OFFLINE is set)")
        data = FinancialData.from_yfinance(ticker_symbol)
        if len(data.years) > 0:
            return data, None
        err = f"No annual financial statement data found for '{ticker_symbol}'."
    except Exception as e:
        err = f"Error retrieving data for '{ticker_symbol}': {e}"
    try:
        with open(SNAPSHOT_FILE, encoding="utf-8") as fh:
            snaps = json.load(fh)
        if ticker_symbol.upper() in snaps:
            snap = snaps[ticker_symbol.upper()]
            data = FinancialData.from_snapshot(snap)
            data.company_name += f" [offline snapshot {snap.get('fetched', '')}]"
            return data, None
    except Exception:
        pass
    return None, err


def load_file_data(uploaded_file, symbol: str, company_name: str,
                   market_cap: Optional[float] = None) -> Tuple[Optional[FinancialData], Optional[str]]:
    """Parses user uploaded Excel or CSV statement file."""
    try:
        data = FinancialData.from_excel_or_csv(
            uploaded_file,
            symbol=symbol or "UPLOAD",
            company_name=company_name or "Uploaded Company",
            market_cap=market_cap,
        )
        if len(data.years) == 0:
            return None, "No recognizable annual statement columns or line items found in uploaded file."
        return data, None
    except Exception as e:
        return None, f"Failed to parse uploaded statement file: {str(e)}"


# =====================================================================
# Sidebar: data source, tickers, uploads
# =====================================================================
with st.sidebar:
    ui.sidebar_brand("Statement Analyzer")
    ui.sidebar_section("Data")
    data_source = st.radio(
        "Data Source",
        ["Yahoo Finance Ticker(s)", "Upload Custom Financials (CSV / Excel)"],
        index=0,
        help="Yahoo Finance falls back to a saved offline snapshot when there is no internet."
    )

    tickers_to_analyze: List[str] = []
    primary_ticker = "AAPL"
    uploaded_data_obj = None

    if data_source == "Yahoo Finance Ticker(s)":
        ticker_input = st.text_input(
            "Stock Ticker(s)",
            value="AAPL, MSFT",
            help="Enter one or more comma-separated tickers for peer comparison (e.g. AAPL, MSFT, GOOGL)"
        )
        raw_tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
        tickers_to_analyze = raw_tickers if raw_tickers else ["AAPL"]
        primary_ticker = tickers_to_analyze[0]

        ui.sidebar_section("Quick peer comparisons")
        for _lab, _tk in (("Tech: AAPL vs MSFT", "AAPL, MSFT"), ("Payments: V vs MA", "V, MA"),
                          ("Beverages: KO vs PEP", "KO, PEP"), ("Industrials: CAT vs DE", "CAT, DE")):
            if st.button(_lab, width="stretch"):
                st.session_state["quick_ticker"] = _tk
                st.rerun()

        if "quick_ticker" in st.session_state:
            tickers_to_analyze = [t.strip().upper() for t in st.session_state["quick_ticker"].split(",")]
            primary_ticker = tickers_to_analyze[0]

    else:
        ui.sidebar_section("Upload private company statements")
        st.caption("Upload an Excel file with tabs `Income Statement`, `Balance Sheet`, `Cash Flow`, or a unified CSV.")
        with open(os.path.join(HERE, "templates", "financial_statements_template.xlsx"), "rb") as f_xl:
            st.download_button(
                "Download Excel template",
                f_xl.read(),
                file_name="financial_statements_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch", icon=":material/download:",
            )
        with open(os.path.join(HERE, "templates", "financial_statements_template.csv"), "rb") as f_csv:
            st.download_button(
                "Download CSV template",
                f_csv.read(),
                file_name="financial_statements_template.csv",
                mime="text/csv",
                width="stretch", icon=":material/download:",
            )

        uploaded_file = st.file_uploader("Upload Completed Statement File", type=["xlsx", "xls", "csv"])
        custom_symbol = st.text_input("Custom Ticker / Code", value="ACME")
        custom_company = st.text_input("Company Name", value="Acme Enterprise Corp")
        custom_mcap = st.number_input("Market value of equity at the latest year end (optional, same units as the file)",
                                      min_value=0.0, value=0.0, step=1_000_000.0, format="%.0f",
                                      help="Used only for the original Altman Z (X4). Leave 0 for a private company: "
                                           "Z is then n/a and Z'' (book equity) is used.")

        if uploaded_file is not None:
            uploaded_data_obj, upload_err = load_file_data(uploaded_file, custom_symbol, custom_company,
                                                           custom_mcap or None)
            if upload_err:
                st.error(upload_err)
            else:
                tickers_to_analyze = [custom_symbol]
                primary_ticker = custom_symbol

    st.caption("Excel export with live formulas · 3- and 5-step DuPont · Altman Z / Z'' and Piotroski F · "
               "rule-based health report. Educational project, not investment advice.")


# =====================================================================
# Load data
# =====================================================================
SUBTITLE = ("Ratios, DuPont, Altman Z, Piotroski F, common-size and trend analysis from annual statements, with an "
            "Excel export where every ratio is a live formula. Missing data is shown as n/a, never guessed.")
loaded_data_dict: Dict[str, FinancialData] = {}
loaded_analyzers: Dict[str, FinancialAnalyzer] = {}
load_warnings: List[str] = []

with st.spinner("Retrieving financial statements and computing accounting ratios..."):
    if data_source == "Yahoo Finance Ticker(s)":
        for tick in tickers_to_analyze:
            d_obj, err = load_ticker_data(tick)
            if err:
                load_warnings.append(err)
            elif d_obj:
                loaded_data_dict[tick] = d_obj
                loaded_analyzers[tick] = FinancialAnalyzer(d_obj)
    else:
        if uploaded_data_obj:
            loaded_data_dict[primary_ticker] = uploaded_data_obj
            loaded_analyzers[primary_ticker] = FinancialAnalyzer(uploaded_data_obj)

if not loaded_data_dict:
    ui.masthead("Financial Statement Analyzer", SUBTITLE, kicker="Financial analysis")
    for w in load_warnings:
        ui.callout(w, "warn", "Data")
    st.error("No active financial data loaded. Please enter a valid ticker or upload a completed template file.")
    ui.footer()
    st.stop()

if len(loaded_data_dict) > 1:
    selected_target = st.sidebar.selectbox(
        "Company for the in-depth tabs",
        options=list(loaded_data_dict.keys()),
        index=0,
        format_func=lambda s: f"{s} · {loaded_data_dict[s].company_name}",
        help="The dashboard, statements, ratios and scoring tabs show this company; the Peer Comparison tab shows all."
    )
else:
    selected_target = list(loaded_data_dict.keys())[0]

target_data = loaded_data_dict[selected_target]
target_analyzer = loaded_analyzers[selected_target]
years = target_data.years
latest_y = years[-1] if years else ""
prior_y = years[-2] if len(years) > 1 else None
CUR = target_data.currency
FY = [f"FY {y}" for y in years]

_mc = target_data.market_cap
mcap_str = ("n/a" if not _mc else f"{_mc/1e12:,.2f}T" if _mc >= 1e12 else f"{_mc/1e9:,.1f}B")
price_str = f"{target_data.share_price:,.2f}" if target_data.share_price else "n/a"
ui.masthead("Financial Statement Analyzer", SUBTITLE, kicker="Financial analysis",
            meta={"Entity": f"{target_data.company_name} ({target_data.symbol})", "Sector": target_data.sector,
                  "Industry": target_data.industry, "Currency": CUR, "Periods": f"{len(years)} fiscal years",
                  "Market cap": mcap_str, "Share price": price_str})
for w in load_warnings:
    ui.callout(w, "warn", "Data")

# =====================================================================
# Tabs
# =====================================================================
tabs = st.tabs([
    "Executive Health Dashboard",
    "Financial Statements",
    "Key Financial Ratios",
    "DuPont & Credit Scoring",
    "Peer Comparison",
    "Export Center",
])

liq = target_analyzer.calculate_liquidity_ratios()
prof = target_analyzer.calculate_profitability_ratios()
solv = target_analyzer.calculate_solvency_ratios()
cfq = target_analyzer.calculate_cash_flow_quality()
altman = target_analyzer.calculate_altman_z_score()
piotroski = target_analyzer.calculate_piotroski_f_score()
health_rep = target_analyzer.generate_health_report()


def latest_and_delta(df: pd.DataFrame, row: str):
    if row not in df.index:
        return None, None
    v = _safe_float(df.loc[row, latest_y])
    p = _safe_float(df.loc[row, prior_y]) if prior_y else None
    return v, (v - p if v is not None and p is not None else None)


def pp(delta: Optional[float]) -> Optional[str]:
    return None if delta is None else f"{delta * 100:+.1f} pp vs FY {prior_y}"


# =====================================================================
# TAB 1: EXECUTIVE HEALTH DASHBOARD
# =====================================================================
with tabs[0]:
    z_val = _safe_float(altman.loc["Altman Z-Score", latest_y])
    z_zone = str(altman.loc["Zone (Original)", latest_y])
    z_title = "Altman Z-Score"
    if z_val is None and _safe_float(altman.loc["Altman Z''-Score (Non-Mfg)", latest_y]) is not None:
        z_val = _safe_float(altman.loc["Altman Z''-Score (Non-Mfg)", latest_y])
        z_zone = str(altman.loc["Zone (Non-Mfg)", latest_y])
        z_title = "Altman Z''-Score"
    z_tone = "pos" if z_zone == "Safe Zone" else ("neg" if z_zone == "Distress Zone" else "warn")
    f_score_val = piotroski["scores"].get(latest_y)
    f_tone = ("neutral" if f_score_val is None else "pos" if f_score_val >= 7 else ("neg" if f_score_val <= 3 else "warn"))
    roe_val, roe_d = latest_and_delta(prof, "Return on Equity (ROE)")
    fcf_m, fcf_d = latest_and_delta(cfq, "FCF Margin")
    cr_val, cr_d = latest_and_delta(liq, "Current Ratio")
    om_val, om_d = latest_and_delta(prof, "Operating Margin")

    ui.kpis([
        dict(label=z_title, value=f"{z_val:.2f}" if z_val is not None else "n/a", delta=z_zone if z_val is not None
             else "not measurable", tone=z_tone if z_val is not None else "neutral", arrow=False),
        dict(label="Piotroski F-Score", value=f"{f_score_val} / 9" if f_score_val is not None else "n/a",
             delta={"pos": "Strong", "warn": "Moderate", "neg": "Weak"}.get(f_tone, "not measurable"), tone=f_tone,
             arrow=False),
        dict(label="Return on equity", value=ui.pct(roe_val) if roe_val is not None else "n/a",
             delta=pp(roe_d), tone=ui.tone(roe_d), note=f"FY {latest_y}"),
        dict(label="FCF margin", value=ui.pct(fcf_m) if fcf_m is not None else "n/a", delta=pp(fcf_d),
             tone=ui.tone(fcf_d), note="FCF / revenue"),
        dict(label="Current ratio", value=f"{cr_val:.2f}x" if cr_val is not None else "n/a",
             delta="above 1.5x" if (cr_val or 0) >= 1.5 else "below 1.5x",
             tone="pos" if (cr_val or 0) >= 1.5 else "warn", arrow=False, note="benchmark > 1.5x"),
        dict(label="Operating margin", value=ui.pct(om_val) if om_val is not None else "n/a", delta=pp(om_d),
             tone=ui.tone(om_d), note="EBIT / revenue"),
    ], cols=6)

    status_kind = {"green": "pos", "red": "neg", "orange": "warn", "yellow": "warn"}.get(
        health_rep.get("status_color", "blue"), "info")
    ui.callout(health_rep["summary"], status_kind, f"Rule-based rating: {health_rep['overall_status']}")
    for note in health_rep.get("notes", []):
        ui.callout(note, "warn", "Note")

    ui.section("Diagnostic findings", "Rules applied to the latest fiscal year; each finding names the ratio behind it.")

    def finding_card(head, items, kind, empty):
        c = {"pos": ui.POS, "warn": ui.WARN, "neg": ui.NEG}[kind]
        if items:
            body = "".join(
                f'<div style="padding:12px 0;border-top:1px solid {ui.HAIRLINE}">'
                f'<div style="font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:{c};font-weight:600">'
                f'{ui._e(it["category"])}</div><div style="font-weight:600;color:{ui.INK};margin:2px 0 4px 0">'
                f'{ui._e(it["title"])}</div><div style="color:{ui.INK_2};font-size:13.5px;line-height:1.5">'
                f'{ui._e(it["detail"])}</div></div>' for it in items)
        else:
            body = (f'<div style="padding:12px 0;border-top:1px solid {ui.HAIRLINE};color:{ui.MUTED};font-size:13.5px">'
                    f'{ui._e(empty)}</div>')
        return (f'<div style="background:{ui.SURFACE};border:1px solid {ui.HAIRLINE};border-top:3px solid {c};'
                f'border-radius:8px;padding:16px 20px 8px 20px">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">'
                f'<span style="font-family:{ui.SERIF};font-size:18px;font-weight:600;color:{ui.INK}">{ui._e(head)}</span>'
                f'<span style="font-size:22px;font-weight:600;color:{c};font-variant-numeric:tabular-nums">{len(items)}</span>'
                f'</div>{body}</div>')

    heads = [("Strengths", health_rep["strengths"], "pos", "No significant strengths identified beyond standard thresholds."),
             ("Monitoring areas", health_rep["weaknesses"], "warn", "Zero material operational weaknesses flagged."),
             ("Red flags & alerts", health_rep["red_flags"], "neg",
              "Clean solvency & accrual screen: passed all severe credit distress and negative-accrual anomaly screens.")]
    st.markdown('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;align-items:stretch">'
                + "".join(finding_card(*h) for h in heads) + "</div>", unsafe_allow_html=True)

    ui.section("Trends and scorecard", f"{CUR} billions; the scorecard compares the latest year with common benchmarks.")
    g1, g2 = st.columns(2, gap="medium")
    rev = [target_data.get_raw_value("income", "revenue", y) for y in years]
    ni = [target_data.get_raw_value("income", "net_income", y) for y in years]
    fcf = num_row(cfq, "Free Cash Flow")
    b = lambda xs: [x / 1e9 if x is not None else None for x in xs]  # noqa: E731
    fig = go.Figure()
    fig.add_bar(x=FY, y=b(rev), name="Revenue", marker_color=ui.ACCENT_2, hovertemplate="%{y:,.1f}B")
    fig.add_scatter(x=FY, y=b(ni), name="Net income", mode="lines+markers", line=dict(color=ui.POS, width=3),
                    hovertemplate="%{y:,.1f}B")
    fig.add_scatter(x=FY, y=b(fcf), name="Free cash flow", mode="lines+markers",
                    line=dict(color=ui.PALETTE[2], width=3, dash="dot"), hovertemplate="%{y:,.1f}B")
    ui.style_fig(fig, "Revenue, net income and free cash flow", f"{target_data.company_name}, {CUR} billions",
                 height=460)
    fig.update_yaxes(tickformat=",.0f")
    ui.chart(fig, container=g1)

    # Bullet scorecard: latest value against a benchmark, with red / amber / green bands
    ic = _safe_float(solv.loc["Interest Coverage", latest_y]) if "Interest Coverage" in solv.index else None
    de = _safe_float(solv.loc["Debt-to-Equity", latest_y]) if "Debt-to-Equity" in solv.index else None
    score = [  # label, value, bands (lo, mid, max), benchmark, higher_is_better, number format, suffix
        ("Current ratio", cr_val, (1.0, 1.5, 3.0), 1.5, True, ".2f", "x"),
        ("Operating margin", om_val, (0.05, 0.15, 0.45), 0.15, True, ".0%", ""),
        ("Return on equity", roe_val, (0.08, 0.15, max(0.6, (roe_val or 0) * 1.1)), 0.15, True, ".0%", ""),
        ("FCF margin", fcf_m, (0.03, 0.10, 0.40), 0.10, True, ".0%", ""),
        ("Interest coverage", ic, (1.5, 3.0, max(20.0, min((ic or 0) * 1.1, 60.0))), 3.0, True, ".1f", "x"),
        ("Debt-to-equity", de, (1.0, 1.5, max(3.0, (de or 0) * 1.1)), 1.5, False, ".2f", "x"),
    ]
    score = [s_ for s_ in score if s_[1] is not None]
    if score:
        fig = go.Figure()
        n = len(score)
        for i, (lab, val, (lo, mid, hi), bench, hib, f_, suf) in enumerate(score):
            top = 1 - i / n - 0.02
            bot = 1 - (i + 1) / n + 0.06
            good = (val >= bench) if hib else (val <= bench)
            steps = ([dict(range=[0, lo], color=ui.NEG_BG), dict(range=[lo, mid], color=ui.WARN_BG),
                      dict(range=[mid, hi], color=ui.POS_BG)] if hib else
                     [dict(range=[0, lo], color=ui.POS_BG), dict(range=[lo, mid], color=ui.WARN_BG),
                      dict(range=[mid, hi], color=ui.NEG_BG)])
            fig.add_trace(go.Indicator(
                mode="number+gauge", value=min(val, hi) if val > 0 else 0,
                number=dict(valueformat=f_, suffix=suf, font=dict(size=16, color=ui.POS if good else ui.NEG,
                                                                  family=ui.SANS)),
                title=dict(text=f"<span style='font-size:12.5px;color:{ui.INK}'>{lab}</span>", align="right"),
                domain=dict(x=[0.30, 0.92], y=[bot, top]),
                gauge=dict(shape="bullet", axis=dict(range=[0, hi], tickformat=f_, tickfont=dict(size=10, color=ui.MUTED),
                                                     ticks=""),
                           steps=steps, bar=dict(color=ui.INK, thickness=0.38), bordercolor=ui.HAIRLINE, borderwidth=0,
                           threshold=dict(line=dict(color=ui.ACCENT, width=3), thickness=0.85, value=bench))))
        ui.style_fig(fig, f"Ratio scorecard, FY {latest_y}",
                     "Bar = latest value, teal tick = benchmark; green band = healthy range", height=460, legend=False)
        fig.update_layout(margin=dict(l=16, r=56, t=88, b=24))
        ui.chart(fig, container=g2)


# =====================================================================
# TAB 2: FINANCIAL STATEMENTS (RAW, COMMON-SIZE, HORIZONTAL)
# =====================================================================
with tabs[1]:
    c1, c2 = st.columns([2, 1], gap="medium")
    view_type = c1.radio(
        "Presentation Mode",
        ["Reported Values ($)", "Common-Size (Vertical %)", "Horizontal Trend (% YoY Change & Indexed)"],
        horizontal=True
    )
    statement_choice = c2.selectbox(
        "Select Financial Statement",
        ["Income Statement", "Balance Sheet", "Cash Flow Statement"]
    )

    def as_num(df):
        return df.apply(pd.to_numeric, errors="coerce")

    if view_type == "Reported Values ($)":
        scale_choice = st.radio("Display Scale", ["Raw Values", "In Millions ($M)", "In Billions ($B)"], index=1,
                                horizontal=True)
        df_to_show = {"Income Statement": target_data.income_statement, "Balance Sheet": target_data.balance_sheet,
                      "Cash Flow Statement": target_data.cash_flow}[statement_choice].copy()
        div, dp, unit = {"In Millions ($M)": (1e6, 1, f"{CUR} millions"), "In Billions ($B)": (1e9, 3, f"{CUR} billions"),
                         "Raw Values": (1.0, 0, CUR)}[scale_choice]
        ui.section(statement_choice, "As reported; negatives in red parentheses; n/a = not reported.", kicker=unit)
        ui.html_table(as_num(df_to_show) / div, fmt=f"acct{dp}", max_height=900)

    elif view_type == "Common-Size (Vertical %)":
        cs_dict = target_analyzer.calculate_common_size()
        pctf = lambda v: f"{v:.2f}%"  # noqa: E731
        if statement_choice == "Income Statement":
            ui.section("Common-size income statement", "Every line item as a percentage of total revenue "
                       "(revenue = 100.0%).", kicker="% of revenue")
            ui.html_table(as_num(cs_dict["income_statement"]), fmt=pctf, max_height=900)
        elif statement_choice == "Balance Sheet":
            ui.section("Common-size balance sheet", "Every line item as a percentage of total assets "
                       "(total assets = 100.0%).", kicker="% of assets")
            ui.html_table(as_num(cs_dict["balance_sheet"]), fmt=pctf, max_height=900)
        else:
            ui.callout("Vertical common-size is standard for Income Statement and Balance Sheet. For Cash Flow, "
                       "review the Cash Flow Quality tab.", "warn")

    else:
        horiz_dict = target_analyzer.calculate_horizontal_analysis()
        sub_view = st.radio("Horizontal Mode", ["YoY Percentage Change (%)", "Base-Year Indexed (Base Year = 100.0)"],
                            horizontal=True)
        h_data = {"Income Statement": horiz_dict["income_statement"], "Balance Sheet": horiz_dict["balance_sheet"],
                  "Cash Flow Statement": horiz_dict["cash_flow"]}[statement_choice]
        if sub_view == "YoY Percentage Change (%)":
            ui.section(f"{statement_choice}: year-on-year change", "(Year t − Year t−1) / Year t−1; red = decline.",
                       kicker="% change")
            ui.html_table(as_num(h_data["yoy"]), fmt=lambda v: f"{v:+.1f}%", color_positive=True, max_height=900)
        else:
            ui.section(f"{statement_choice}: indexed trend", f"Base year ({years[0]}) = 100.0; later years show the "
                       "cumulative change.", kicker="Index")
            ui.html_table(as_num(h_data["indexed"]), fmt=lambda v: f"{v:.1f}", max_height=900)


# =====================================================================
# TAB 3: KEY FINANCIAL RATIOS BY CATEGORY
# =====================================================================
def ratio_lines(df, rows, title, subtitle, yfmt, bench=None, height=420):
    fig = go.Figure()
    for i, r in enumerate([r for r in rows if r in df.index]):
        fig.add_scatter(x=FY, y=num_row(df, r), name=r, mode="lines+markers",
                        line=dict(color=ui.PALETTE[i % len(ui.PALETTE)], width=2.8), marker=dict(size=8),
                        hovertemplate=f"%{{y:{yfmt}}}")
    for yv, lab, col in (bench or []):
        fig.add_hline(y=yv, line_dash="dash", line_color=col, line_width=1.2, annotation_text=lab,
                      annotation_font=dict(color=col, size=11), annotation_position="top left")
    ui.style_fig(fig, title, subtitle, height=height)
    fig.update_yaxes(tickformat=yfmt)
    return fig


with tabs[2]:
    ratio_cat = st.tabs([
        "1. Liquidity",
        "2. Profitability",
        "3. Solvency & Leverage",
        "4. Efficiency & Working Capital",
        "5. Cash Flow Quality",
        "6. Growth (YoY)"
    ])

    with ratio_cat[0]:
        ui.callout_html(
            "<b>Current ratio (CA / CL)</b>: ability to cover short-term debts with short-term assets; conservative "
            "benchmark <b>&gt; 1.5x–2.0x</b>. <b>Quick ratio</b> ((cash + STI + receivables) / CL): acid test without "
            "inventory; target <b>&gt; 1.0x</b>. <b>Cash ratio</b> ((cash + STI) / CL): most conservative test; target "
            "<b>&gt; 0.2x–0.5x</b>.", "info", "Liquidity")
        liq_df = target_analyzer.calculate_liquidity_ratios()
        a, b_ = st.columns(2, gap="medium")
        with a:
            ui.subhead("Liquidity ratios", "Year-end balances")
            show_table(liq_df, CUR)
        ui.chart(ratio_lines(liq_df, list(liq_df.index), "Liquidity ratios over time", "Times current liabilities",
                             ".2f", [(1.0, "1.0x parity", ui.NEG), (1.5, "1.5x benchmark", ui.POS)], height=380),
                 container=b_)

    with ratio_cat[1]:
        ui.callout_html(
            "<b>Gross margin</b>: pricing power and production efficiency. <b>Operating margin</b> (EBIT / revenue): "
            "operating cost efficiency. <b>Net margin</b>: bottom-line profit per dollar of sales. <b>ROA</b>: target "
            "<b>&gt; 5%–10%</b>. <b>ROE</b>: target <b>&gt; 15%</b>. <b>ROIC</b> (NOPAT / invested capital) should "
            "exceed the WACC (~8–10%).", "info", "Profitability")
        prof_df = target_analyzer.calculate_profitability_ratios()
        show_table(prof_df, CUR)
        g1, g2 = st.columns(2, gap="medium")
        ui.chart(ratio_lines(prof_df, ["Gross Margin", "Operating Margin", "Net Profit Margin"], "Margins",
                             "Share of revenue", ".0%"), container=g1)
        ui.chart(ratio_lines(prof_df, ["Return on Assets (ROA)", "Return on Equity (ROE)",
                                       "Return on Invested Capital (ROIC)"], "Returns on capital",
                             "Ending balances", ".0%", [(0.15, "15% ROE benchmark", ui.POS)]), container=g2)

    with ratio_cat[2]:
        ui.callout_html(
            "<b>Debt-to-equity</b>: gearing; prudent <b>&lt; 1.0x–1.5x</b>. <b>Debt-to-assets</b>: share of assets "
            "financed by creditors; prudent <b>&lt; 0.5x</b>. <b>Interest coverage</b> (EBIT / interest): earnings "
            "buffer over interest; minimum safe <b>&gt; 3.0x</b> (warning below 1.5x).", "info", "Solvency")
        solv_df = target_analyzer.calculate_solvency_ratios()
        show_table(solv_df, CUR)
        g1, g2 = st.columns(2, gap="medium")
        fig = go.Figure()
        for i, r in enumerate(["Debt-to-Equity", "Debt-to-Assets"]):
            if r in solv_df.index:
                fig.add_bar(x=FY, y=num_row(solv_df, r), name=r, marker_color=[ui.ACCENT_2, ui.PALETTE[1]][i],
                            hovertemplate="%{y:.2f}x")
        fig.add_hline(y=1.5, line_dash="dash", line_color=ui.NEG, line_width=1.2, annotation_text="1.5x D/E ceiling",
                      annotation_font=dict(color=ui.NEG, size=11))
        ui.style_fig(fig, "Debt gearing", "Times equity / share of assets", height=420)
        fig.update_layout(barmode="group")
        ui.chart(fig, container=g1)
        icv = num_row(solv_df, "Interest Coverage")
        fig = go.Figure(go.Bar(x=FY, y=icv, marker_color=[ui.POS if (v or 0) >= 3 else (ui.WARN if (v or 0) >= 1.5
                                                                                           else ui.NEG) for v in icv],
                               text=[f"{v:.1f}x" if v is not None else "n/a" for v in icv], textposition="outside",
                               hovertemplate="%{y:.1f}x<extra></extra>"))
        fig.add_hline(y=3.0, line_dash="dash", line_color=ui.WARN, annotation_text="3.0x minimum",
                      annotation_font=dict(color=ui.WARN, size=11))
        ui.style_fig(fig, "Interest coverage", "EBIT / interest expense; green ≥ 3x, amber ≥ 1.5x, red below",
                     height=420, legend=False)
        ui.chart(fig, container=g2)

    with ratio_cat[3]:
        ui.callout_html(
            "<b>DSO</b> = AR / revenue × 365: days to collect from customers. <b>DIO</b> = inventory / COGS × 365: days "
            "inventory is held. <b>DPO</b> = AP / COGS × 365: days to pay suppliers. <b>CCC</b> = DIO + DSO − DPO: days "
            "cash is tied up; negative means suppliers finance the business (e.g. Apple). No inventory reported → DIO "
            "counts as 0. Year-end balances; rows marked “avg.” use the average of this and last year-end. 365-day year.",
            "info", "Working capital cycle")
        eff_df = target_analyzer.calculate_efficiency_ratios()
        show_table(eff_df, CUR)
        days = ["Days Sales Outstanding (DSO)", "Days Inventory Outstanding (DIO)", "Days Payable Outstanding (DPO)"]
        if any(r in eff_df.index for r in days):
            fig = go.Figure()
            for i, r in enumerate([r for r in days if r in eff_df.index]):
                sign = -1 if "DPO" in r else 1
                fig.add_bar(x=FY, y=[sign * v if v is not None else None for v in num_row(eff_df, r)],
                            name=r.split("(")[-1].rstrip(")") + (" (shown negative)" if sign < 0 else ""),
                            marker_color=[ui.ACCENT_2, ui.PALETTE[1], ui.PALETTE[2]][i], hovertemplate="%{y:.1f} days")
            if "Cash Conversion Cycle (CCC)" in eff_df.index:
                ccc = num_row(eff_df, "Cash Conversion Cycle (CCC)")
                fig.add_scatter(x=FY, y=ccc, name="Cash conversion cycle", mode="lines+markers+text",
                                line=dict(color=ui.INK, width=3), text=[f"{v:.0f}" if v is not None else "" for v in ccc],
                                textposition="top center", hovertemplate="%{y:.1f} days")
            fig.add_hline(y=0, line_color=ui.MUTED, line_width=1)
            ui.style_fig(fig, "Working-capital days and the cash conversion cycle",
                         "DSO + DIO − DPO = CCC; DPO drawn below zero because it shortens the cycle", height=440)
            fig.update_layout(barmode="relative")
            ui.chart(fig)

    with ratio_cat[4]:
        ui.callout_html(
            "<b>CFO / net income</b>: benchmark <b>&gt; 1.0x</b>; below 0.8x for several years can signal aggressive "
            "accruals or working-capital bloat. <b>Free cash flow</b> (CFO − capex): cash available to investors. "
            "<b>Sloan accrual ratio</b> ((NI − CFO) / total assets): values above 0.10 flag elevated restatement risk.",
            "info", "Earnings quality")
        cfq_df = target_analyzer.calculate_cash_flow_quality()
        show_table(cfq_df, CUR)
        fcfv = [v / 1e9 if v is not None else None for v in num_row(cfq_df, "Free Cash Flow")]
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(x=FY, y=fcfv, name="Free cash flow", marker_color=ui.bar_colors([v or 0 for v in fcfv]),
                    hovertemplate="%{y:,.2f}B")
        cfo_row = next((r for r in cfq_df.index if "Net Income" in r and "/" in r), None)
        if cfo_row:
            fig.add_scatter(x=FY, y=num_row(cfq_df, cfo_row), name="CFO / net income (rhs)", mode="lines+markers",
                            line=dict(color=ui.PALETTE[4], width=3), secondary_y=True, hovertemplate="%{y:.2f}x")
        ui.style_fig(fig, "Free cash flow and earnings quality", f"{CUR} billions; red = negative FCF", height=420)
        fig.update_yaxes(showgrid=False, secondary_y=True, tickformat=".1f")
        ui.chart(fig)

    with ratio_cat[5]:
        ui.callout("Year-on-year expansion in sales, operating profit, net income, EPS and free cash flow.", "info",
                   "Growth")
        growth_df = target_analyzer.calculate_growth_metrics()
        show_table(growth_df, CUR)
        gdf = growth_df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        if not gdf.empty:
            z = gdf.values.astype(float) * 100
            lim = float(np.nanpercentile(np.abs(z), 90)) if np.isfinite(z).any() else 10.0
            fig = go.Figure(go.Heatmap(z=z, x=[f"FY {c}" for c in gdf.columns], y=list(gdf.index),
                                       colorscale=ui.DIVERGING, zmid=0, zmin=-max(lim, 1), zmax=max(lim, 1),
                                       text=[[("n/a" if not np.isfinite(v) else f"{v:+.1f}%") for v in r] for r in z],
                                       texttemplate="%{text}", textfont=dict(size=13),
                                       colorbar=dict(ticksuffix="%", len=0.9),
                                       hovertemplate="%{y} · %{x}: %{z:+.1f}%<extra></extra>"))
            ui.style_fig(fig, "Growth heatmap", "Green = growth, red = decline", height=380, legend=False,
                         hovermode="closest")
            fig.update_yaxes(autorange="reversed", showgrid=False, showspikes=False, ticks="")
            fig.update_xaxes(showspikes=False, ticks="")
            ui.chart(fig)


# =====================================================================
# TAB 4: DUPONT ANALYSIS & SCORING MODELS
# =====================================================================
with tabs[3]:
    sub_model_tabs = st.tabs([
        "3-Step DuPont Analysis",
        "5-Step DuPont Analysis",
        "Altman Z-Score (Credit Risk)",
        "Piotroski F-Score (9 Factors)"
    ])
    dupont_dict = target_analyzer.calculate_dupont_analysis()

    def factor_grid(df, rows, fmts, title, subtitle):
        rows = [r for r in rows if r in df.index]
        fig = make_subplots(rows=1, cols=len(rows), subplot_titles=rows, horizontal_spacing=0.06)
        for i, r in enumerate(rows):
            vals = num_row(df, r)
            fig.add_bar(x=FY, y=vals, row=1, col=i + 1, name=r, showlegend=False,
                        marker_color=ui.PALETTE[i % len(ui.PALETTE)],
                        text=[format(v, fmts[i]) if v is not None else "n/a" for v in vals], textposition="outside",
                        textfont=dict(size=11), hovertemplate=f"{r}<br>%{{x}}: %{{y:{fmts[i]}}}<extra></extra>")
            fig.update_yaxes(tickformat=fmts[i], row=1, col=i + 1, showticklabels=False, showgrid=False)
        ui.style_fig(fig, title, subtitle, height=400, legend=False, hovermode="closest")
        fig.update_annotations(font=dict(size=12.5, color=ui.INK_2, family=ui.SANS))
        fig.update_xaxes(showspikes=False, tickfont=dict(size=10.5))
        return fig

    with sub_model_tabs[0]:
        ui.callout_html(
            "ROE = <b>net profit margin</b> × <b>asset turnover</b> × <b>financial leverage</b>, i.e. NI / equity = "
            "(NI / revenue) × (revenue / total assets) × (total assets / equity). Ending balances, so the product equals "
            "ROE exactly. Shows whether a high ROE comes from margin, efficiency or debt.", "info", "3-step DuPont")
        d3 = dupont_dict["three_step"]
        show_table(d3, CUR, row_styles={"3-Step DuPont ROE": "total", "Actual Reported ROE": "sub"})
        ui.chart(factor_grid(d3, ["Net Profit Margin", "Asset Turnover", "Financial Leverage", "3-Step DuPont ROE"],
                             [".1%", ".2f", ".2f", ".1%"], "DuPont drivers", "Margin × turnover × leverage = ROE"))

    with sub_model_tabs[1]:
        ui.callout_html(
            "ROE = <b>tax burden</b> × <b>interest burden</b> × <b>operating margin</b> × <b>asset turnover</b> × "
            "<b>financial leverage</b>, i.e. (NI / EBT) × (EBT / EBIT) × (EBIT / revenue) × (revenue / assets) × "
            "(assets / equity); EBIT = operating income.", "info", "5-step DuPont")
        d5 = dupont_dict["five_step"]
        show_table(d5, CUR)
        rows5 = [r for r in d5.index if "ROE" not in r][:5]
        if rows5:
            ui.chart(factor_grid(d5, rows5, [".1%" if "Margin" in r else ".2f" for r in rows5], "Extended DuPont factors",
                                 "Each factor over time; their product equals ROE"))

    with sub_model_tabs[2]:
        ui.callout_html(
            "<b>Z</b> = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 0.999·X5 &nbsp;|&nbsp; <b>Z''</b> = 6.56·X1 + 3.26·X2 + "
            "6.72·X3 + 1.05·X4''. X1 working capital / assets; X2 retained earnings / assets (buybacks can make it "
            "negative); X3 EBIT / assets; X4 market value of equity at fiscal year end / total liabilities (X4'' uses "
            "book equity); X5 sales / assets (not used in Z''). <b>Z zones:</b> safe &gt; 2.99, grey 1.81–2.99, "
            "distress &lt; 1.81. <b>Z'' zones:</b> safe &gt; 2.60, grey 1.10–2.60, distress &lt; 1.10.",
            "info", "Altman Z-Score credit-risk model")
        altman_df = target_analyzer.calculate_altman_z_score()
        g1, g2 = st.columns(2, gap="medium")
        z_scores = num_row(altman_df, "Altman Z-Score")
        z2 = num_row(altman_df, "Altman Z''-Score (Non-Mfg)")
        zmax = max([v for v in z_scores + z2 if v is not None] + [4.0]) * 1.15
        fig = go.Figure()
        for y0, y1, col, lab in ((2.99, zmax, ui.POS_BG, "Safe > 2.99"), (1.81, 2.99, ui.WARN_BG, "Grey 1.81–2.99"),
                                 (min(0, min([v for v in z_scores + z2 if v is not None] + [0])) - 0.5, 1.81, ui.NEG_BG,
                                  "Distress < 1.81")):
            fig.add_hrect(y0=y0, y1=y1, fillcolor=col, opacity=1, line_width=0, layer="below",
                          annotation_text=lab, annotation_position="top left",
                          annotation_font=dict(size=11, color=ui.INK_2))
        fig.add_scatter(x=FY, y=z_scores, name="Altman Z", mode="lines+markers+text",
                        line=dict(color=ui.ACCENT_2, width=3), marker=dict(size=9),
                        text=[f"{v:.2f}" if v is not None else "" for v in z_scores], textposition="top center",
                        hovertemplate="%{y:.2f}")
        fig.add_scatter(x=FY, y=z2, name="Altman Z'' (non-manufacturing)", mode="lines+markers",
                        line=dict(color=ui.PALETTE[2], width=2.5, dash="dot"), hovertemplate="%{y:.2f}")
        ui.style_fig(fig, "Altman Z-Score trajectory", "Bands use the original Z thresholds", height=440)
        fig.update_yaxes(range=[None, zmax])
        ui.chart(fig, container=g1)

        xs = ["X1 (Working Capital / Assets)", "X2 (Retained Earnings / Assets)", "X3 (EBIT / Assets)",
              "X4 (Market Value of Equity / Liabilities)", "X5 (Revenue / Assets)"]
        coefs = [1.2, 1.4, 3.3, 0.6, 0.999]
        vals = [_safe_float(altman_df.loc[x, latest_y]) if x in altman_df.index else None for x in xs]
        if all(v is not None for v in vals):
            contrib = [c * v for c, v in zip(coefs, vals)]
            labels = [f"{x.split(' ')[0]} · {c:g}×" for x, c in zip(xs, coefs)]
            fig = go.Figure(go.Waterfall(
                x=labels + ["Z-Score"], y=contrib + [0], measure=["relative"] * 5 + ["total"],
                text=[f"{v:+.2f}" for v in contrib] + [f"{sum(contrib):.2f}"], textposition="outside",
                customdata=[x.split("(")[1].rstrip(")") for x in xs] + ["Total"],
                hovertemplate="%{customdata}: %{y:+.2f}<extra></extra>"))
            ui.style_fig(fig, f"Z-Score build-up, FY {latest_y}", "Coefficient × ratio for each of the five factors",
                         height=440, legend=False, hovermode="closest")
            ui.chart(fig, container=g2)
        else:
            with g2:
                ui.callout("The Z-Score build-up needs all five factors; at least one is not reported.", "warn")
        ui.subhead("Altman inputs and scores", "Fiscal-year values")
        show_table(altman_df, CUR, row_styles={"Altman Z-Score": "total", "Altman Z''-Score (Non-Mfg)": "sub"})
        st.caption(FinancialAnalyzer.ALTMAN_NOTE)

    with sub_model_tabs[3]:
        ui.callout_html(
            "Nine yes/no signals (Piotroski 2000) comparing year t with year t−1: profitability (1–4), leverage / "
            "liquidity / equity issuance (5–7) and efficiency (8–9). ROA and asset turnover use beginning-of-year assets, "
            "so the first one or two years cannot be fully scored (shown as n/a). <b>Interpretation:</b> 8–9 strong, "
            "5–7 moderate, 0–4 weak.", "info", "Piotroski F-Score")
        det = piotroski["detailed"]
        sig = [r for r in det.index if r[:2].rstrip(".").isdigit()]
        g1, g2 = st.columns([3, 2], gap="medium")
        if sig:
            z = [[(np.nan if _safe_float(det.loc[r, y]) is None else float(det.loc[r, y])) for y in years] for r in sig]
            txt = [["n/a" if np.isnan(v) else ("Pass" if v >= 1 else "Fail") for v in row] for row in z]
            short = [r if len(r) <= 46 else r[:44] + "…" for r in sig]
            fig = go.Figure(go.Heatmap(
                z=z, x=FY, y=short, zmin=0, zmax=1, xgap=3, ygap=3,
                colorscale=[[0, ui.rgba(ui.NEG, 0.88)], [0.5, ui.rgba(ui.NEG, 0.88)], [0.5, ui.rgba(ui.POS, 0.88)],
                            [1, ui.rgba(ui.POS, 0.88)]],
                showscale=False, text=txt, texttemplate="%{text}", customdata=[[r] * len(years) for r in sig],
                textfont=dict(size=12.5, color="white"), hovertemplate="%{customdata}<br>%{x}: %{text}<extra></extra>"))
            ui.style_fig(fig, "Nine signals by year", "Green = pass, red = fail, blank = not measurable", height=460,
                         legend=False, hovermode="closest")
            fig.update_yaxes(autorange="reversed", showgrid=False, showspikes=False, ticks="", tickfont=dict(size=11.5))
            fig.update_xaxes(showspikes=False, side="top", ticks="")
            fig.update_layout(margin=dict(l=16, r=24, t=96, b=24))
            ui.chart(fig, container=g1)
        sc = [piotroski["scores"].get(y) for y in years]
        fig = go.Figure(go.Bar(
            x=FY, y=[v if v is not None else 0 for v in sc],
            marker_color=[ui.MUTED if v is None else ui.POS if v >= 7 else (ui.NEG if v <= 3 else ui.WARN) for v in sc],
            text=[f"{v} / 9" if v is not None else "n/a" for v in sc], textposition="outside",
            hovertemplate="%{x}: %{text}<extra></extra>"))
        fig.add_hrect(y0=7, y1=9.6, fillcolor=ui.POS_BG, opacity=0.6, line_width=0, layer="below",
                      annotation_text="Strong", annotation_position="top left", annotation_font=dict(size=11, color=ui.POS))
        ui.style_fig(fig, "Total F-Score", "Out of 9; years with fewer than 9 measurable signals show n/a", height=460,
                     legend=False, hovermode="closest")
        fig.update_yaxes(range=[0, 9.6], dtick=3)
        ui.chart(fig, container=g2)
        ui.subhead("Signal detail", "1 = pass, 0 = fail")
        show_table(det, CUR, row_styles={"Total Piotroski F-Score": "total"})


# =====================================================================
# TAB 5: PEER COMPARISON VIEW
# =====================================================================
with tabs[4]:
    if len(loaded_data_dict) < 2:
        ui.callout("To compare peers, enter two or more comma-separated tickers in the sidebar (e.g. AAPL, MSFT, GOOGL "
                   "or KO, PEP).", "info", "Peer comparison")
    else:
        peer_records = []
        for sym, d_obj in loaded_data_dict.items():
            an = loaded_analyzers[sym]
            y_last = d_obj.years[-1] if d_obj.years else ""
            p_prof = an.calculate_profitability_ratios()
            p_liq = an.calculate_liquidity_ratios()
            p_solv = an.calculate_solvency_ratios()
            p_cfq = an.calculate_cash_flow_quality()
            p_alt = an.calculate_altman_z_score()
            p_f = an.calculate_piotroski_f_score()
            p_rep = an.generate_health_report()
            rev = d_obj.get_raw_value("income", "revenue", y_last)
            ni = d_obj.get_raw_value("income", "net_income", y_last)
            peer_records.append({
                "Ticker": sym,
                "Company": d_obj.company_name,
                "Latest FY": y_last,
                "Revenue (B)": rev / 1e9 if rev is not None else None,
                "Net Income (B)": ni / 1e9 if ni is not None else None,
                "Operating Margin": _safe_float(p_prof.loc["Operating Margin", y_last]),
                "Net Margin": _safe_float(p_prof.loc["Net Profit Margin", y_last]),
                "ROE": _safe_float(p_prof.loc["Return on Equity (ROE)", y_last]),
                "ROIC": _safe_float(p_prof.loc["Return on Invested Capital (ROIC)", y_last]),
                "Current Ratio": _safe_float(p_liq.loc["Current Ratio", y_last]),
                "Debt-to-Equity": _safe_float(p_solv.loc["Debt-to-Equity", y_last]),
                "FCF Margin": _safe_float(p_cfq.loc["FCF Margin", y_last]),
                "Altman Z": _safe_float(p_alt.loc["Altman Z-Score", y_last]),
                "Piotroski F": p_f["scores"].get(y_last),
                "Status": p_rep["overall_status"],
            })
        peer_summary_df = pd.DataFrame(peer_records)

        def _p(v):
            return "n/a" if v is None or pd.isna(v) else ui.pct(v)

        n_peer = len(peer_records)
        ui.kpis([dict(label=f"{r['Ticker']} · {r['Company'].split(' [')[0]}",
                      value=f"{r['Revenue (B)']:,.1f}B" if r["Revenue (B)"] is not None else "n/a",
                      delta=f"op. margin {_p(r['Operating Margin'])}",
                      tone="pos" if (r["Operating Margin"] or 0) > 0 else "neg", arrow=False,
                      note=f"FY {r['Latest FY']} revenue · {r['Status']}", accent=ui.PALETTE[i % len(ui.PALETTE)])
                 for i, r in enumerate(peer_records)], cols=min(max(n_peer, 2), 5))
        ui.spacer(16)

        g1, g2 = st.columns(2, gap="medium")
        radar_categories = ["Profitability (ROE)", "Operating Margin", "Liquidity (Current Ratio)",
                            "Cash Flow (FCF Margin)", "Credit Safety (Piotroski)"]
        fig_radar = go.Figure()
        for idx, row in peer_summary_df.iterrows():
            def _n(v, top):
                f = _safe_float(v)
                return None if f is None else min(1.0, max(0.0, f / top))
            r_vals = [_n(row["ROE"], 0.40), _n(row["Operating Margin"], 0.40), _n(row["Current Ratio"], 3.0),
                      _n(row["FCF Margin"], 0.35), _n(row["Piotroski F"], 9.0)]
            r_vals.append(r_vals[0])
            col = ui.PALETTE[idx % len(ui.PALETTE)]
            fig_radar.add_trace(go.Scatterpolar(
                r=r_vals, theta=radar_categories + [radar_categories[0]], fill="toself", name=row["Ticker"],
                line=dict(color=col, width=2.5), fillcolor=ui.rgba(col, 0.14), marker=dict(size=7),
                hovertemplate=f"{row['Ticker']} · %{{theta}}: %{{r:.2f}}<extra></extra>"))
        ui.style_fig(fig_radar, "Financial strength radar", "Each axis scaled 0–1 against a reference ceiling",
                     height=480, hovermode="closest")
        fig_radar.update_layout(polar=dict(
            bgcolor="white", radialaxis=dict(visible=True, range=[0, 1], gridcolor=ui.GRID, tickfont=dict(size=10,
                                                                                                         color=ui.MUTED),
                                             linecolor=ui.HAIRLINE, angle=36, tickangle=36,
                                             tickvals=[0.25, 0.5, 0.75, 1.0]),
            angularaxis=dict(gridcolor=ui.GRID, linecolor=ui.HAIRLINE, tickfont=dict(size=12, color=ui.INK_2))))
        ui.chart(fig_radar, container=g1)

        metrics = ["Operating Margin", "Net Margin", "ROE", "ROIC", "FCF Margin"]
        fig_bar = go.Figure()
        for i, row in peer_summary_df.iterrows():
            vals = [_safe_float(row[m]) for m in metrics]
            fig_bar.add_bar(x=metrics, y=vals, name=row["Ticker"], marker_color=ui.PALETTE[i % len(ui.PALETTE)],
                            hovertemplate=f"{row['Ticker']}: %{{y:.1%}}<extra></extra>")
        ui.style_fig(fig_bar, "Margins and returns side by side", "Latest fiscal year", height=480,
                     hovermode="closest")
        fig_bar.update_layout(barmode="group", bargap=0.25)
        fig_bar.update_yaxes(tickformat=".0%")
        ui.chart(fig_bar, container=g2)

        ui.section("Peer summary", "Latest fiscal year for each company; USD billions unless stated.")
        peer_tbl = peer_summary_df.set_index("Ticker").drop(columns=["Company"])
        fm = {"Revenue (B)": lambda v: f"{v:,.1f}B", "Net Income (B)": lambda v: f"{v:,.1f}B",
              "Current Ratio": lambda v: f"{v:.2f}x", "Debt-to-Equity": lambda v: f"{v:.2f}x",
              "Altman Z": lambda v: f"{v:.2f}", "Piotroski F": lambda v: f"{v:.0f}/9"}
        for m in ["Operating Margin", "Net Margin", "ROE", "ROIC", "FCF Margin"]:
            fm[m] = lambda v: f"{v * 100:.1f}%"
        show_tbl = pd.DataFrame({c: [("n/a" if (v is None or (isinstance(v, float) and pd.isna(v)))
                                      else fm[c](v) if c in fm else str(v)) for v in peer_tbl[c]]
                                 for c in peer_tbl.columns}, index=peer_tbl.index).T
        ui.html_table(show_tbl, fmt="plain", index_label="Metric")


# =====================================================================
# TAB 6: EXPORT CENTER (EXCEL, PDF, MARKDOWN)
# =====================================================================
with tabs[5]:
    ui.section("Export Center", "Download the analysis as an Excel model (live formulas), a PDF health report or a "
               "Markdown summary.")
    exp_col1, exp_col2, exp_col3 = st.columns(3, gap="medium")
    with exp_col1:
        ui.card("Formatted Excel model", "<p>" + "Multi-tab workbook where every ratio is a live Excel formula referencing "
                "the statement tabs." + "</p>")
        if st.button("Generate Live Formula Excel (.xlsx)", width="stretch", type="primary"):
            with st.spinner("Compiling openpyxl workbook with dynamic formulas..."):
                excel_bytes = export_analysis_to_excel(target_analyzer)
                st.download_button(label="Download Excel Model", data=excel_bytes,
                                   file_name=f"{target_data.symbol}_financial_model.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   width="stretch", type="primary")
                st.success("Formatted Excel workbook compiled with live formulas.")
    with exp_col2:
        ui.card("PDF health report", "<p>" + "Printable report with header, status badges, diagnostic findings and "
                "formatted tables." + "</p>")
        if st.button("Generate Executive PDF Report", width="stretch"):
            with st.spinner("Rendering ReportLab PDF document..."):
                pdf_bytes = generate_pdf_report(target_analyzer)
                st.download_button(label="Download PDF Report", data=pdf_bytes,
                                   file_name=f"{target_data.symbol}_financial_health_report.pdf",
                                   mime="application/pdf", width="stretch")
                st.success("PDF report successfully rendered.")
    with exp_col3:
        ui.card("Markdown summary", "<p>" + "Full diagnostic report in GitHub-flavoured Markdown for documentation and "
                "quick sharing." + "</p>")
        if st.button("Generate Markdown Report (.md)", width="stretch"):
            md_text = generate_markdown_report(target_analyzer)
            st.download_button(label="Download Markdown File", data=md_text.encode("utf-8"),
                               file_name=f"{target_data.symbol}_analysis_report.md", mime="text/markdown",
                               width="stretch")
            st.success("Markdown report generated.")
    ui.spacer(16)
    with st.expander("Live preview of the Markdown report"):
        st.markdown(generate_markdown_report(target_analyzer))

ui.footer("Ratios are computed from reported annual statements (yfinance or the bundled offline snapshot). "
          "Rule-based ratings are educational, not investment advice.")
