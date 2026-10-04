"""
Loan Amortization & Investment Growth Calculator (Streamlit)
============================================================
Loan schedules with extra payments, investment growth with contributions,
NPV / IRR / APR-EAR tools, and Excel exports where every cell is a live formula.
All maths lives in finance_calc.py; the Excel builders are in excel_export.py.
The look (fonts, colours, KPI cards, tables, Plotly template) comes from ui_theme.py,
a vendored copy of the portfolio's shared design system (finance/_shared/).
"""

from datetime import date
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui_theme as ui
from finance_calc import (
    SUPPORTED_FREQUENCIES,
    periodic_rate,
    compute_amortization_schedule,
    compute_investment_growth,
    goal_seek_contribution,
    goal_seek_return,
    analyze_cash_flows,
    compare_apr_ear_frequencies,
    compare_two_loans,
    apr_to_ear,
    pmt
)
from excel_export import build_investment_workbook, build_loan_workbook, export_workbook_to_bytes

ui.apply("Loan & Investment Calculator · Yamen Agha", icon=":material/account_balance:", sidebar="collapsed")


# =============================================================================
# HELPER FORMATTING FUNCTIONS
# =============================================================================

def fmt_curr(val: float) -> str:
    return f"${val:,.2f}"

def fmt_pct(val: float) -> str:
    return f"{val * 100:.2f}%"

def fmt_num(val: float) -> str:
    return f"{val:,.0f}"


def money0(v: float) -> str:
    return ui.money(v, dp=0)


INTEREST_C = ui.PALETTE[2]     # interest = cost of borrowing (warm orange)
PRINCIPAL_C = ui.ACCENT_2      # principal = equity built (oxford blue)
EXTRA_C = ui.POS               # extra principal (green)

# =============================================================================
# HEADER
# =============================================================================

ui.masthead(
    "Loan & Investment Calculator",
    "Amortization schedules, extra payments, compound growth, NPV / IRR and APR vs EAR, with Excel exports "
    "where every cell is a live formula.",
    kicker="Time value of money",
    meta={"Engine": "finance_calc.py", "Exports": "live-formula Excel + CSV",
          "Checked against": "LibreOffice Calc"},
)

tab_loan, tab_investment, tab_tools = st.tabs([
    "Loan Amortization & Payoff Accelerator",
    "Investment Growth & Wealth Accumulation",
    "Financial Decision Tools (NPV / IRR / Compare)"
])


# =============================================================================
# TAB 1: LOAN AMORTIZATION MODE
# =============================================================================

