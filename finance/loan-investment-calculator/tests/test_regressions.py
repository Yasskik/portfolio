"""Regression tests for the review fixes (TVM conventions, schedules, investment model, tools)."""
import math
from datetime import date

import pytest

import finance_calc as fc
from finance_calc import (analyze_cash_flows, compute_amortization_schedule, compute_investment_growth,
                          goal_seek_contribution, goal_seek_return, periodic_rate, xround)


# ---------------------------------------------------------------- rounding / rates
def test_round_half_up_like_excel():
    assert xround(2.675) == 2.68          # Python's round(2.675, 2) gives 2.67
    assert xround(1.005) == 1.01
    assert xround(0.125) == 0.13          # banker's rounding would give 0.12
    assert xround(-0.125) == -0.13
    assert xround(-0.001) == 0.0 and math.copysign(1, xround(-0.001)) == 1.0


def test_periodic_rate_equivalent():
    assert periodic_rate(0.06, 12, 12) == 0.06 / 12
    i = periodic_rate(0.06, 4, 12)          # quarterly compounding, monthly contributions
    assert (1 + i) ** 12 == pytest.approx((1 + 0.06 / 4) ** 4, rel=1e-14)
    assert periodic_rate(0.05, 0, 12) == pytest.approx(math.exp(0.05 / 12) - 1)
    assert periodic_rate(0.05, -1, 12) == pytest.approx(math.exp(0.05 / 12) - 1)


def test_effect_nominal_and_errors():
    assert fc.effect(0.06, 12) == pytest.approx(0.0616778118644985, abs=1e-15)
    assert fc.nominal(fc.effect(0.06, 12), 12) == pytest.approx(0.06, abs=1e-13)
    with pytest.raises(ValueError):
        fc.effect(0.06, 0)
    assert fc.apr_to_ear(0.0, 12) == 0.0


# ---------------------------------------------------------------- TVM edge cases
def test_rate_no_solution_raises_instead_of_garbage():
    with pytest.raises(ValueError):            # old code returned -164% silently
        fc.rate(10, 100, 1000, 0)


def test_rate_zero_and_beginning():
    assert fc.rate(12, 0, -1000, 1000, 1, 0.0) == pytest.approx(0.0, abs=1e-12)
    r = fc.rate(60, -400, 20000, 0, 1)
    assert fc.pmt(r, 60, 20000, 0, 1) == pytest.approx(-400, abs=1e-8)


def test_ipmt_beginning_convention():
    # Excel/LibreOffice: IPMT(0.08/12, 2, 120, 10000, 0, 1) = -65.8631726643133
    assert fc.ipmt(0.08 / 12, 1, 120, 10000, 0, 1) == 0.0
    assert fc.ipmt(0.08 / 12, 2, 120, 10000, 0, 1) == pytest.approx(-65.8631726643133, abs=1e-9)
    assert fc.ppmt(0.08 / 12, 2, 120, 10000, 0, 1) == pytest.approx(-54.6609276886902, abs=1e-9)


def test_pmt_requires_positive_nper():
    with pytest.raises(ValueError):
        fc.pmt(0.01, 0, 1000)


def test_irr_edge_cases():
    with pytest.raises(ValueError):
        fc.irr([100, 50])                     # no sign change
    roots = fc.irr_all([-100, 230, -132])     # two sign changes -> 10% and 20%
    assert roots == pytest.approx([0.10, 0.20], abs=1e-9)
    assert fc.irr([-100, 230, -132], 0.05) == pytest.approx(0.10)
    assert fc.irr([-100, 230, -132], 0.18) == pytest.approx(0.20)
    # old code crashed with OverflowError here; the true root is about -89.5%
    r = fc.irr([-1e6, 10000, 10000])
    assert -1e6 + 10000 / (1 + r) + 10000 / (1 + r) ** 2 == pytest.approx(0, abs=1e-4)


def test_npv_convention_t0_vs_excel():
    cfs = [25000, 35000, 40000, 35000, 30000]
    correct = fc.net_present_value(0.10, -100000, cfs)
    assert correct == pytest.approx(24238.5952275987, abs=1e-6)       # LibreOffice value
    wrong = fc.npv(0.10, [-100000] + cfs)
    assert wrong == pytest.approx(correct / 1.10)
    res = analyze_cash_flows(100000, cfs, 0.10)
    assert res.npv == pytest.approx(correct)
    assert res.excel_npv_all_values == pytest.approx(wrong)
    assert res.irr == pytest.approx(0.187778056387563, abs=1e-12)
    assert res.irr_note == ""


def test_cash_flow_tool_notes_and_zero_outlay():
    res = analyze_cash_flows(100, [230, -132], 0.05)
    assert "Multiple IRRs" in res.irr_note and len(res.irr_roots) == 2
    res2 = analyze_cash_flows(100, [-10, -20], 0.05)
    assert res2.irr is None and "never change sign" in res2.irr_note
    res3 = analyze_cash_flows(0, [100, 200], 0.1)
    assert res3.profitability_index is None
    res4 = analyze_cash_flows(1000, [100, 100], 0.1)
    assert res4.payback_period is None and res4.discounted_payback_period is None


