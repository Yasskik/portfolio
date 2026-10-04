"""
Unit tests for dcf.py core valuation engine.
"""

import io
import math
import openpyxl
import pytest

from dcf import (
    CashFlowProjection,
    DataUnavailableError,
    DCFAssumptions,
    DCFResult,
    HistoricalFinancials,
    SensitivityMatrix,
    ValuationSummary,
    WACCInputs,
    WACCResult,
    build_valuation_bridge,
    calculate_terminal_value_exit_multiple,
    calculate_terminal_value_ggm,
    calculate_wacc,
    fetch_company_data,
    generate_sensitivity_table,
    get_fallback_company_data,
    project_cash_flows,
    run_dcf,
)
from excel_export import export_to_excel


# ==============================================================================
# WACC Tests
# ==============================================================================

def test_wacc_standard_market_weights():
    """Verify CAPM cost of equity, after-tax debt, and market-weighted WACC."""
    inputs = WACCInputs(
        risk_free_rate=0.04,          # 4.0%
        beta=1.2,                     # Beta = 1.2
        equity_risk_premium=0.055,    # ERP = 5.5% -> Ke = 4% + 1.2*5.5% = 10.6%
        cost_of_debt=0.05,            # 5.0%
        tax_rate=0.20,                # 20.0% -> Kd_after_tax = 4.0%
        market_cap=800_000_000.0,     # E = 800M (80%)
        total_debt=200_000_000.0      # D = 200M (20%)
    )
    result = calculate_wacc(inputs)

    assert math.isclose(result.cost_of_equity, 0.106, rel_tol=1e-5)
    assert math.isclose(result.pre_tax_cost_of_debt, 0.05, rel_tol=1e-5)
    assert math.isclose(result.after_tax_cost_of_debt, 0.04, rel_tol=1e-5)
    assert math.isclose(result.weight_equity, 0.80, rel_tol=1e-5)
    assert math.isclose(result.weight_debt, 0.20, rel_tol=1e-5)
    # WACC = 0.80 * 0.106 + 0.20 * 0.04 = 0.0848 + 0.0080 = 0.0928 (9.28%)
    assert math.isclose(result.wacc, 0.0928, rel_tol=1e-5)


def test_wacc_custom_overrides():
    """Verify manual equity and debt weight overrides."""
    inputs = WACCInputs(
        risk_free_rate=0.03,
        beta=1.0,
        equity_risk_premium=0.06,    # Ke = 3% + 6% = 9%
        cost_of_debt=0.04,
        tax_rate=0.25,               # Kd_after_tax = 3%
        market_cap=1_000_000_000.0,
        total_debt=1_000_000_000.0,
        weight_equity_override=0.60,
        weight_debt_override=0.40
    )
    result = calculate_wacc(inputs)
    assert math.isclose(result.weight_equity, 0.60, rel_tol=1e-5)
    assert math.isclose(result.weight_debt, 0.40, rel_tol=1e-5)
    # WACC = 0.60 * 0.09 + 0.40 * 0.03 = 0.054 + 0.012 = 0.066 (6.6%)
    assert math.isclose(result.wacc, 0.066, rel_tol=1e-5)


# ==============================================================================
# Cash Flow Projections & FCFF Tests
# ==============================================================================

def test_project_cash_flows_logic():
    """Verify 5-year compounding revenue, NOPAT, NWC change, and FCFF build."""
    base_revenue = 1000.0
    base_nwc = 100.0
    wacc = 0.10

    assumptions = DCFAssumptions(
        projection_years=5,
        revenue_growth_rates=[0.10] * 5,   # 10% per year
        ebit_margins=[0.20] * 5,           # 20% margin
        tax_rates=[0.25] * 5,              # 25% tax
        capex_pcts=[0.05] * 5,             # 5% of rev
        da_pcts=[0.04] * 5,                # 4% of rev
        nwc_pcts=[0.10] * 5,               # 10% of rev
        mid_year_convention=False
    )

    proj = project_cash_flows(base_revenue, base_nwc, assumptions, wacc)

    # Check Year 1:
    # Rev = 1000 * 1.10 = 1100
    assert math.isclose(proj.revenue[1], 1100.0, rel_tol=1e-5)
    # EBIT = 1100 * 0.20 = 220
    assert math.isclose(proj.ebit[1], 220.0, rel_tol=1e-5)
    # NOPAT = 220 * (1 - 0.25) = 165
    assert math.isclose(proj.nopat[1], 165.0, rel_tol=1e-5)
    # D&A = 1100 * 0.04 = 44
    assert math.isclose(proj.da[1], 44.0, rel_tol=1e-5)
    # Capex = 1100 * 0.05 = 55
    assert math.isclose(proj.capex[1], 55.0, rel_tol=1e-5)
    # NWC = 1100 * 0.10 = 110
    assert math.isclose(proj.nwc[1], 110.0, rel_tol=1e-5)
    # NWC change = 110 - 100 = 10
    assert math.isclose(proj.nwc_change[1], 10.0, rel_tol=1e-5)
    # FCFF = NOPAT (165) + D&A (44) - Capex (55) - NWC change (10) = 144.0
    assert math.isclose(proj.fcff[1], 144.0, rel_tol=1e-5)

    # Check end-of-year discount factor for Year 1: 1 / (1 + 0.10)^1 = 1 / 1.10 = ~0.90909
    assert math.isclose(proj.discount_factor[1], 1.0 / 1.10, rel_tol=1e-5)
    assert math.isclose(proj.pv_fcff[1], 144.0 / 1.10, rel_tol=1e-5)


