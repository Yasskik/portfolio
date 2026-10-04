"""
Unit Tests for Financial Calculation Engine & Excel Export
==========================================================
Tests check mathematical outputs against known Excel and textbook values.
"""

import math
from datetime import date
import openpyxl
import pytest

from finance_calc import (
    pmt,
    fv,
    pv,
    nper,
    rate,
    ipmt,
    ppmt,
    npv,
    net_present_value,
    irr,
    apr_to_ear,
    ear_to_apr,
    compute_amortization_schedule,
    compute_investment_growth,
    goal_seek_contribution,
    goal_seek_return,
    analyze_cash_flows,
    compare_apr_ear_frequencies,
    compare_two_loans
)
from excel_export import create_financial_workbook, export_workbook_to_bytes


class TestCoreTVMFormulas:
    """Test TVM functions against known Excel results."""

    def test_pmt_standard_mortgage(self):
        # Excel: =PMT(0.06/12, 360, 200000) -> -1199.10
        val = pmt(0.06 / 12, 360, 200000)
        assert round(val, 2) == -1199.10

    def test_pmt_zero_rate(self):
        # Excel: =PMT(0, 10, 1000) -> -100.00
        val = pmt(0, 10, 1000)
        assert round(val, 2) == -100.00

    def test_pmt_annuity_due(self):
        # Excel: =PMT(0.08/12, 120, 10000, 0, 1) -> -120.52
        val = pmt(0.08 / 12, 120, 10000, 0, 1)
        assert round(val, 2) == -120.52

    def test_fv_ordinary_annuity(self):
        # Excel: =FV(0.05/12, 120, -100, -1000) -> 17175.24
        val = fv(0.05 / 12, 120, -100, -1000)
        assert round(val, 2) == 17175.24

    def test_fv_zero_rate(self):
        val = fv(0, 10, -100, -500)
        assert val == 1500.0

    def test_pv_ordinary_annuity(self):
        # Excel: =PV(0.08/12, 120, -121.3276) -> 10000.00
        val = pv(0.08 / 12, 120, -121.32759)
        assert round(val, 2) == 10000.00

    def test_pv_zero_rate(self):
        val = pv(0, 10, -100, -1000)
        assert val == 2000.0

    def test_nper_standard(self):
        # Excel: =NPER(0.06/12, -1199.1011, 200000) -> 360.00
        val = nper(0.06 / 12, -1199.1011, 200000)
        assert round(val, 1) == 360.0

    def test_nper_zero_rate(self):
        val = nper(0, -100, 1000)
        assert val == 10.0

    def test_rate_standard(self):
        # Excel: =RATE(360, -1199.1011, 200000) -> 0.005 (0.5% per month)
        r = rate(360, -1199.1011, 200000)
        assert round(r, 5) == 0.00500

    def test_ipmt_and_ppmt_period_1(self):
        # Period 1 of 360, 6% on 200k
        # IPMT = -200000 * 0.005 = -1000.00
        # PMT = -1199.10
        # PPMT = -199.10
        i1 = ipmt(0.06 / 12, 1, 360, 200000)
        p1 = ppmt(0.06 / 12, 1, 360, 200000)
        tot = pmt(0.06 / 12, 360, 200000)

        assert round(i1, 2) == -1000.00
        assert round(p1, 2) == -199.10
        assert round(i1 + p1, 2) == round(tot, 2)

    def test_npv_excel_values(self):
        # Excel: =NPV(0.10, 100, 200, 300) -> 481.59
        cfs = [100, 200, 300]
        val = npv(0.10, cfs)
        assert round(val, 2) == 481.59

    def test_irr_excel_values(self):
        # Excel: =IRR({-1000, 300, 420, 680}) -> 0.1634 (16.34%)
        cfs = [-1000, 300, 420, 680]
        val = irr(cfs)
        assert round(val, 4) == 0.1634

    def test_apr_to_ear_monthly(self):
        # 12% APR compounded monthly = (1 + 0.01)^12 - 1 = 12.6825%
        ear_val = apr_to_ear(0.12, 12)
        assert round(ear_val, 6) == round((1.01 ** 12) - 1, 6)
        apr_back = ear_to_apr(ear_val, 12)
        assert round(apr_back, 6) == 0.120000

    def test_apr_to_ear_continuous(self):
        # 10% APR compounded continuous = e^0.10 - 1
        ear_val = apr_to_ear(0.10, -1)
        assert round(ear_val, 6) == round(math.exp(0.10) - 1, 6)