with tab_loan:
    col_in_main, col_in_extra = st.columns(2, gap="medium")

    with col_in_main.container(border=True):
        ui.subhead("Loan structure & core terms", "Principal, rate, term and repayment profile")
        c_p, c_r = st.columns(2)
        l_principal = c_p.number_input(
            "Principal Loan Amount ($)",
            min_value=1000.0,
            max_value=100_000_000.0,
            value=200_000.0,
            step=5_000.0,
            format="%.2f",
            key="l_principal"
        )
        l_rate = c_r.number_input(
            "Annual Interest Rate (%)",
            min_value=0.0,
            max_value=40.0,
            value=6.00,
            step=0.125,
            format="%.3f",
            key="l_rate"
        ) / 100.0

        c_term, c_freq = st.columns(2)
        with c_term:
            l_term = st.number_input(
                "Term (Years)",
                min_value=0.5,
                max_value=50.0,
                value=30.0,
                step=1.0,
                key="l_term"
            )
        with c_freq:
            freq_map = {"Monthly (12/yr)": 12, "Bi-Weekly (26/yr)": 26, "Weekly (52/yr)": 52, "Quarterly (4/yr)": 4,
                        "Semi-Annual (2/yr)": 2, "Annual (1/yr)": 1}
            l_freq_label = st.selectbox(
                "Payment Frequency",
                options=list(freq_map.keys()),
                index=0,
                key="l_freq"
            )
            l_freq = freq_map[l_freq_label]

        c_date, c_type = st.columns(2)
        with c_date:
            l_start_date = st.date_input("First Payment Date", value=date(2026, 11, 1), key="l_start_date",
                                         help="Date of payment #1. Monthly dates keep the same day of the month "
                                              "(31st -> last day of shorter months).")
        with c_type:
            loan_type_map = {
                "Fixed Payment (Standard Annuity)": "fixed_payment",
                "Equal Principal Amortization": "equal_principal",
                "Interest-Only then Balloon": "interest_only"
            }
            l_type_label = st.selectbox(
                "Loan Type",
                options=list(loan_type_map.keys()),
                index=0,
                key="l_type"
            )
            l_type = loan_type_map[l_type_label]

        c_comp, c_balloon = st.columns(2)
        with c_comp:
            comp_opts = {"Same as payments (standard)": None, "Semi-annual (Canadian mortgages)": 2,
                         "Monthly": 12, "Annual": 1, "Daily (365)": 365}
            l_comp_label = st.selectbox("Interest Compounding", options=list(comp_opts.keys()), index=0, key="l_comp",
                                        help="If compounding differs from the payment frequency, the app uses the "
                                             "equivalent periodic rate (1 + APR/m)^(m/p) - 1.")
            l_comp = comp_opts[l_comp_label]
        with c_balloon:
            l_balloon = st.number_input(
                "Balloon at Maturity ($)", min_value=0.0, max_value=float(l_principal) - 1.0, value=0.0, step=5_000.0,
                key="l_balloon", disabled=(l_type != "fixed_payment"),
                help="Fixed-payment loans only: the payment is set so this amount is still owed and paid with "
                     "the last payment. Interest-only loans always end with the whole principal as the balloon.")
            if l_type != "fixed_payment":
                l_balloon = 0.0
        l_periodic = periodic_rate(l_rate, l_comp if l_comp is not None else l_freq, l_freq)
        st.caption(f"Periodic rate used: **{l_periodic*100:.5f}%** per payment "
                   f"({'APR / payments per year' if l_comp in (None, l_freq) else 'equivalent rate (1 + APR/m)^(m/p) - 1'}).")

    with col_in_extra.container(border=True):
        ui.subhead("Extra payments & payoff acceleration",
                   "Recurring extra principal and one-off lump sums shorten the loan")
        c_x, c_s = st.columns(2)
        l_extra_recurring = c_x.number_input(
            "Recurring Extra Principal per Period ($)",
            min_value=0.0,
            max_value=500_000.0,
            value=200.0,
            step=50.0,
            format="%.2f",
            key="l_extra_recurring"
        )
        l_extra_start_period = c_s.number_input(
            "Begin Recurring Extra at Period #",
            min_value=1,
            max_value=int(round(l_term * l_freq)),
            value=1,
            step=1,
            key="l_extra_start"
        )

        n_max = max(1, int(round(l_term * l_freq)))
        st.markdown('<div class="ya-subhead-n" style="margin-top:4px">Lump-sum prepayments (up to 3), paid together '
                    'with the regular payment of that number</div>', unsafe_allow_html=True)
        lump_sums = {}
        for j, (default_p, col_l) in enumerate(zip((12, 36, 60), st.columns(3)), start=1):
            with col_l:
                ls_p = st.number_input(f"Payment # (lump sum {j})", min_value=1, max_value=n_max,
                                       value=min(default_p, n_max), key=f"ls_p{j}")
                ls_a = st.number_input(f"Amount ($) (lump sum {j})", min_value=0.0, value=0.0, step=1000.0, key=f"ls_a{j}")
            if ls_a > 0:
                lump_sums[int(ls_p)] = lump_sums.get(int(ls_p), 0.0) + ls_a

    # Execute Loan Amortization Calculation
    try:
        loan_result = compute_amortization_schedule(
            principal=l_principal,
            annual_interest_rate=l_rate,
            term_years=l_term,
            payment_frequency=l_freq,
            start_date=l_start_date,
            loan_type=l_type,
            recurring_extra_payment=l_extra_recurring,
            recurring_extra_start_period=l_extra_start_period,
            lump_sum_extras=lump_sums,
            balloon_amount=l_balloon,
            compounding_frequency=l_comp,
        )
        summary = loan_result.summary
        df_sched = loan_result.schedule
        df_base = loan_result.baseline_schedule
    except Exception as e:
        st.error(f"Error computing loan schedule: {e}")
        st.stop()

    ui.section("Key results", f"{l_type_label} · {l_freq_label.split(' (')[0].lower()} payments · "
               f"{l_term:g} years", kicker="Loan")

    pay_note = {"fixed_payment": "Regular " + l_freq_label.split()[0].lower() + " payment",
                "equal_principal": "First payment (falls each period)",
                "interest_only": "Interest only; balloon " + fmt_curr(summary.final_payment)}[l_type]
    saved_share = summary.interest_saved / summary.baseline_total_interest if summary.baseline_total_interest > 0 else 0
    ui.kpis([
        dict(label="Scheduled payment", value=fmt_curr(summary.scheduled_payment), note=pay_note, tone="accent",
             accent=ui.ACCENT),
        dict(label="Total interest paid", value=fmt_curr(summary.total_interest_paid),
             delta=f"baseline {money0(summary.baseline_total_interest)}", tone="warn", arrow=False,
             accent=INTEREST_C),
        dict(label="Total cash outflow", value=fmt_curr(summary.total_amount_paid),
             note=f"Principal + interest + extras ({summary.actual_payments_count} payments)", accent=PRINCIPAL_C),
        dict(label="Interest saved", value=fmt_curr(summary.interest_saved),
             delta=f"{fmt_pct(saved_share)} saved" if summary.interest_saved > 0 else "no extra payments",
             tone="pos" if summary.interest_saved > 0 else "neutral", arrow=False),
        dict(label="Payoff date", value=summary.payoff_date.strftime('%b %Y'),
             delta=f"orig. {summary.original_payoff_date.strftime('%b %Y')}",
             tone="pos" if summary.periods_saved > 0 else "neutral", arrow=False),
    ], cols=5)

    # Callout for savings (plain text, so the figures are searchable in tests and screen readers)
    if summary.interest_saved > 0 or summary.periods_saved > 0:
        months_saved = int(round(summary.periods_saved * 12 / l_freq))
        yrs, mos = divmod(months_saved, 12)
        time_saved_str = f"{yrs} years, {mos} months" if yrs > 0 else f"{mos} months"
        ui.callout(f"Adding extra payments saves {fmt_curr(summary.interest_saved)} in interest and pays off the loan "
                   f"{time_saved_str} earlier (payoff date: {summary.payoff_date.strftime('%B %d, %Y')}).",
                   "pos", "Acceleration impact")

    ui.section("Amortization dynamics", "Hover for exact values; drag to zoom, double-click to reset; click legend "
               "items to hide a series.")
    col_ch1, col_ch2 = st.columns(2, gap="medium")

    fig_bal = go.Figure()
    fig_bal.add_trace(go.Scatter(
        x=df_base["date"], y=df_base["ending_balance"], mode="lines", name="Baseline (no extra)",
        line=dict(color=ui.MUTED, width=2, dash="dash"), hovertemplate="$%{y:,.0f}"))
    fig_bal.add_trace(go.Scatter(
        x=df_sched["date"], y=df_sched["ending_balance"], mode="lines", name="With extra payments",
        fill="tozeroy", fillcolor=ui.rgba(ui.ACCENT_2, 0.12), line=dict(color=ui.ACCENT_2, width=3),
        hovertemplate="$%{y:,.0f}"))
    if summary.periods_saved > 0:
        fig_bal.add_vline(x=pd.Timestamp(summary.payoff_date).timestamp() * 1000, line_dash="dot",
                          line_color=ui.POS, line_width=1.5)
        fig_bal.add_annotation(x=pd.Timestamp(summary.payoff_date), y=summary.original_principal * 0.92,
                               text=f"Paid off {summary.payoff_date.strftime('%b %Y')}", showarrow=False,
                               xanchor="left", xshift=6, font=dict(color=ui.POS, size=12))
    ui.style_fig(fig_bal, "Remaining balance", "Baseline schedule vs accelerated payoff", height=440)
    fig_bal.update_layout(hovermode="x unified")
    fig_bal.update_yaxes(tickformat="$~s")
    ui.chart(fig_bal, container=col_ch1)

    fig_split = go.Figure()
    fig_split.add_trace(go.Scatter(x=df_sched["date"], y=df_sched["interest"], name="Interest", mode="lines",
                                   stackgroup="pay", fillcolor=ui.rgba(INTEREST_C, 0.75), line_color=INTEREST_C,
                                   hovertemplate="$%{y:,.2f}"))
    fig_split.add_trace(go.Scatter(x=df_sched["date"], y=df_sched["principal"], name="Principal", mode="lines",
                                   stackgroup="pay", fillcolor=ui.rgba(PRINCIPAL_C, 0.75), line_color=PRINCIPAL_C,
                                   hovertemplate="$%{y:,.2f}"))
    if df_sched["extra_payment"].sum() > 0:
        fig_split.add_trace(go.Scatter(x=df_sched["date"], y=df_sched["extra_payment"], name="Extra principal",
                                       fillcolor=ui.rgba(EXTRA_C, 0.7), line_color=EXTRA_C,
                                       hovertemplate="$%{y:,.2f}", mode="lines", stackgroup="pay"))
    ui.style_fig(fig_split, "Payment composition", "Interest vs principal in every payment (stacked)", height=440)
    fig_split.update_yaxes(tickformat="$,.0f")
    ui.chart(fig_split, container=col_ch2)

    col_ch3, col_ch4 = st.columns(2, gap="medium")
    fig_cum = go.Figure()
    fig_cum.add_trace(go.Scatter(x=df_sched["date"], y=df_sched["cumulative_principal"], name="Cumulative principal",
                                 mode="lines", stackgroup="cum", fillcolor=ui.rgba(PRINCIPAL_C, 0.55),
                                 line=dict(color=PRINCIPAL_C, width=1.5), hovertemplate="$%{y:,.0f}"))
    fig_cum.add_trace(go.Scatter(x=df_sched["date"], y=df_sched["cumulative_interest"], name="Cumulative interest",
                                 mode="lines", stackgroup="cum", fillcolor=ui.rgba(INTEREST_C, 0.55),
                                 line=dict(color=INTEREST_C, width=1.5), hovertemplate="$%{y:,.0f}"))
    ui.style_fig(fig_cum, "Cumulative cash paid", "Stacked: principal repaid (incl. extras) plus interest paid to date", height=420)
    fig_cum.update_yaxes(tickformat="$~s")
    ui.chart(fig_cum, container=col_ch3)

    yr = df_sched.assign(year=pd.to_datetime(df_sched["date"]).dt.year).groupby("year")[
        ["interest", "principal", "extra_payment"]].sum()
    fig_yr = go.Figure()
    fig_yr.add_bar(x=yr.index, y=yr["interest"], name="Interest", marker_color=INTEREST_C,
                   hovertemplate="$%{y:,.0f}")
    fig_yr.add_bar(x=yr.index, y=yr["principal"], name="Principal", marker_color=PRINCIPAL_C,
                   hovertemplate="$%{y:,.0f}")
    if yr["extra_payment"].sum() > 0:
        fig_yr.add_bar(x=yr.index, y=yr["extra_payment"], name="Extra principal", marker_color=EXTRA_C,
                       hovertemplate="$%{y:,.0f}")
    ui.style_fig(fig_yr, "Calendar-year totals", "Interest, scheduled principal and extra principal paid each year",
                 height=420)
    fig_yr.update_layout(barmode="stack", bargap=0.18)
    fig_yr.update_yaxes(tickformat="$~s")
    ui.chart(fig_yr, container=col_ch4)

    ui.section("Full amortization schedule", f"{len(df_sched)} payments; sticky header, scroll inside the table.",
               kicker="Schedule")
    col_exp1, col_exp2, _sp = st.columns(3)
    with col_exp1:
        wb_live, _ = build_loan_workbook(
            principal=l_principal,
            annual_interest_rate=l_rate,
            term_years=l_term,
            payment_frequency=l_freq,
            start_date=l_start_date,
            loan_type=l_type,
            balloon_amount=l_balloon,
            recurring_extra=l_extra_recurring,
            recurring_extra_start_period=int(l_extra_start_period),
            lump_sum_extras=lump_sums,
            compounding_frequency=l_comp,
        )
        excel_bytes = export_workbook_to_bytes(wb_live)
        st.download_button(
            label="Download live Excel model (.xlsx)",
            data=excel_bytes,
            file_name=f"Amortization_Model_{l_principal:.0f}_{l_term:.0f}yr.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Generates an Excel workbook where the schedule cells are LIVE formulas linked to the inputs section!",
            type="primary", width="stretch", icon=":material/download:",
        )
    with col_exp2:
        csv_bytes = df_sched.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download schedule (CSV)",
            data=csv_bytes,
            file_name="loan_amortization_schedule.csv",
            mime="text/csv", width="stretch",
        )

    display_df = df_sched.drop(columns=["cumulative_interest", "cumulative_principal"]).copy()
    display_df["date"] = display_df["date"].apply(lambda d: d.strftime("%Y-%m-%d"))
    display_df = display_df.set_index("period")
    display_df.columns = ["Payment date", "Beginning balance", "Scheduled payment", "Principal", "Interest",
                          "Extra payment", "Total payment", "Ending balance"]
    ui.html_table(display_df, fmt="acct2", index_label="Period", max_height=520)