def test_mid_year_discount_period():
    """Verify mid-year convention discount periods (0.5, 1.5, 2.5, 3.5, 4.5)."""
    assumptions = DCFAssumptions(mid_year_convention=True)
    proj = project_cash_flows(100.0, 10.0, assumptions, 0.08)
    expected_periods = [0.0, 0.5, 1.5, 2.5, 3.5, 4.5]
    for actual, exp in zip(proj.discount_period, expected_periods):
        assert math.isclose(actual, exp, abs_tol=1e-5)


# ==============================================================================
# Terminal Value & Valuation Bridge Tests
# ==============================================================================

def test_terminal_value_gordon_growth():
    """Verify Gordon Growth Model calculations."""
    final_fcf = 100.0
    wacc = 0.10
    g = 0.02
    tv, pv_tv = calculate_terminal_value_ggm(final_fcf, wacc, g, projection_years=5)

    # TV = 100 * 1.02 / (0.10 - 0.02) = 102 / 0.08 = 1275.0
    assert math.isclose(tv, 1275.0, rel_tol=1e-5)
    # PV(TV) = 1275 / (1.10)^5 = 1275 / 1.61051 = ~791.67
    assert math.isclose(pv_tv, 1275.0 / (1.10 ** 5), rel_tol=1e-5)


def test_terminal_value_ggm_safeguard():
    """WACC <= g makes the Gordon formula meaningless: return NaN instead of a fake number."""
    tv, pv_tv = calculate_terminal_value_ggm(100.0, 0.02, 0.025, projection_years=5)
    assert math.isnan(tv) and math.isnan(pv_tv)
    tv, pv_tv = calculate_terminal_value_ggm(100.0, 0.025, 0.025, projection_years=5)
    assert math.isnan(tv) and math.isnan(pv_tv)


def test_terminal_value_exit_multiple():
    """Verify Exit Multiple terminal value calculations."""
    final_ebitda = 200.0
    multiple = 12.0
    wacc = 0.09
    tv, pv_tv = calculate_terminal_value_exit_multiple(final_ebitda, multiple, wacc, projection_years=5)

    # TV = 200 * 12 = 2400.0
    assert math.isclose(tv, 2400.0, rel_tol=1e-5)
    # PV(TV) = 2400 / (1.09)^5
    assert math.isclose(pv_tv, 2400.0 / (1.09 ** 5), rel_tol=1e-5)


def test_valuation_bridge_calculation():
    """Verify EV -> Equity Value -> Implied Share Price bridge."""
    bridge = build_valuation_bridge(
        method_name="Gordon Growth",
        pv_fcf_sum=500.0,
        terminal_val=2000.0,
        pv_terminal_val=1200.0,
        total_cash=100.0,
        total_debt=300.0,
        shares_outstanding=50.0,
        current_price=25.0
    )

    # EV = 500 + 1200 = 1700
    assert math.isclose(bridge.enterprise_value, 1700.0, rel_tol=1e-5)
    # Net Debt = 300 - 100 = 200
    assert math.isclose(bridge.net_debt, 200.0, rel_tol=1e-5)
    # Equity Value = 1700 - 200 = 1500
    assert math.isclose(bridge.equity_value, 1500.0, rel_tol=1e-5)
    # Implied Share Price = 1500 / 50 = 30.0
    assert math.isclose(bridge.implied_share_price, 30.0, rel_tol=1e-5)
    # Upside % = (30 - 25) / 25 = 20.0%
    assert math.isclose(bridge.upside_downside_pct, 20.0, rel_tol=1e-5)


# ==============================================================================
# Sensitivity Analysis Tests
# ==============================================================================