class TestLoanAmortizationEngine:
    """Test loan amortization schedule generation, extra payments, and payoff acceleration."""

    def test_fixed_payment_amortization_payoff(self):
        # $100,000 at 5% for 15 years monthly
        res = compute_amortization_schedule(
            principal=100000,
            annual_interest_rate=0.05,
            term_years=15,
            payment_frequency=12,
            start_date=date(2026, 1, 1),
            loan_type="fixed_payment"
        )
        assert res.summary.total_payments_count == 180
        assert res.summary.actual_payments_count == 180
        # Ending balance of final row must be zero
        assert res.schedule["ending_balance"].iloc[-1] == 0.0
        # Total principal paid equals original principal
        assert round(res.summary.total_principal_paid, 0) == 100000

    def test_equal_principal_loan(self):
        res = compute_amortization_schedule(
            principal=120000,
            annual_interest_rate=0.06,
            term_years=10,
            payment_frequency=12,
            loan_type="equal_principal"
        )
        assert res.summary.actual_payments_count == 120
        # Principal payment in every row before the end should be ~1000
        assert round(res.schedule["principal"].iloc[0], 2) == 1000.00
        assert round(res.schedule["principal"].iloc[50], 2) == 1000.00
        assert res.schedule["ending_balance"].iloc[-1] == 0.0

    def test_interest_only_loan(self):
        res = compute_amortization_schedule(
            principal=200000,
            annual_interest_rate=0.06,
            term_years=5,
            payment_frequency=12,
            loan_type="interest_only"
        )
        assert res.summary.actual_payments_count == 60
        # Payments in periods 1 to 59 are purely interest: 200,000 * 0.06/12 = 1,000
        assert res.schedule["principal"].iloc[0] == 0.0
        assert res.schedule["interest"].iloc[0] == 1000.00
        # Period 60 pays full principal
        assert res.schedule["principal"].iloc[-1] == 200000.00
        assert res.schedule["ending_balance"].iloc[-1] == 0.0

    def test_extra_recurring_payment_accelerates_payoff(self):
        # Base loan: $300k at 6% for 30 years -> 360 months
        # Add $250 extra per month
        res = compute_amortization_schedule(
            principal=300000,
            annual_interest_rate=0.06,
            term_years=30,
            payment_frequency=12,
            recurring_extra_payment=250.0
        )
        assert res.summary.periods_saved > 0
        assert res.summary.interest_saved > 20000.0  # Saves significant interest
        assert res.summary.actual_payments_count < 360
        assert res.schedule["ending_balance"].iloc[-1] == 0.0

    def test_lump_sum_extra_payment(self):
        # Lump sum of $20,000 at month 12
        res = compute_amortization_schedule(
            principal=200000,
            annual_interest_rate=0.05,
            term_years=20,
            payment_frequency=12,
            lump_sum_extras={12: 20000.0}
        )
        assert res.summary.interest_saved > 10000.0
        assert res.summary.periods_saved > 0
        row12 = res.schedule[res.schedule["period"] == 12].iloc[0]
        assert row12["extra_payment"] == 20000.0


class TestInvestmentGrowthEngine:
    """Test compound growth, inflation adjustment, step-up contributions, and goal seek."""

    def test_basic_compound_growth(self):
        res = compute_investment_growth(
            initial_amount=10000,
            regular_contribution=500,
            contribution_frequency=12,
            annual_return=0.08,
            years=10
        )
        assert res.summary.final_nominal_value > 100000
        assert res.summary.total_growth > 0
        assert res.summary.final_real_value < res.summary.final_nominal_value

    def test_annual_schedule_matches_periods(self):
        res = compute_investment_growth(
            initial_amount=5000,
            regular_contribution=200,
            contribution_frequency=12,
            annual_return=0.07,
            years=5
        )
        df_ann = res.annual_schedule
        assert len(df_ann) == 5
        # Final year ending balance matches period ending balance
        assert round(df_ann["ending_balance"].iloc[-1], 2) == round(res.summary.final_nominal_value, 2)

    def test_contribution_step_up(self):
        res_no_step = compute_investment_growth(
            initial_amount=0,
            regular_contribution=1000,
            contribution_frequency=1,
            annual_return=0.05,
            years=5,
            annual_contribution_increase_pct=0.0
        )
        res_step = compute_investment_growth(
            initial_amount=0,
            regular_contribution=1000,
            contribution_frequency=1,
            annual_return=0.05,
            years=5,
            annual_contribution_increase_pct=0.05
        )
        assert res_step.summary.total_contributions > res_no_step.summary.total_contributions
        assert res_step.summary.final_nominal_value > res_no_step.summary.final_nominal_value

    def test_goal_seek_contribution(self):
        # Target: $1,000,000 in 30 years at 8% with $10k initial
        req_contrib = goal_seek_contribution(
            target_future_value=1000000,
            initial_amount=10000,
            years=30,
            annual_return=0.08,
            contribution_frequency=12
        )
        assert req_contrib > 0
        # Verify result achieved is close to $1M
        check_res = compute_investment_growth(
            initial_amount=10000,
            regular_contribution=req_contrib,
            contribution_frequency=12,
            annual_return=0.08,
            years=30
        )
        assert abs(check_res.summary.final_nominal_value - 1000000) < 100.0

    def test_goal_seek_return(self):
        # Given $50,000 initial and $500/mo, what return is needed to reach $500,000 in 15 years?
        req_ret = goal_seek_return(
            target_future_value=500000,
            initial_amount=50000,
            regular_contribution=500,
            years=15,
            contribution_frequency=12
        )
        assert req_ret is not None
        assert req_ret > 0.05
        # Verify
        check_res = compute_investment_growth(
            initial_amount=50000,
            regular_contribution=500,
            contribution_frequency=12,
            annual_return=req_ret,
            years=15
        )
        assert abs(check_res.summary.final_nominal_value - 500000) < 500.0