# ---------------------------------------------------------------- loans
def test_reference_mortgage():
    r = compute_amortization_schedule(200_000, 0.06, 30, 12, date(2026, 11, 1))
    s = r.summary
    assert s.scheduled_payment == 1199.10
    assert s.total_interest_paid == 231_677.04
    assert s.final_payment == 1200.14
    assert r.schedule["ending_balance"].iloc[-1] == 0.0
    assert r.schedule["principal"].sum() == pytest.approx(200_000, abs=1e-6)
    assert s.payoff_date == date(2056, 10, 1)


def test_extra_payments_shorten_term_like_nper():
    r = compute_amortization_schedule(200_000, 0.06, 30, 12, date(2026, 11, 1), recurring_extra_payment=200)
    s = r.summary
    assert s.actual_payments_count == math.ceil(fc.nper(0.005, -1399.10, 200_000)) == 252
    assert s.total_interest_paid == 151_876.18
    assert s.interest_saved == pytest.approx(231_677.04 - 151_876.18, abs=0.005)
    assert s.payoff_date == date(2047, 10, 1)
    assert r.schedule["ending_balance"].iloc[-1] == 0.0
    assert s.total_principal_paid == pytest.approx(200_000, abs=0.005)


def test_extra_start_period_and_lump_sum_cap():
    r = compute_amortization_schedule(10_000, 0.05, 1, 12, date(2026, 1, 1), recurring_extra_payment=100,
                                      recurring_extra_start_period=6, lump_sum_extras={10: 1e9})
    sch = r.schedule
    assert (sch.loc[sch.period < 6, "extra_payment"] == 0).all()
    assert sch["ending_balance"].iloc[-1] == 0.0 and len(sch) == 10   # huge lump sum capped at the balance


@pytest.mark.parametrize("loan_type", ["fixed_payment", "equal_principal", "interest_only"])
@pytest.mark.parametrize("freq", [1, 2, 4, 12, 26, 52])
def test_every_schedule_ends_at_exactly_zero(loan_type, freq):
    r = compute_amortization_schedule(123_456.78, 0.0725, 7, freq, date(2026, 1, 31), loan_type,
                                      recurring_extra_payment=37.5)
    sch = r.schedule
    assert sch["ending_balance"].iloc[-1] == 0.0
    assert (sch["ending_balance"] >= 0).all()
    assert sch["principal"].sum() + sch["extra_payment"].sum() == pytest.approx(123_456.78, abs=1e-6)
    for col in ("interest", "principal", "extra_payment", "total_payment", "ending_balance"):
        assert all(abs(v * 100 - round(v * 100)) < 1e-6 for v in sch[col])  # whole cents


def test_month_end_dates_like_edate():
    r = compute_amortization_schedule(10_000, 0.05, 3, 12, date(2027, 1, 31))
    d = list(r.schedule["date"])
    assert d[:4] == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]
    assert date(2028, 2, 29) in d                                       # leap year
    b = compute_amortization_schedule(10_000, 0.05, 1, 26, date(2026, 10, 2))
    assert b.schedule["date"].iloc[1] == date(2026, 10, 16)


def test_balloon_loan():
    r = compute_amortization_schedule(100_000, 0.05, 5, 12, date(2026, 1, 31), balloon_amount=20_000)
    assert r.summary.scheduled_payment == xround(-fc.pmt(0.05 / 12, 60, 100_000, -20_000))
    last = r.schedule.iloc[-1]
    assert last["beginning_balance"] == pytest.approx(20_000 + r.summary.scheduled_payment, rel=0.01)
    assert last["total_payment"] == r.summary.final_payment == 21_593.15
    with pytest.raises(ValueError):
        compute_amortization_schedule(100_000, 0.05, 5, balloon_amount=100_000)


def test_interest_only_and_equal_principal():
    io = compute_amortization_schedule(200_000, 0.06, 5, 12, loan_type="interest_only")
    assert (io.schedule["scheduled_payment"].iloc[:-1] == 1000.0).all()
    assert io.summary.final_payment == 201_000.0
    ep = compute_amortization_schedule(120_000, 0.06, 10, 12, loan_type="equal_principal")
    assert ep.summary.scheduled_payment == 1600.0                       # 1,000 principal + 600 interest
    assert ep.schedule["scheduled_payment"].is_monotonic_decreasing


def test_zero_interest_loan():
    r = compute_amortization_schedule(10_000, 0.0, 1, 12, date(2026, 1, 1))
    assert r.summary.scheduled_payment == 833.33
    assert r.summary.total_interest_paid == 0.0
    assert r.summary.final_payment == 833.37
    io = compute_amortization_schedule(10_000, 0.0, 1, 12, loan_type="interest_only")
    assert io.summary.actual_payments_count == 12 and io.summary.final_payment == 10_000


def test_canadian_compounding():
    r = compute_amortization_schedule(400_000, 0.0499, 25, 12, compounding_frequency=2)
    i = (1 + 0.0499 / 2) ** (2 / 12) - 1
    assert r.summary.periodic_rate == pytest.approx(i, rel=1e-14)
    assert r.summary.scheduled_payment == xround(-fc.pmt(i, 300, 400_000))