# =============================================================================
# TAB 2: INVESTMENT GROWTH & WEALTH ACCUMULATION MODE
# =============================================================================

with tab_investment:
    col_inv_left, col_inv_right = st.columns(2, gap="medium")

    with col_inv_left.container(border=True):
        ui.subhead("Capital & contributions", "What goes in, how often, and how it grows over time")
        inv_initial = st.number_input(
            "Initial Investment Capital ($)",
            min_value=0.0,
            max_value=100_000_000.0,
            value=10_000.0,
            step=2_500.0,
            key="inv_initial"
        )
        c_rc, c_rf = st.columns(2)
        with c_rc:
            inv_contrib = st.number_input(
                "Regular Contribution ($)",
                min_value=0.0,
                max_value=500_000.0,
                value=500.0,
                step=100.0,
                key="inv_contrib"
            )
        with c_rf:
            contrib_freq_map = {"Monthly (12/yr)": 12, "Bi-Weekly (26/yr)": 26, "Weekly (52/yr)": 52,
                                "Quarterly (4/yr)": 4, "Semi-Annual (2/yr)": 2, "Annually (1/yr)": 1}
            inv_freq_lbl = st.selectbox(
                "Contribution Frequency",
                options=list(contrib_freq_map.keys()),
                index=0,
                key="inv_freq"
            )
            inv_freq = contrib_freq_map[inv_freq_lbl]

        c_time, c_step = st.columns(2)
        with c_time:
            timing_map = {"End of Period (Ordinary Annuity)": "end", "Beginning of Period (Annuity Due)": "beginning"}
            inv_timing_lbl = st.selectbox("Contribution Timing", options=list(timing_map.keys()), index=0, key="inv_timing")
            inv_timing = timing_map[inv_timing_lbl]
        with c_step:
            inv_stepup = st.number_input(
                "Annual Contribution Increase (%)",
                min_value=-10.0,
                max_value=25.0,
                value=0.0,
                step=0.5,
                help="Steps up regular contribution each year (e.g. to match salary growth)",
                key="inv_stepup"
            ) / 100.0

    with col_inv_right.container(border=True):
        ui.subhead("Return, compounding & economic factors", "Nominal return, horizon, inflation and tax drag")
        c_ret, c_comp = st.columns(2)
        with c_ret:
            inv_return = st.number_input(
                "Expected Annual Return (%)",
                min_value=-20.0,
                max_value=100.0,
                value=7.0,
                step=0.5,
                key="inv_return"
            ) / 100.0
        with c_comp:
            comp_freq_map = {
                "Monthly (12/yr)": 12,
                "Quarterly (4/yr)": 4,
                "Semi-Annually (2/yr)": 2,
                "Annually (1/yr)": 1,
                "Daily (365/yr)": 365,
                "Continuous Compounding": -1
            }
            inv_comp_lbl = st.selectbox("Compounding Frequency", options=list(comp_freq_map.keys()), index=0, key="inv_comp")
            inv_comp = comp_freq_map[inv_comp_lbl]

        c_yrs, c_inf = st.columns(2)
        with c_yrs:
            inv_years = st.number_input("Investment Horizon (Years)", min_value=1.0, max_value=60.0, value=20.0, step=1.0, key="inv_years")
        with c_inf:
            inv_inflation = st.number_input(
                "Expected Inflation Rate (%)",
                min_value=0.0,
                max_value=20.0,
                value=2.5,
                step=0.25,
                key="inv_inflation"
            ) / 100.0

        inv_tax = st.number_input(
            "Tax Rate on Investment Gains (%)",
            min_value=0.0,
            max_value=50.0,
            value=0.0,
            step=1.0,
            help="Assumption: gains are taxed as they accrue each period (like interest in a taxable account) "
                 "and the tax is paid from the account. Losses get no refund. This is a 'tax drag' model, not "
                 "capital-gains tax on sale.",
            key="inv_tax"
        ) / 100.0

    st.caption(
        f"Return is a nominal annual rate compounded {inv_comp_lbl.split(' (')[0].lower()}. Rate used per contribution "
        f"period: **{periodic_rate(inv_return, inv_comp, inv_freq)*100:.5f}%** = (1 + R/m)^(m/p) - 1, the equivalent "
        "periodic rate, so the effective annual return is the same whatever the contribution frequency."
    )

    try:
        inv_result = compute_investment_growth(
            initial_amount=inv_initial,
            regular_contribution=inv_contrib,
            contribution_frequency=inv_freq,
            contribution_timing=inv_timing,
            annual_return=inv_return,
            compounding_frequency=inv_comp,
            years=inv_years,
            annual_contribution_increase_pct=inv_stepup,
            inflation_rate=inv_inflation,
            tax_rate_on_gains=inv_tax
        )
        inv_summary = inv_result.summary
        df_inv_annual = inv_result.annual_schedule
        df_inv_period = inv_result.period_schedule
    except Exception as e:
        st.error(f"Error computing investment model: {e}")
        st.stop()

    ui.section("Key results", f"{inv_years:g}-year horizon · {fmt_pct(inv_return)} nominal return · "
               f"{fmt_pct(inv_inflation)} inflation", kicker="Investment")
    multiple = inv_summary.total_growth / inv_summary.total_invested if inv_summary.total_invested > 0 else 0
    ui.kpis([
        dict(label="Final portfolio value", value=fmt_curr(inv_summary.final_nominal_value),
             note=f"Nominal value at year {inv_years:.0f}", tone="accent", accent=ui.ACCENT),
        dict(label="Real purchasing power", value=fmt_curr(inv_summary.final_real_value),
             delta=f"−{money0(inv_summary.purchasing_power_loss)} to inflation" if inv_summary.purchasing_power_loss > 0
             else None, tone="neg", arrow=False, note=f"at {fmt_pct(inv_inflation)} inflation"),
        dict(label="Total contributed", value=fmt_curr(inv_summary.total_contributions + inv_summary.initial_amount),
             note=f"Initial: {fmt_curr(inv_summary.initial_amount)}", accent=ui.ACCENT_2),
        dict(label="Total compound growth", value=fmt_curr(inv_summary.total_growth),
             delta=f"{multiple:.2f}x money invested", tone=ui.tone(inv_summary.total_growth), arrow=False,
             note="after tax"),
        dict(label="Effective APY / EAR", value=fmt_pct(inv_summary.effective_annual_return),
             note=f"Nominal {fmt_pct(inv_return)}; {fmt_pct(inv_summary.periodic_rate)} per period"),
    ], cols=5)

    ui.section("Growth trajectory", "Where the final value comes from, year by year.")
    col_iv1, col_iv2 = st.columns(2, gap="medium")
    yrs_x = df_inv_annual["year"]
    contrib_only = df_inv_annual["cumulative_contributions"] - inv_summary.initial_amount
    fig_inv = go.Figure()
    for y_, nm, col in ((np.full(len(yrs_x), inv_summary.initial_amount), "Initial capital", ui.PALETTE[4]),
                        (contrib_only, "Contributions", ui.ACCENT_2),
                        (df_inv_annual["cumulative_growth"], "Compound growth", ui.POS)):
        fig_inv.add_trace(go.Scatter(x=yrs_x, y=y_, name=nm, mode="lines", stackgroup="v",
                                     fillcolor=ui.rgba(col, 0.62), line=dict(color=col, width=1.2),
                                     hovertemplate="$%{y:,.0f}"))
    fig_inv.add_trace(go.Scatter(x=yrs_x, y=df_inv_annual["real_balance"], name="Real value (inflation-adj.)",
                                 mode="lines", line=dict(color=ui.INK, width=2.5, dash="dash"),
                                 hovertemplate="$%{y:,.0f}"))
    ui.style_fig(fig_inv, "Portfolio value by source", "Stacked nominal value; dashed line = purchasing power",
                 height=460, xtitle="Year")
    fig_inv.update_yaxes(tickformat="$~s")
    ui.chart(fig_inv, container=col_iv1)

    val_initial = inv_summary.initial_amount
    val_contrib = inv_summary.total_contributions
    val_growth = inv_summary.total_growth
    parts = [(l_, v_, c_) for l_, v_, c_ in (("Initial capital", val_initial, ui.PALETTE[4]),
                                             ("Contributions", val_contrib, ui.ACCENT_2),
                                             ("Compound growth", val_growth, ui.POS)) if v_ > 0]
    fig_pie = go.Figure(go.Pie(
        labels=[p_[0] for p_ in parts], values=[p_[1] for p_ in parts], hole=0.62, sort=False,
        marker=dict(colors=[p_[2] for p_ in parts], line=dict(color="white", width=2)),
        textinfo="percent", textfont=dict(size=13, color="white"),
        hovertemplate="%{label}: $%{value:,.0f} (%{percent})<extra></extra>"))
    fig_pie.add_annotation(text=f"<b>{money0(inv_summary.final_nominal_value)}</b><br>"
                                f"<span style='font-size:12px;color:{ui.MUTED}'>final value</span>",
                           showarrow=False, font=dict(size=20, color=ui.INK, family=ui.SERIF))
    ui.style_fig(fig_pie, "Final value composition", "Share of the nominal ending balance", height=460,
                 hovermode="closest")
    ui.chart(fig_pie, container=col_iv2)

    fig_bar = go.Figure()
    fig_bar.add_bar(x=yrs_x, y=df_inv_annual["contributions"], name="Contributions", marker_color=ui.ACCENT_2,
                    hovertemplate="$%{y:,.0f}")
    fig_bar.add_bar(x=yrs_x, y=df_inv_annual["interest_earned"], name="Growth / returns",
                    marker_color=ui.bar_colors(df_inv_annual["interest_earned"]) if (df_inv_annual["interest_earned"] < 0).any()
                    else ui.POS, hovertemplate="$%{y:,.0f}")
    if df_inv_annual["tax_paid"].sum() > 0:
        fig_bar.add_bar(x=yrs_x, y=-df_inv_annual["tax_paid"], name="Tax paid", marker_color=ui.NEG,
                        hovertemplate="$%{y:,.0f}")
    ui.style_fig(fig_bar, "Annual inflows", "Contributions vs compound returns each year; tax drag shown below zero",
                 height=400, xtitle="Year")
    fig_bar.update_layout(barmode="relative", bargap=0.18)
    fig_bar.update_yaxes(tickformat="$~s")
    ui.chart(fig_bar)

    ui.section("Goal-seek solver", "The regular contribution or annual return needed to reach a target value.",
               kicker="Solve")
    with st.container(border=True):
        col_gs1, col_gs2, col_gs3 = st.columns(3)
        with col_gs1:
            gs_target = st.number_input(
                "Target Future Value ($)",
                min_value=1_000.0,
                max_value=1_000_000_000.0,
                value=1_000_000.0,
                step=50_000.0,
                format="%.2f",
                key="gs_target"
            )
        with col_gs2:
            gs_mode = st.radio(
                "Solve For:",
                options=[f"Required Contribution per Period ({inv_freq_lbl.split()[0]})", "Required Annual Return"],
                key="gs_mode"
            )
        with col_gs3:
            gs_real_toggle = st.checkbox(
                "Target in Real Purchasing Power",
                value=False,
                help="If enabled, adjusts target to account for inflation over the horizon"
            )

        if gs_mode.startswith("Required Contribution"):
            req_contrib = goal_seek_contribution(
                target_future_value=gs_target,
                initial_amount=inv_initial,
                years=inv_years,
                annual_return=inv_return,
                contribution_frequency=inv_freq,
                contribution_timing=inv_timing,
                compounding_frequency=inv_comp,
                annual_contribution_increase_pct=inv_stepup,
                inflation_rate=inv_inflation,
                tax_rate_on_gains=inv_tax,
                adjust_target_for_inflation=gs_real_toggle
            )
            target_txt = f"{fmt_curr(gs_target)} in today's money" if gs_real_toggle else fmt_curr(gs_target)
            if req_contrib == 0:
                ui.callout(f"The initial amount alone reaches {target_txt}: no contributions are needed.", "pos",
                           "Goal-seek result")
            else:
                ui.callout(
                    f"To reach {target_txt} in {inv_years:g} years at {fmt_pct(inv_return)}, invest "
                    f"{fmt_curr(req_contrib)} per {inv_freq_lbl.split()[0].lower()} period"
                    + (f" in year 1, rising {inv_stepup*100:g}% a year." if inv_stepup else "."), "pos",
                    "Goal-seek result")
        else:
            req_ret = goal_seek_return(
                target_future_value=gs_target,
                initial_amount=inv_initial,
                regular_contribution=inv_contrib,
                years=inv_years,
                contribution_frequency=inv_freq,
                contribution_timing=inv_timing,
                compounding_frequency=inv_comp,
                annual_contribution_increase_pct=inv_stepup,
                inflation_rate=inv_inflation,
                tax_rate_on_gains=inv_tax,
                adjust_target_for_inflation=gs_real_toggle
            )
            if req_ret is not None:
                ui.callout(
                    f"To reach {fmt_curr(gs_target)}{' (real)' if gs_real_toggle else ''} with "
                    f"{fmt_curr(inv_contrib)} {inv_freq_lbl.split()[0].lower()} contributions, you need a nominal annual "
                    f"return of {fmt_pct(req_ret)} (compounded {inv_comp_lbl.split(' (')[0].lower()}).", "pos",
                    "Goal-seek result")
            else:
                ui.callout("Not reachable even at a 100% annual return. Increase the contributions or the horizon.",
                           "warn", "Goal-seek result")

    ui.section("Year-by-year growth schedule", "Nominal dollars; real balance in today's money.", kicker="Schedule")
    col_ie1, col_ie2, _sp2 = st.columns(3)
    with col_ie1:
        wb_inv_live, _ = build_investment_workbook(
            initial_amount=inv_initial,
            regular_contribution=inv_contrib,
            contribution_frequency=inv_freq,
            contribution_timing=inv_timing,
            annual_return=inv_return,
            compounding_frequency=inv_comp,
            years=inv_years,
            annual_contribution_increase_pct=inv_stepup,
            inflation_rate=inv_inflation,
            tax_rate_on_gains=inv_tax,
        )
        inv_excel_bytes = export_workbook_to_bytes(wb_inv_live)
        st.download_button(
            label="Download live Excel model (.xlsx)",
            data=inv_excel_bytes,
            file_name=f"Investment_Growth_{inv_years:.0f}yr.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_inv_excel", type="primary", width="stretch", icon=":material/download:",
        )
    with col_ie2:
        inv_csv_bytes = df_inv_annual.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download schedule (CSV)",
            data=inv_csv_bytes,
            file_name="investment_growth_schedule.csv",
            mime="text/csv",
            key="dl_inv_csv", width="stretch",
        )

    disp_inv_df = df_inv_annual.copy()
    disp_inv_df["year"] = disp_inv_df["year"].astype(int)
    disp_inv_df = disp_inv_df.set_index("year")
    disp_inv_df.columns = ["Beginning balance", "Contributions", "Growth earned", "Taxes paid", "Ending balance",
                           "Real balance", "Cumulative contributed", "Cumulative growth"]
    disp_inv_df["Taxes paid"] = -disp_inv_df["Taxes paid"]
    ui.html_table(disp_inv_df, fmt="acct2", index_label="Year", max_height=520)