def test_sensitivity_table_monotonicity():
    """
    Verify 2D sensitivity table monotonicity:
      - Higher WACC leads to lower implied price (holding g constant)
      - Higher growth rate leads to higher implied price (holding WACC constant)
    """
    comp = get_fallback_company_data("AAPL")
    assump = DCFAssumptions()
    wacc_inputs = WACCInputs(
        risk_free_rate=0.04,
        beta=1.1,
        equity_risk_premium=0.055,
        cost_of_debt=0.05,
        tax_rate=0.21,
        market_cap=comp.market_cap,
        total_debt=comp.total_debt
    )

    sens = generate_sensitivity_table(
        comp.revenue[-1],
        comp.revenue[-1] * 0.08,
        assump,
        comp,
        wacc_inputs,
        method="ggm",
        wacc_steps=[0.08, 0.09, 0.10],
        param_steps=[0.02, 0.025, 0.03]
    )

    # Dimensions
    assert len(sens.table) == 3
    assert len(sens.table[0]) == 3

    # Check that as WACC increases along columns, price decreases
    for c in range(3):
        assert sens.table[0][c] > sens.table[1][c] > sens.table[2][c]

    # Check that as Growth (g) increases along rows, price increases
    for r in range(3):
        assert sens.table[r][0] < sens.table[r][1] < sens.table[r][2]


# ==============================================================================
# Fallback Financial Profile Tests
# ==============================================================================

def test_fallback_company_profiles():
    """Offline snapshot tickers load real data; unknown tickers raise instead of inventing data."""
    for ticker in ["AAPL", "MSFT", "KO"]:
        data = get_fallback_company_data(ticker)
        assert data.ticker == ticker
        assert len(data.years) == len(data.revenue) == len(data.historical_fcff) >= 3
        assert data.current_price > 0
        assert data.shares_outstanding > 0
        assert data.as_of
        for fcff in data.historical_fcff:
            assert isinstance(fcff, float)
    with pytest.raises(DataUnavailableError):
        get_fallback_company_data("CUSTOM")


# ==============================================================================
# Full Pipeline & Excel Export Tests
# ==============================================================================

def test_full_dcf_pipeline():
    """Verify run_dcf returns a fully populated DCFResult."""
    comp = get_fallback_company_data("MSFT")
    assump = DCFAssumptions()
    wacc_in = WACCInputs(
        risk_free_rate=0.042,
        beta=comp.beta,
        equity_risk_premium=0.055,
        cost_of_debt=0.048,
        tax_rate=0.21,
        market_cap=comp.market_cap,
        total_debt=comp.total_debt
    )

    dcf_res = run_dcf(comp, assump, wacc_in)
    assert dcf_res.wacc_result.wacc > 0
    assert dcf_res.projections.cumulative_pv_fcff > 0
    assert dcf_res.ggm_valuation.implied_share_price > 0
    assert dcf_res.exit_valuation.implied_share_price > 0
    assert len(dcf_res.ggm_sensitivity.table) == 5
    assert len(dcf_res.exit_sensitivity.table) == 5


def test_excel_export_formulas_and_structure():
    """
    Verify openpyxl creates an authentic workbook with all 3 worksheets,
    valid Excel formulas, and standard financial number formatting.
    """
    comp = get_fallback_company_data("AAPL")
    assump = DCFAssumptions()
    wacc_in = WACCInputs(
        risk_free_rate=0.0425,
        beta=comp.beta,
        equity_risk_premium=0.055,
        cost_of_debt=0.045,
        tax_rate=0.21,
        market_cap=comp.market_cap,
        total_debt=comp.total_debt
    )

    dcf_res = run_dcf(comp, assump, wacc_in)
    excel_bytes = export_to_excel(dcf_res)
    assert len(excel_bytes) > 5000

    # Load and inspect the generated workbook in memory
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=False)
    sheet_names = wb.sheetnames
    assert sheet_names == ["Summary", "Assumptions", "Historicals", "WACC", "DCF", "Sensitivity"]

    ws = wb["DCF"]
    assert ws["C7"].value == "=B7*(1+C6)"             # revenue grows off prior year
    assert ws["C19"].value == "=C11+C13-C15-C18"       # FCFF = NOPAT + D&A - capex - dNWC
    assert ws["B26"].value.startswith("=SUM(")
    assert ws["B43"].value == "=B41/B42"               # implied price
    wacc_ws = wb["WACC"]
    assert wacc_ws["B8"].value == "=B5+B6*B7"          # CAPM
    assert wacc_ws["B22"].value == "=B19*B8+B20*B13"   # WACC
    assert wb["Sensitivity"]["D8"].value.startswith("=IF(")