def test_loan_validation():
    for kw in (dict(annual_interest_rate=-0.01), dict(payment_frequency=24), dict(loan_type="bullet"),
               dict(recurring_extra_payment=-5)):
        args = dict(principal=1000, annual_interest_rate=0.05, term_years=1) | kw
        with pytest.raises(ValueError):
            compute_amortization_schedule(**args)


# ---------------------------------------------------------------- investments
@pytest.mark.parametrize("timing,when", [("end", 0), ("beginning", 1)])
@pytest.mark.parametrize("comp", [1, 4, 12, 365, -1])
def test_investment_matches_excel_fv(timing, when, comp):
    res = compute_investment_growth(10_000, 500, 12, timing, 0.07, comp, 20, 0, 0, 0)
    i = periodic_rate(0.07, comp, 12)
    assert res.summary.final_nominal_value == pytest.approx(fc.fv(i, 240, -500, -10_000, when), rel=1e-12)


def test_reference_investment():
    s = compute_investment_growth(10_000, 500, 12, "end", 0.07, 12, 20, 0, 0, 0).summary
    assert round(s.final_nominal_value, 2) == 300_850.72
    assert s.total_invested == 130_000 and s.total_contributions == 120_000
    assert round(s.total_growth, 2) == 170_850.72


def test_compounding_vs_contribution_frequency_same_ear():
    a = compute_investment_growth(1000, 0, 12, annual_return=0.06, compounding_frequency=4, years=1, inflation_rate=0)
    b = compute_investment_growth(1000, 0, 1, annual_return=0.06, compounding_frequency=4, years=1, inflation_rate=0)
    assert a.summary.final_nominal_value == pytest.approx(1000 * (1 + 0.06 / 4) ** 4, rel=1e-13)
    assert b.summary.final_nominal_value == pytest.approx(a.summary.final_nominal_value, rel=1e-13)


def test_tax_drag_and_inflation():
    s = compute_investment_growth(10_000, 0, 1, annual_return=0.10, compounding_frequency=1, years=10,
                                  inflation_rate=0.03, tax_rate_on_gains=0.25).summary
    assert s.final_nominal_value == pytest.approx(10_000 * 1.075 ** 10, rel=1e-12)   # 10% x (1 - 25%)
    assert s.final_real_value == pytest.approx(s.final_nominal_value / 1.03 ** 10, rel=1e-12)
    neg = compute_investment_growth(10_000, 0, 1, annual_return=-0.10, compounding_frequency=1, years=1,
                                    inflation_rate=0, tax_rate_on_gains=0.25).summary
    assert neg.total_taxes_paid == 0 and neg.final_nominal_value == pytest.approx(9000)


def test_step_up_not_rounded():
    s = compute_investment_growth(0, 100, 1, "end", 0.0, 1, 3, 0.03, 0, 0).summary
    assert s.total_contributions == pytest.approx(100 + 103 + 106.09)


def test_goal_seek_contribution_exact_and_frequency():
    for freq in (12, 52, 4):
        c = goal_seek_contribution(1_000_000, 10_000, 30, 0.08, contribution_frequency=freq)
        fvv = compute_investment_growth(10_000, c, freq, annual_return=0.08, years=30).summary.final_nominal_value
        assert fvv == pytest.approx(1_000_000, abs=0.01)
    assert goal_seek_contribution(1000, 5000, 10, 0.05) == 0.0
    c_real = goal_seek_contribution(500_000, 0, 20, 0.07, inflation_rate=0.03, adjust_target_for_inflation=True)
    real = compute_investment_growth(0, c_real, 12, annual_return=0.07, years=20, inflation_rate=0.03).summary
    assert real.final_real_value == pytest.approx(500_000, rel=1e-6)


def test_goal_seek_return_converges_or_none():
    r = goal_seek_return(500_000, 50_000, 500, 15)
    fvv = compute_investment_growth(50_000, 500, 12, annual_return=r, years=15).summary.final_nominal_value
    assert fvv == pytest.approx(500_000, abs=0.01)
    assert goal_seek_return(1e9, 100, 10, 5) is None                     # old code returned 200%
    assert goal_seek_return(1000, 0, 0, 5) is None


def test_investment_validation():
    with pytest.raises(ValueError):
        compute_investment_growth(1000, 10, contribution_timing="middle")
    with pytest.raises(ValueError):
        compute_investment_growth(1000, 10, tax_rate_on_gains=1.0)


# ---------------------------------------------------------------- loan comparison
def test_compare_two_loans_breakeven_and_fee_apr():
    c = fc.compare_two_loans(300_000, 0.065, 30, 0, 300_000, 0.06, 30, 4_000)
    assert c.breakeven_months == pytest.approx(4_000 / (c.loan_a_pmt - c.loan_b_pmt), abs=0.05)
    assert c.loan_b_apr_with_fees > 0.06 and c.loan_a_apr_with_fees is None
