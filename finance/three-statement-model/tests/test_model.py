"""Forecast engine: linkages, schedules, revolver, circularity, scenarios."""
import math

import pytest

import model as M
from tests.conftest import TICKERS, build


@pytest.mark.parametrize("t", TICKERS)
@pytest.mark.parametrize("scen", ["Base", "Bull", "Bear"])
def test_balances_and_ties_every_ticker_and_scenario(hist, base_models, t, scen):
    m = build(hist[t], M.scenario_drivers(base_models[t].drivers, scen))
    assert m.verify_balance_checks()["all_balanced"]
    for y in m.forecast_years:
        assert abs(y.balance_check) < 1e-6
    ties = m.integrity_checks()
    assert ties.abs().to_numpy().max() < 1e-6


@pytest.mark.parametrize("t", TICKERS)
def test_cash_comes_from_cash_flow_statement(base_models, t):
    m = base_models[t]
    prev = m.historical_years[-1]
    for y in m.forecast_years:
        assert y.beginning_cash == pytest.approx(prev.cash)
        assert y.cash == pytest.approx(prev.cash + y.cfo + y.cfi + y.cff)
        prev = y


def test_retained_earnings_and_equity_roll_forward(base_models):
    m = base_models["AAPL"]
    prev = m.historical_years[-1]
    for y in m.forecast_years:
        assert y.retained_earnings == pytest.approx(prev.retained_earnings + y.ni_common + y.cff_dividends_paid)
        assert y.treasury_stock == pytest.approx(prev.treasury_stock - y.cff_share_buybacks)
        assert y.common_stock == prev.common_stock and y.aoci_other == prev.aoci_other
        assert y.cff_share_buybacks < 0 and y.cff_dividends_paid < 0
        prev = y


def test_working_capital_days_bases_and_signs(base_models):
    m = base_models["KO"]
    d = m.drivers
    prev = m.historical_years[-1]
    for i, y in enumerate(m.forecast_years):
        assert y.accounts_receivable == pytest.approx(d.dso[i] / 365 * y.revenue)
        assert y.inventory == pytest.approx(d.dio[i] / 365 * y.cogs)
        assert y.accounts_payable == pytest.approx(d.dpo[i] / 365 * y.cogs)
        assert y.cfo_change_ar == pytest.approx(prev.accounts_receivable - y.accounts_receivable)   # AR up = cash down
        assert y.cfo_change_inv == pytest.approx(prev.inventory - y.inventory)
        assert y.cfo_change_ap == pytest.approx(y.accounts_payable - prev.accounts_payable)        # AP up = cash up
        prev = y


def test_higher_dso_reduces_cash_by_the_extra_receivables(hist, base_models):
    d = base_models["KO"].drivers.copy()
    d.dso = [x + 10 for x in d.dso]
    d.interest_calc_method = "beginning"
    d0 = base_models["KO"].drivers.copy()
    d0.interest_calc_method = "beginning"
    a, b = build(hist["KO"], d0), build(hist["KO"], d)
    y0, y1 = a.forecast_years[0], b.forecast_years[0]
    extra_ar = 10 / 365 * y0.revenue
    assert y1.accounts_receivable - y0.accounts_receivable == pytest.approx(extra_ar)
    # first year: cash falls by the extra AR (income statement unchanged with beginning balances)
    assert y1.revolver_draw == 0
    assert y0.cash - y1.cash == pytest.approx(extra_ar, rel=1e-9)


def test_ppe_roll_forward_and_da(base_models):
    m = base_models["T"]
    prev = m.historical_years[-1]
    for i, y in enumerate(m.forecast_years):
        capex = m.drivers.capex_pct_rev[i] * y.revenue
        assert y.da == pytest.approx(m.drivers.da_pct[i] * prev.net_ppe)
        assert y.net_ppe == pytest.approx(prev.net_ppe + capex - y.da)
        assert y.cfi_capex == pytest.approx(-capex)
        prev = y


def test_da_never_exceeds_available_ppe(hist):
    m = build(hist["AAPL"])
    d = m.drivers.copy()
    d.da_pct = [5.0] * 5
    m2 = build(hist["AAPL"], d)
    for y in m2.forecast_years:
        assert y.net_ppe >= -1e-9
    assert m2.verify_balance_checks()["all_balanced"]


def test_tax_never_negative_on_losses(hist, base_models):
    d = M.scenario_drivers(base_models["F"].drivers, "Bear")
    m = build(hist["F"], d)
    losses = [y for y in m.forecast_years if y.ebt < 0]
    assert losses, "the F bear case should produce pre-tax losses"
    for y in losses:
        assert y.tax_expense == 0
        assert y.net_income == pytest.approx(y.ebt)
    for y in m.forecast_years:
        if y.ebt > 0:
            assert y.tax_expense == pytest.approx(y.ebt * d.tax_rate[0])


def test_debt_repayment_capped_at_balance(hist, base_models):
    d = base_models["T"].drivers.copy()
    debt = hist["T"].years[-1].senior_debt
    d.debt_repayment = [debt * 0.6] * 5
    m = build(hist["T"], d)
    assert m.forecast_years[0].senior_debt == pytest.approx(debt * 0.4)
    assert m.forecast_years[1].senior_debt == pytest.approx(0)
    assert all(y.senior_debt >= -1e-9 for y in m.forecast_years)
    assert m.verify_balance_checks()["all_balanced"]