# =============================================================================
# TAB 3: FINANCIAL TOOLS (NPV, IRR, APR TO EAR, LOAN COMPARISON)
# =============================================================================

with tab_tools:
    tool_subtab1, tool_subtab2, tool_subtab3 = st.tabs([
        "NPV & IRR Project Evaluator",
        "APR to EAR (APY) Converter",
        "Side-by-Side Loan Comparison"
    ])

    # -------------------------------------------------------------------------
    # TOOL 1: NPV & IRR EVALUATOR
    # -------------------------------------------------------------------------
    with tool_subtab1:
        ui.callout("Initial outlay at t = 0 (today, not discounted), then cash flows at the end of years 1..n. In "
                   "Excel: = CF0 + NPV(rate, CF1:CFn). Excel's NPV() discounts its first value by a full period, so "
                   "putting CF0 inside it is a classic mistake.", "info", "Discounted cash flow")

        col_dcf_in1, col_dcf_in2 = st.columns([1, 2], gap="medium")
        with col_dcf_in1.container(border=True):
            ui.subhead("Project", "Outlay, hurdle rate and horizon")
            dcf_init = st.number_input(
                "Initial Capital Outlay (Period 0) ($)",
                min_value=0.0,
                value=100_000.0,
                step=10_000.0,
                key="dcf_init"
            )
            dcf_rate = st.number_input(
                "Discount / Hurdle Rate (%)",
                min_value=0.0,
                max_value=50.0,
                value=10.0,
                step=0.5,
                key="dcf_rate"
            ) / 100.0
            n_periods = st.number_input("Number of Cash Flow Periods", min_value=1, max_value=25, value=5, step=1, key="dcf_n")

        with col_dcf_in2.container(border=True):
            ui.subhead("Cash inflows", "End-of-year amounts in dollars (negative = outflow)")
            default_cfs = [25_000.0, 35_000.0, 40_000.0, 35_000.0, 30_000.0]
            cf_inputs = []
            cols_grid = st.columns(min(int(n_periods), 5))
            for i in range(int(n_periods)):
                col_target = cols_grid[i % len(cols_grid)]
                with col_target:
                    def_val = default_cfs[i] if i < len(default_cfs) else 30_000.0
                    v = st.number_input(f"Year {i+1}", value=float(def_val), step=5000.0, format="%.0f", key=f"cf_p_{i+1}")
                    cf_inputs.append(v)

        dcf_res = analyze_cash_flows(dcf_init, cf_inputs, dcf_rate)

        irr_txt = fmt_pct(dcf_res.irr) if dcf_res.irr is not None else "N/A"
        pb_txt = (f"{dcf_res.discounted_payback_period:.2f} yrs" if dcf_res.discounted_payback_period is not None
                  else "Beyond horizon")
        ui.kpis([
            dict(label="NPV (CF0 at t = 0)", value=ui.money(dcf_res.npv),
                 delta="Accept (NPV > 0)" if dcf_res.npv > 0 else "Reject (NPV < 0)",
                 tone="pos" if dcf_res.npv > 0 else "neg", arrow=False,
                 value_tone="pos" if dcf_res.npv > 0 else "neg"),
            dict(label="Internal rate of return", value=irr_txt,
                 delta=(f"{(dcf_res.irr - dcf_rate) * 1e4:+,.0f} bps vs hurdle" if dcf_res.irr is not None else None),
                 tone=ui.tone(dcf_res.irr - dcf_rate) if dcf_res.irr is not None else "neutral",
                 note=f"Hurdle {fmt_pct(dcf_rate)}"),
            dict(label="Profitability index", value=(f"{dcf_res.profitability_index:.2f}"
                                                     if dcf_res.profitability_index is not None else "n/a"),
                 note="PV of inflows / outlay", accent=ui.ACCENT_2),
            dict(label="Discounted payback", value=pb_txt,
                 note="Simple payback: " + (f"{dcf_res.payback_period:.2f} yrs" if dcf_res.payback_period is not None
                                            else "beyond horizon"), accent=ui.ACCENT),
        ], cols=4)

        if dcf_res.irr_note:
            ui.callout(dcf_res.irr_note, "warn", "IRR")
        st.caption(
            f"Check: wrong Excel version `=NPV(rate, CF0:CFn)` would give {fmt_curr(dcf_res.excel_npv_all_values)} "
            f"(= correct NPV / (1 + rate)). Payback periods assume cash arrives evenly within each year."
        )

        g1, g2 = st.columns(2, gap="medium")
        all_cf = [-abs(dcf_init)] + list(cf_inputs)
        years_arr = list(range(len(all_cf)))
        pv = [cf / (1 + dcf_rate) ** t for t, cf in enumerate(all_cf)]
        fig_dcf = go.Figure()
        fig_dcf.add_bar(x=years_arr, y=all_cf, name="Cash flow", marker_color=[ui.rgba(c, 0.35) for c in
                                                                               ui.bar_colors(all_cf)],
                        hovertemplate="$%{y:,.0f}")
        fig_dcf.add_bar(x=years_arr, y=pv, name="Present value", marker_color=ui.bar_colors(pv),
                        hovertemplate="$%{y:,.0f}")
        fig_dcf.add_scatter(x=years_arr, y=dcf_res.cumulative_discounted_cash_flows, name="Cumulative discounted",
                            mode="lines+markers", line=dict(color=ui.INK, width=3), marker=dict(size=8),
                            hovertemplate="$%{y:,.0f}")
        fig_dcf.add_scatter(x=years_arr, y=dcf_res.cumulative_cash_flows, name="Cumulative undiscounted",
                            mode="lines", line=dict(color=ui.MUTED, width=2, dash="dot"), hovertemplate="$%{y:,.0f}")
        fig_dcf.add_hline(y=0, line_color=ui.INK_2, line_width=1)
        if dcf_res.discounted_payback_period is not None:
            fig_dcf.add_vline(x=dcf_res.discounted_payback_period, line_dash="dash", line_color=ui.POS,
                              annotation_text=f"Discounted payback {dcf_res.discounted_payback_period:.2f} yrs",
                              annotation_font=dict(color=ui.POS, size=11), annotation_position="top left")
        ui.style_fig(fig_dcf, "Cash flows and break-even", "Faded bars = nominal, solid = discounted at the hurdle rate",
                     height=460, xtitle="Year")
        fig_dcf.update_layout(barmode="group", bargap=0.25)
        fig_dcf.update_yaxes(tickformat="$~s")
        ui.chart(fig_dcf, container=g1)

        hi = max(0.4, (dcf_res.irr or 0) * 1.8, dcf_rate * 2)
        rates = np.linspace(0, hi, 61)
        prof = [analyze_cash_flows(dcf_init, cf_inputs, float(r)).npv for r in rates]
        fig_np = go.Figure()
        fig_np.add_scatter(x=rates, y=np.where(np.array(prof) >= 0, prof, np.nan), mode="lines", name="NPV > 0",
                           line=dict(color=ui.POS, width=3), fill="tozeroy", fillcolor=ui.rgba(ui.POS, 0.10),
                           hovertemplate="%{x:.1%}: $%{y:,.0f}<extra></extra>")
        fig_np.add_scatter(x=rates, y=np.where(np.array(prof) < 0, prof, np.nan), mode="lines", name="NPV < 0",
                           line=dict(color=ui.NEG, width=3), fill="tozeroy", fillcolor=ui.rgba(ui.NEG, 0.10),
                           hovertemplate="%{x:.1%}: $%{y:,.0f}<extra></extra>")
        fig_np.add_scatter(x=[dcf_rate], y=[dcf_res.npv], mode="markers+text", name="At hurdle rate",
                           marker=dict(size=12, color=ui.ACCENT_2, line=dict(color="white", width=2)),
                           text=[f"NPV {money0(dcf_res.npv)}"], textposition="top right",
                           hovertemplate="Hurdle %{x:.1%}: $%{y:,.0f}<extra></extra>")
        if dcf_res.irr is not None:
            fig_np.add_vline(x=dcf_res.irr, line_dash="dash", line_color=ui.INK_2,
                             annotation_text=f"IRR {fmt_pct(dcf_res.irr)}", annotation_position="top right",
                             annotation_font=dict(size=11, color=ui.INK_2))
        fig_np.add_hline(y=0, line_color=ui.INK_2, line_width=1)
        ui.style_fig(fig_np, "NPV profile", "NPV at every discount rate; it crosses zero at the IRR", height=460,
                     xtitle="Discount rate", hovermode="closest")
        fig_np.update_xaxes(tickformat=".0%")
        fig_np.update_yaxes(tickformat="$~s")
        ui.chart(fig_np, container=g2)

    # -------------------------------------------------------------------------
    # TOOL 2: APR TO EAR (APY) CONVERTER
    # -------------------------------------------------------------------------
    with tool_subtab2:
        ui.callout("Compounding frequency changes the actual annual yield: EAR = (1 + APR / m)^m − 1; continuous "
                   "compounding gives e^APR − 1.", "info", "Nominal vs effective")
        col_apr1, col_apr2 = st.columns([1, 2], gap="medium")
        with col_apr1:
            with st.container(border=True):
                apr_input = st.number_input(
                    "Nominal APR (%)",
                    min_value=0.01,
                    max_value=100.0,
                    value=8.0,
                    step=0.25,
                    key="apr_input"
                ) / 100.0
            df_apr_table = compare_apr_ear_frequencies(apr_input)
            ear_monthly_val = apr_to_ear(apr_input, 12)
            ui.kpis([dict(label="Effective annual yield (monthly)", value=fmt_pct(ear_monthly_val),
                          delta=f"+{(ear_monthly_val - apr_input)*10000:.1f} bps over APR", tone="pos")], cols=1)
            ui.kpis([dict(label="Continuous-compounding ceiling",
                          value=fmt_pct(float(df_apr_table["Effective EAR (APY)"].iloc[-1])),
                          delta=f"+{float(df_apr_table['Spread (bps)'].iloc[-1]):.1f} bps over APR", tone="accent",
                          arrow=False)], cols=1)

        with col_apr2:
            disp_apr = df_apr_table.copy().set_index("Compounding Frequency")
            disp_apr["Nominal APR"] = disp_apr["Nominal APR"].apply(fmt_pct)
            disp_apr["Effective EAR (APY)"] = disp_apr["Effective EAR (APY)"].apply(fmt_pct)
            disp_apr["Spread (bps)"] = disp_apr["Spread (bps)"].apply(lambda x: f"+{x:.1f} bps")
            disp_apr = disp_apr.astype(str)
            ui.html_table(disp_apr, fmt="plain", index_label="Compounding")

        sp = df_apr_table["Spread (bps)"].astype(float)
        shades = [ui.rgba(ui.ACCENT, 0.35 + 0.65 * (v / sp.max() if sp.max() > 0 else 0)) for v in sp]
        fig_ear = go.Figure(go.Bar(x=df_apr_table["Compounding Frequency"], y=sp, marker_color=shades,
                                   text=[f"{v:.1f}" for v in sp], textposition="outside",
                                   hovertemplate="%{x}: +%{y:.2f} bps<extra></extra>"))
        ui.style_fig(fig_ear, "Yield spread over the nominal APR", "Basis points gained from more frequent "
                     "compounding", height=400, legend=False, hovermode="closest")
        fig_ear.update_yaxes(ticksuffix=" bps")
        ui.chart(fig_ear)

    # -------------------------------------------------------------------------
    # TOOL 3: SIDE-BY-SIDE LOAN COMPARISON
    # -------------------------------------------------------------------------
    with tool_subtab3:
        ui.callout("Compare two financing proposals, e.g. 30-year vs 15-year, or a low rate with points vs a higher "
                   "rate with no points. Monthly payments, fees not financed.", "info", "Refinance analysis")
        col_la, col_lb = st.columns(2, gap="medium")
        with col_la.container(border=True):
            ui.subhead("Loan option A", "")
            name_a = st.text_input("Name", value="30-Year Fixed (Standard)", key="name_a")
            ca1, ca2 = st.columns(2)
            prin_a = ca1.number_input("Principal ($)", value=350_000.0, step=10_000.0, key="prin_a")
            rate_a = ca2.number_input("Interest Rate (%)", value=6.75, step=0.125, key="rate_a") / 100.0
            term_a = ca1.number_input("Term (Years)", value=30.0, step=1.0, key="term_a")
            fee_a = ca2.number_input("Upfront Fees / Points ($)", value=0.0, step=500.0, key="fee_a")

        with col_lb.container(border=True):
            ui.subhead("Loan option B", "")
            name_b = st.text_input("Name", value="15-Year Fixed (Accelerated)", key="name_b")
            cb1, cb2 = st.columns(2)
            prin_b = cb1.number_input("Principal ($)", value=350_000.0, step=10_000.0, key="prin_b")
            rate_b = cb2.number_input("Interest Rate (%)", value=5.75, step=0.125, key="rate_b") / 100.0
            term_b = cb1.number_input("Term (Years)", value=15.0, step=1.0, key="term_b")
            fee_b = cb2.number_input("Upfront Fees / Points ($)", value=2_500.0, step=500.0, key="fee_b")

        comp_res = compare_two_loans(
            principal_a=prin_a,
            rate_a=rate_a,
            term_a_years=term_a,
            upfront_fees_a=fee_a,
            principal_b=prin_b,
            rate_b=rate_b,
            term_b_years=term_b,
            upfront_fees_b=fee_b,
            name_a=name_a,
            name_b=name_b
        )

        be_txt = f"{comp_res.breakeven_months:.1f} months" if comp_res.breakeven_months else "n/a"
        ui.kpis([
            dict(label="Monthly payment delta", value=f"{fmt_curr(abs(comp_res.payment_difference))} / mo",
                 note=f"{name_b if comp_res.payment_difference > 0 else name_a} pays more per month",
                 accent=ui.ACCENT_2),
            dict(label="Lifetime interest delta", value=fmt_curr(abs(comp_res.interest_difference)),
                 delta=f"lower total cost: {comp_res.cheaper_loan}", tone="pos", arrow=False,
                 note=f"{name_a if comp_res.interest_difference > 0 else name_b} pays less interest"),
            dict(label="Upfront fee break-even", value=be_txt,
                 note="Extra fees / monthly saving (simple, undiscounted)", accent=ui.ACCENT),
        ], cols=3)

        disp_comp = comp_res.summary_df.copy()
        for idx in [0, 3, 4, 5, 6]:
            val_a = disp_comp.loc[idx, name_a]
            val_b = disp_comp.loc[idx, name_b]
            diff = disp_comp.loc[idx, "Difference"]
            if isinstance(val_a, (int, float)):
                disp_comp.loc[idx, name_a] = fmt_curr(val_a)
            if isinstance(val_b, (int, float)):
                disp_comp.loc[idx, name_b] = fmt_curr(val_b)
            if isinstance(diff, (int, float)):
                disp_comp.loc[idx, "Difference"] = (f"−{fmt_curr(-diff)}" if diff < 0 else
                                                    f"{'+' if diff > 0 else ''}{fmt_curr(diff)}")
        disp_comp = disp_comp.set_index("Metric").astype(str)
        ui.html_table(disp_comp, fmt="plain", index_label="Metric",
                      row_styles={"Total Cost (payments + fees, undiscounted)": "total"})

        sched_a = compute_amortization_schedule(prin_a, rate_a, term_a, 12).schedule
        sched_b = compute_amortization_schedule(prin_b, rate_b, term_b, 12).schedule
        g1, g2 = st.columns(2, gap="medium")
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Scatter(x=sched_a["period"], y=sched_a["ending_balance"], name=name_a, mode="lines",
                                      line=dict(color=ui.ACCENT_2, width=3), fill="tozeroy",
                                      fillcolor=ui.rgba(ui.ACCENT_2, 0.08), hovertemplate="$%{y:,.0f}"))
        fig_comp.add_trace(go.Scatter(x=sched_b["period"], y=sched_b["ending_balance"], name=name_b, mode="lines",
                                      line=dict(color=ui.PALETTE[1], width=3), fill="tozeroy",
                                      fillcolor=ui.rgba(ui.PALETTE[1], 0.08), hovertemplate="$%{y:,.0f}"))
        ui.style_fig(fig_comp, "Remaining balance", "Month by month", height=440, xtitle="Month #")
        fig_comp.update_yaxes(tickformat="$~s")
        ui.chart(fig_comp, container=g1)

        fig_ci = go.Figure()
        fig_ci.add_trace(go.Scatter(x=sched_a["period"], y=sched_a["cumulative_interest"], name=name_a, mode="lines",
                                    line=dict(color=ui.ACCENT_2, width=3), hovertemplate="$%{y:,.0f}"))
        fig_ci.add_trace(go.Scatter(x=sched_b["period"], y=sched_b["cumulative_interest"], name=name_b, mode="lines",
                                    line=dict(color=ui.PALETTE[1], width=3), hovertemplate="$%{y:,.0f}"))
        ui.style_fig(fig_ci, "Cumulative interest paid", "The gap at the end is the lifetime interest delta",
                     height=440, xtitle="Month #")
        fig_ci.update_yaxes(tickformat="$~s")
        ui.chart(fig_ci, container=g2)

ui.footer("TVM functions and Excel exports checked against LibreOffice Calc · Python, Streamlit, Plotly, openpyxl · "
          "educational tool, not financial advice.")