class TestFinancialTools:
    """Test DCF cash flow analysis, loan comparison, and APR-to-EAR."""

    def test_analyze_cash_flows(self):
        res = analyze_cash_flows(
            initial_investment=1000,
            cash_flows=[300, 420, 680],
            discount_rate=0.10
        )
        assert res.npv > 0
        assert res.irr is not None and round(res.irr, 4) == 0.1634
        assert res.profitability_index > 1.0
        assert res.payback_period is not None and 2.0 <= res.payback_period <= 3.0

    def test_compare_two_loans(self):
        comp = compare_two_loans(
            principal_a=300000,
            rate_a=0.065,
            term_a_years=30,
            upfront_fees_a=0,
            principal_b=300000,
            rate_b=0.055,
            term_b_years=15,
            upfront_fees_b=3000,
            name_a="30-Year Fixed (6.5%)",
            name_b="15-Year Fixed (5.5%)"
        )
        # 15-yr will have higher monthly payment but drastically lower total interest
        assert comp.loan_b_pmt > comp.loan_a_pmt
        assert comp.loan_b_total_interest < comp.loan_a_total_interest
        assert comp.cheaper_loan == "15-Year Fixed (5.5%)"

    def test_apr_ear_table(self):
        df = compare_apr_ear_frequencies(0.08)
        assert len(df) == 8
        # Compounding daily or continuous should be higher than monthly
        ear_annual = df[df["Compounding Frequency"] == "Annually"]["Effective EAR (APY)"].iloc[0]
        ear_monthly = df[df["Compounding Frequency"] == "Monthly"]["Effective EAR (APY)"].iloc[0]
        ear_daily = df[df["Compounding Frequency"] == "Daily"]["Effective EAR (APY)"].iloc[0]
        assert ear_annual < ear_monthly < ear_daily


class TestEdgeCasesAndFrequencies:
    """Additional edge cases to ensure robustness."""

    def test_quarterly_and_annual_loan_frequencies(self):
        # Quarterly loan
        res_q = compute_amortization_schedule(
            principal=100000,
            annual_interest_rate=0.06,
            term_years=5,
            payment_frequency=4
        )
        assert res_q.summary.total_payments_count == 20
        assert res_q.schedule["ending_balance"].iloc[-1] == 0.0

        # Annual loan
        res_a = compute_amortization_schedule(
            principal=50000,
            annual_interest_rate=0.08,
            term_years=10,
            payment_frequency=1
        )
        assert res_a.summary.total_payments_count == 10
        assert res_a.schedule["ending_balance"].iloc[-1] == 0.0

    def test_investment_tax_drag(self):
        # Investment with tax drag on gains
        res_no_tax = compute_investment_growth(
            initial_amount=10000,
            regular_contribution=500,
            annual_return=0.10,
            years=10,
            tax_rate_on_gains=0.0
        )
        res_taxed = compute_investment_growth(
            initial_amount=10000,
            regular_contribution=500,
            annual_return=0.10,
            years=10,
            tax_rate_on_gains=0.20
        )
        assert res_taxed.summary.final_nominal_value < res_no_tax.summary.final_nominal_value
        assert res_taxed.summary.total_taxes_paid > 0

    def test_balloon_loan_structure(self):
        res = compute_amortization_schedule(
            principal=100000,
            annual_interest_rate=0.05,
            term_years=5,
            payment_frequency=12,
            balloon_amount=20000.0
        )
        assert res.summary.actual_payments_count == 60
        assert res.schedule["ending_balance"].iloc[-1] == 0.0


class TestExcelExport:
    """Test dynamic live Excel generation with openpyxl."""

    def test_create_financial_workbook_and_formulas(self):
        wb = create_financial_workbook(
            loan=dict(principal=250000, annual_interest_rate=0.06, term_years=15, payment_frequency=12,
                      recurring_extra=100),
            investment=dict(initial_amount=25000.0, regular_contribution=1000.0, annual_return=0.08, years=30),
        )
        assert {"Loan", "Investment", "Investment (Annual)", "TVM Functions"} <= set(wb.sheetnames)

        ws_loan = wb["Loan"]
        assert ws_loan["C4"].value == 250000
        assert ws_loan["C5"].value == 0.06
        assert ws_loan["C6"].value == 15
        assert ws_loan["C7"].value == 12
        assert "PMT" in str(ws_loan["C18"].value)
        assert "EDATE" in str(ws_loan["B32"].value)
        assert "ROUND" in str(ws_loan["D32"].value)
        assert "SUM" in str(ws_loan["I7"].value)

        ws_inv = wb["Investment"]
        assert ws_inv["C4"].value == 25000.0
        assert ws_inv["C8"].value == 0.08
        assert str(ws_inv["E25"].value).startswith("=")

        data = export_workbook_to_bytes(wb)
        assert len(data) > 5000