def test_revolver_draws_to_minimum_cash_and_repays(hist, base_models):
    m = build(hist["AAPL"], M.revolver_stress(base_models["AAPL"].drivers))
    f = m.forecast_years
    assert f[0].revolver_draw > 0
    assert f[0].cash == pytest.approx(m.drivers.min_cash_balance)
    assert f[0].revolver_debt == pytest.approx(f[0].revolver_draw)
    assert any(y.revolver_repayment > 0 for y in f[1:])
    assert f[-1].revolver_debt == pytest.approx(0, abs=1e-6)
    for y in f:
        assert y.cash >= m.drivers.min_cash_balance - 1e-6
        assert not (y.revolver_draw > 0 and y.revolver_repayment > 0)
        assert y.revolver_debt <= m.drivers.revolver_capacity + 1e-6
    assert f[0].interest_expense_revolver > 0
    assert m.verify_balance_checks()["all_balanced"]
    assert m.warnings() == []


def test_revolver_capacity_cap_and_shortfall_flag(hist, base_models):
    m = build(hist["F"], M.scenario_drivers(base_models["F"].drivers, "Bear"))
    cap = m.drivers.revolver_capacity
    assert max(y.revolver_debt for y in m.forecast_years) == pytest.approx(cap)
    assert any(y.funding_shortfall > 0 for y in m.forecast_years)
    assert any("capacity exhausted" in w for w in m.warnings())
    assert m.verify_balance_checks()["all_balanced"]          # still balances: cash simply goes below minimum


def test_zero_capacity_means_no_revolver(hist, base_models):
    d = M.revolver_stress(base_models["AAPL"].drivers)
    d.revolver_capacity = 0
    m = build(hist["AAPL"], d)
    assert all(y.revolver_debt == 0 for y in m.forecast_years)
    assert m.forecast_years[0].cash < d.min_cash_balance
    assert m.verify_balance_checks()["all_balanced"]


def test_circularity_converges_to_a_fixed_point(base_models):
    m = base_models["AAPL"]
    prev = m.historical_years[-1]
    d = m.drivers
    for i, y in enumerate(m.forecast_years):
        assert y.circularity_converged and not y.breaker_tripped
        avg_cash = (prev.cash + prev.st_investments + y.cash + y.st_investments) / 2
        assert y.interest_income == pytest.approx(d.cash_interest_rate[i] * avg_cash, rel=1e-9)
        assert y.interest_expense_term == pytest.approx(d.debt_interest_rate[i] * (prev.senior_debt + y.senior_debt) / 2)
        assert 2 <= y.circularity_iterations <= 20
        prev = y


def test_beginning_balance_method_and_circuit_breaker(hist, base_models):
    for setting in ("beginning", "breaker"):
        d = base_models["AAPL"].drivers.copy()
        if setting == "beginning":
            d.interest_calc_method = "beginning"
        else:
            d.circuit_breaker = True
        m = build(hist["AAPL"], d)
        prev = m.historical_years[-1]
        for i, y in enumerate(m.forecast_years):
            assert y.interest_income == pytest.approx(d.cash_interest_rate[i] * (prev.cash + prev.st_investments))
            assert y.circularity_iterations == 1
            prev = y
        assert m.verify_balance_checks()["all_balanced"]


def test_breaker_trips_when_iteration_cannot_converge(hist, base_models):
    d = base_models["AAPL"].drivers.copy()
    d.max_iterations = 1
    m = build(hist["AAPL"], d)
    assert all(y.breaker_tripped for y in m.forecast_years)
    assert any("circuit breaker" in w for w in m.warnings())
    assert m.verify_balance_checks()["all_balanced"]


def test_scenario_deltas_are_applied(base_models):
    b = base_models["AAPL"].drivers
    bull, bear = M.scenario_drivers(b, "Bull"), M.scenario_drivers(b, "Bear")
    for i in range(5):
        assert bull.revenue_growth[i] == pytest.approx(b.revenue_growth[i] + 0.03)
        assert bear.revenue_growth[i] == pytest.approx(b.revenue_growth[i] - 0.05)
        assert bear.gross_margin[i] == pytest.approx(b.gross_margin[i] - 0.02)
        assert bear.dso[i] == pytest.approx(b.dso[i] + 5)
        assert bull.dpo[i] == pytest.approx(b.dpo[i] + 3)
        assert bear.debt_interest_rate[i] == pytest.approx(b.debt_interest_rate[i] + 0.015)
    assert M.scenario_drivers(b, "Base").revenue_growth == b.revenue_growth
    assert b.revenue_growth == base_models["AAPL"].drivers.revenue_growth       # base not mutated


def test_scenario_ordering(hist, base_models):
    ms = M.run_scenarios(hist["MSFT"].years, base_models["MSFT"].drivers, "MSFT", "MSFT")
    comp = M.scenario_comparison(ms)
    assert comp.loc["Bull", "Year-5 revenue"] > comp.loc["Base", "Year-5 revenue"] > comp.loc["Bear", "Year-5 revenue"]
    assert comp["Max balance-check error"].max() < 1e-6


def test_driver_validation():
    d = M.ForecastDrivers()
    d.dso = [1, 2]
    with pytest.raises(ValueError):
        d.validate()
    d = M.ForecastDrivers()
    d.tax_rate = [-0.1] * 5
    with pytest.raises(ValueError):
        d.validate()
    d = M.ForecastDrivers()
    d.revenue_growth = [float("nan")] * 5
    with pytest.raises(ValueError):
        d.validate()


def test_needs_three_historical_years(hist):
    with pytest.raises(ValueError):
        M.ThreeStatementModel(hist["AAPL"].years[:2])


def test_forecast_labels(base_models):
    assert base_models["AAPL"].forecast_labels() == ["2026E", "2027E", "2028E", "2029E", "2030E"]
    assert base_models["MSFT"].forecast_labels()[0] == "2027E"
