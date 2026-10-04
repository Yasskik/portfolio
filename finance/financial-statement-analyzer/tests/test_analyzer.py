"""
Unit Tests for Financial Statement Analyzer (tests/test_analyzer.py)
-------------------------------------------------------------------
Verifies ratio accuracy, mathematical identities (DuPont), credit models (Altman Z,
Piotroski F), common-size & horizontal analysis, template loading, Excel export
live formulas, and graceful handling of missing data.
"""

import io
import math
import numpy as np
import pandas as pd
import pytest
import openpyxl

from analyzer import (
    FinancialData,
    FinancialAnalyzer,
    _safe_div,
    _safe_float,
)
from excel_export import export_analysis_to_excel
from report_export import generate_markdown_report, generate_pdf_report


# =====================================================================
# Fixtures: Deterministic Synthetic Company Data
# =====================================================================

@pytest.fixture
def sample_financial_data():
    """Returns a 4-year clean synthetic financial dataset for testing."""
    years = ["2021", "2022", "2023", "2024"]

    income_df = pd.DataFrame({
        "2021": [1000.0, 600.0, 400.0, 200.0, 200.0, 20.0, 180.0, 36.0, 144.0, 1.44, 100.0],
        "2022": [1200.0, 700.0, 500.0, 220.0, 280.0, 20.0, 260.0, 52.0, 208.0, 2.08, 100.0],
        "2023": [1400.0, 800.0, 600.0, 250.0, 350.0, 25.0, 325.0, 65.0, 260.0, 2.60, 100.0],
        "2024": [1600.0, 900.0, 700.0, 280.0, 420.0, 20.0, 400.0, 80.0, 320.0, 3.20, 100.0],
    }, index=[
        "Total Revenue", "Cost Of Revenue", "Gross Profit", "Operating Expense",
        "Operating Income", "Interest Expense", "Pretax Income", "Tax Provision",
        "Net Income", "Diluted EPS", "Diluted Average Shares"
    ])

    balance_df = pd.DataFrame({
        "2021": [150.0, 50.0, 120.0, 80.0, 400.0, 600.0, 1000.0, 100.0, 50.0, 200.0, 250.0, 300.0, 450.0, 350.0, 550.0, 200.0],
        "2022": [180.0, 60.0, 140.0, 90.0, 470.0, 680.0, 1150.0, 115.0, 50.0, 220.0, 250.0, 300.0, 470.0, 480.0, 680.0, 250.0],
        "2023": [220.0, 80.0, 160.0, 100.0, 560.0, 740.0, 1300.0, 125.0, 50.0, 240.0, 230.0, 280.0, 480.0, 620.0, 820.0, 320.0],
        "2024": [280.0, 100.0, 180.0, 110.0, 670.0, 830.0, 1500.0, 140.0, 50.0, 260.0, 200.0, 250.0, 500.0, 780.0, 1000.0, 410.0],
    }, index=[
        "Cash And Cash Equivalents", "Other Short Term Investments", "Accounts Receivable",
        "Inventory", "Current Assets", "Net PPE", "Total Assets", "Accounts Payable",
        "Current Debt", "Current Liabilities", "Long Term Debt", "Total Debt",
        "Total Liabilities Net Minority Interest", "Retained Earnings", "Stockholders Equity",
        "Working Capital"
    ])

    cashflow_df = pd.DataFrame({
        "2021": [180.0, -80.0, 100.0, -90.0, -60.0, 40.0, -30.0],
        "2022": [230.0, -90.0, 140.0, -100.0, -70.0, 45.0, -40.0],
        "2023": [290.0, -100.0, 190.0, -120.0, -80.0, 50.0, -50.0],
        "2024": [360.0, -110.0, 250.0, -130.0, -90.0, 60.0, -60.0],
    }, index=[
        "Operating Cash Flow", "Capital Expenditure", "Free Cash Flow",
        "Investing Cash Flow", "Financing Cash Flow", "Depreciation And Amortization",
        "Cash Dividends Paid"
    ])

    return FinancialData(
        symbol="TEST",
        company_name="Test Enterprise Corp",
        income_statement=income_df,
        balance_sheet=balance_df,
        cash_flow=cashflow_df,
        currency="USD",
        market_cap=3000.0
    )


# =====================================================================
# Tests: Math Helpers & Missing Data Handling
# =====================================================================

def test_safe_div():
    """Verify safe division handles zero denominators, inf, and nan gracefully."""
    assert _safe_div(10.0, 2.0) == 5.0
    assert _safe_div(10.0, 0.0) is None
    assert _safe_div(None, 5.0) is None
    assert _safe_div(5.0, None) is None
    assert _safe_div(np.nan, 2.0) is None
    assert _safe_div(2.0, np.nan) is None
    assert _safe_div(10.0, 0.0, default=0.0) == 0.0


def test_safe_float():
    """Verify safe float conversion."""
    assert _safe_float(42) == 42.0
    assert _safe_float("3.14") == 3.14
    assert _safe_float(None) is None
    assert _safe_float("invalid") is None
    assert _safe_float(np.nan) is None
    assert _safe_float(float("inf")) is None


def test_missing_data_graceful_handling():
    """Ensure missing statements or missing items return None/NaN, never invent numbers."""
    empty_data = FinancialData(
        symbol="EMPTY",
        company_name="Empty Corp",
        income_statement=pd.DataFrame(),
        balance_sheet=pd.DataFrame(),
        cash_flow=pd.DataFrame(),
    )
    analyzer = FinancialAnalyzer(empty_data)
    liq = analyzer.calculate_liquidity_ratios()
    assert liq.empty or liq.isna().all().all()

    health = analyzer.generate_health_report()
    assert health["overall_status"] == "Insufficient Data"


# =====================================================================
# Tests: Core Ratio Categories
# =====================================================================

def test_liquidity_ratios(sample_financial_data):
    """Test Current, Quick, and Cash Ratios."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    liq = analyzer.calculate_liquidity_ratios()

    # 2024: Current Assets = 670, Current Liabilities = 260
    expected_cr = 670.0 / 260.0
    assert pytest.approx(liq.loc["Current Ratio", "2024"], rel=1e-3) == expected_cr

    # 2024 Quick Ratio: (Cash 280 + STI 100 + Rec 180) / CL 260 = 560 / 260
    # Secondary check: (CA 670 - Inv 110) / CL 260 = 560 / 260
    expected_qr = 560.0 / 260.0
    assert pytest.approx(liq.loc["Quick Ratio", "2024"], rel=1e-3) == expected_qr

    # 2024 Cash Ratio: (Cash 280 + STI 100) / 260 = 380 / 260
    expected_cash_r = 380.0 / 260.0
    assert pytest.approx(liq.loc["Cash Ratio", "2024"], rel=1e-3) == expected_cash_r


def test_profitability_ratios(sample_financial_data):
    """Test Gross, Operating, Net Margin, ROA, ROE, ROIC."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    prof = analyzer.calculate_profitability_ratios()

    # 2024: Rev = 1600, GP = 700, OpInc = 420, NI = 320, Assets = 1500, Equity = 1000
    assert pytest.approx(prof.loc["Gross Margin", "2024"], rel=1e-3) == 700.0 / 1600.0
    assert pytest.approx(prof.loc["Operating Margin", "2024"], rel=1e-3) == 420.0 / 1600.0
    assert pytest.approx(prof.loc["Net Profit Margin", "2024"], rel=1e-3) == 320.0 / 1600.0
    assert pytest.approx(prof.loc["Return on Assets (ROA)", "2024"], rel=1e-3) == 320.0 / 1500.0
    assert pytest.approx(prof.loc["Return on Equity (ROE)", "2024"], rel=1e-3) == 320.0 / 1000.0

    # ROIC: NOPAT / Invested Capital
    # Tax Rate = 80 / 400 = 20%. NOPAT = 420 * (1 - 0.20) = 336
    # Invested Capital = Total Debt 250 + Equity 1000 = 1250
    expected_roic = 336.0 / 1250.0
    assert pytest.approx(prof.loc["Return on Invested Capital (ROIC)", "2024"], rel=1e-3) == expected_roic


def test_solvency_ratios(sample_financial_data):
    """Test Debt-to-Equity, Debt-to-Assets, Interest Coverage."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    solv = analyzer.calculate_solvency_ratios()

    # 2024: Debt = 250, Equity = 1000, Assets = 1500, EBIT = 420, Int = 20
    assert pytest.approx(solv.loc["Debt-to-Equity", "2024"], rel=1e-3) == 250.0 / 1000.0
    assert pytest.approx(solv.loc["Debt-to-Assets", "2024"], rel=1e-3) == 250.0 / 1500.0
    assert pytest.approx(solv.loc["Financial Leverage (Multiplier)", "2024"], rel=1e-3) == 1500.0 / 1000.0
    assert pytest.approx(solv.loc["Interest Coverage", "2024"], rel=1e-3) == 420.0 / 20.0


def test_efficiency_and_working_capital(sample_financial_data):
    """Test Asset Turnover, Inventory Turnover, DSO, DIO, DPO, CCC."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    eff = analyzer.calculate_efficiency_ratios()

    # 2024: Rev = 1600, COGS = 900, Assets = 1500, Inv = 110, Rec = 180, AP = 140
    expected_at = 1600.0 / 1500.0
    expected_inv_t = 900.0 / 110.0
    expected_dso = (180.0 / 1600.0) * 365.0
    expected_dio = (110.0 / 900.0) * 365.0
    expected_dpo = (140.0 / 900.0) * 365.0
    expected_ccc = expected_dio + expected_dso - expected_dpo

    assert pytest.approx(eff.loc["Asset Turnover", "2024"], rel=1e-3) == expected_at
    assert pytest.approx(eff.loc["Inventory Turnover", "2024"], rel=1e-3) == expected_inv_t
    assert pytest.approx(eff.loc["Days Sales Outstanding (DSO)", "2024"], rel=1e-3) == expected_dso
    assert pytest.approx(eff.loc["Days Inventory Outstanding (DIO)", "2024"], rel=1e-3) == expected_dio
    assert pytest.approx(eff.loc["Days Payable Outstanding (DPO)", "2024"], rel=1e-3) == expected_dpo
    assert pytest.approx(eff.loc["Cash Conversion Cycle (CCC)", "2024"], rel=1e-3) == expected_ccc


def test_cash_flow_quality(sample_financial_data):
    """Test Operating Cash Flow / Net Income, FCF, and Sloan Accruals."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    cfq = analyzer.calculate_cash_flow_quality()

    # 2024: OCF = 360, CapEx = -110, FCF = 250, NI = 320, Rev = 1600, Assets = 1500
    assert pytest.approx(cfq.loc["Operating Cash Flow / Net Income", "2024"], rel=1e-3) == 360.0 / 320.0
    assert pytest.approx(cfq.loc["Free Cash Flow", "2024"], rel=1e-3) == 250.0
    assert pytest.approx(cfq.loc["FCF Margin", "2024"], rel=1e-3) == 250.0 / 1600.0

    # Sloan Accrual: (NI 320 - CFO 360) / Assets 1500 = -40 / 1500
    assert pytest.approx(cfq.loc["Sloan Accrual Ratio", "2024"], rel=1e-3) == (320.0 - 360.0) / 1500.0


def test_growth_metrics(sample_financial_data):
    """Test YoY growth rates."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    growth = analyzer.calculate_growth_metrics()

    # Base year 2021 must be None
    assert math.isnan(growth.loc["Revenue YoY Growth", "2021"]) or growth.loc["Revenue YoY Growth", "2021"] is None
    # 2022 vs 2021: Rev grew from 1000 to 1200 (+20.0%)
    assert pytest.approx(growth.loc["Revenue YoY Growth", "2022"], rel=1e-3) == 0.20
    # 2024 vs 2023: NI grew from 260 to 320
    assert pytest.approx(growth.loc["Net Income YoY Growth", "2024"], rel=1e-3) == (320.0 - 260.0) / 260.0


# =====================================================================
# Tests: Mathematical Identities (DuPont 3-Step & 5-Step)
# =====================================================================

def test_dupont_3_step_mathematical_identity(sample_financial_data):
    """
    Verify DuPont 3-Step:
    ROE = Net Profit Margin * Asset Turnover * Financial Leverage
    Product must identically equal Reported ROE across every fiscal year.
    """
    analyzer = FinancialAnalyzer(sample_financial_data)
    dupont = analyzer.calculate_dupont_analysis()["three_step"]

    for y in sample_financial_data.years:
        npm = dupont.loc["Net Profit Margin", y]
        at = dupont.loc["Asset Turnover", y]
        fl = dupont.loc["Financial Leverage", y]
        calc_roe = dupont.loc["3-Step DuPont ROE", y]
        reported_roe = dupont.loc["Actual Reported ROE", y]

        assert pytest.approx(npm * at * fl, rel=1e-5) == calc_roe
        assert pytest.approx(calc_roe, rel=1e-5) == reported_roe


def test_dupont_5_step_mathematical_identity(sample_financial_data):
    """
    Verify DuPont 5-Step:
    ROE = Tax Burden * Interest Burden * Operating Margin * Asset Turnover * Financial Leverage
    Product must identically equal Reported ROE across every fiscal year.
    """
    analyzer = FinancialAnalyzer(sample_financial_data)
    dupont = analyzer.calculate_dupont_analysis()["five_step"]

    for y in sample_financial_data.years:
        tb = dupont.loc["Tax Burden (NI / EBT)", y]
        ib = dupont.loc["Interest Burden (EBT / EBIT)", y]
        om = dupont.loc["Operating Margin (EBIT / Rev)", y]
        at = dupont.loc["Asset Turnover (Rev / Assets)", y]
        fl = dupont.loc["Financial Leverage (Assets / Eq)", y]
        calc_roe = dupont.loc["5-Step DuPont ROE", y]
        reported_roe = dupont.loc["Actual Reported ROE", y]

        product = tb * ib * om * at * fl
        assert pytest.approx(product, rel=1e-5) == calc_roe
        assert pytest.approx(calc_roe, rel=1e-5) == reported_roe


# =====================================================================
# Tests: Scoring Models (Altman Z & Piotroski F)
# =====================================================================

def test_altman_z_score_calculation_and_zones(sample_financial_data):
    """Verify Altman Z-score components and Zone classifications."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    altman = analyzer.calculate_altman_z_score()

    # 2024 calculations:
    # Assets = 1500, WC = 410, RE = 780, EBIT = 420, MktCap = 3000, Liab = 500, Rev = 1600
    x1 = 410.0 / 1500.0
    x2 = 780.0 / 1500.0
    x3 = 420.0 / 1500.0
    x4 = 3000.0 / 500.0  # uses market cap
    x5 = 1600.0 / 1500.0

    expected_z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 0.999 * x5
    actual_z = altman.loc["Altman Z-Score", "2024"]

    assert pytest.approx(actual_z, rel=1e-3) == expected_z
    assert actual_z > 2.99
    assert altman.loc["Zone (Original)", "2024"] == "Safe Zone"


def test_piotroski_f_score_all_criteria(sample_financial_data):
    """Verify all 9 Piotroski F-score criteria on expanding company."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    f_res = analyzer.calculate_piotroski_f_score()

    scores = f_res["scores"]
    # ROA and turnover need beginning-of-year assets, so the first two years can't be fully scored
    assert scores["2021"] is None and scores["2022"] is None
    for y in ["2023", "2024"]:
        assert scores[y] >= 7
        assert "Strong" in f_res["interpretations"][y]


# =====================================================================
# Tests: Common-Size & Horizontal Analysis
# =====================================================================

def test_common_size_and_horizontal(sample_financial_data):
    """Verify vertical common size (% of revenue, % of assets) and horizontal base indexing."""
    analyzer = FinancialAnalyzer(sample_financial_data)

    # Vertical
    cs = analyzer.calculate_common_size()
    cs_inc = cs["income_statement"]
    cs_bs = cs["balance_sheet"]

    # Revenue must be exactly 100% in vertical income statement
    assert pytest.approx(cs_inc.loc["Total Revenue", "2024"], rel=1e-3) == 100.0
    # Total assets must be exactly 100% in vertical balance sheet
    assert pytest.approx(cs_bs.loc["Total Assets", "2024"], rel=1e-3) == 100.0

    # Horizontal
    horiz = analyzer.calculate_horizontal_analysis()
    inc_base = horiz["income_statement"]["indexed"]
    # Base year 2021 must be 100%
    assert pytest.approx(inc_base.loc["Total Revenue", "2021"], rel=1e-3) == 100.0
    # 2024 revenue 1600 / 1000 = 160.0%
    assert pytest.approx(inc_base.loc["Total Revenue", "2024"], rel=1e-3) == 160.0


# =====================================================================
# Tests: Financial Health Report
# =====================================================================

def test_rule_based_health_report(sample_financial_data):
    """Verify rule-based diagnostic flags expected strengths for prime company."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    report = analyzer.generate_health_report()

    assert "Prime" in report["overall_status"] or "Strong" in report["overall_status"]
    assert len(report["strengths"]) >= 4
    assert len(report["red_flags"]) == 0


# =====================================================================
# Tests: Template Files & Excel Export
# =====================================================================

def test_template_loading():
    """Verify Excel and CSV template files load cleanly into FinancialData."""
    data_xl = FinancialData.from_excel_or_csv("templates/financial_statements_template.xlsx", symbol="T-XL")
    analyzer_xl = FinancialAnalyzer(data_xl)
    assert len(data_xl.years) == 4
    assert analyzer_xl.calculate_liquidity_ratios().shape[1] == 4

    data_csv = FinancialData.from_excel_or_csv("templates/financial_statements_template.csv", symbol="T-CSV")
    analyzer_csv = FinancialAnalyzer(data_csv)
    assert len(data_csv.years) == 4
    assert analyzer_csv.calculate_liquidity_ratios().shape[1] == 4


def test_excel_export_live_formulas(sample_financial_data):
    """Verify that export_analysis_to_excel creates valid sheets with live formulas."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    raw_bytes = export_analysis_to_excel(analyzer)
    assert len(raw_bytes) > 5000

    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=False)
    for name in ("Summary", "Income Statement", "Balance Sheet", "Cash Flow", "Ratios", "DuPont",
                 "Altman Z", "Piotroski", "Common-Size", "Notes"):
        assert name in wb.sheetnames

    # Check that ratio cell contains a live formula starting with '='
    ws_ratios = wb["Ratios"]
    current_ratio_formula = str(ws_ratios["B5"].value)
    assert current_ratio_formula.startswith("=")
    assert "Balance Sheet" in current_ratio_formula


def test_report_export_generators(sample_financial_data):
    """Verify Markdown and PDF report generators run and return content."""
    analyzer = FinancialAnalyzer(sample_financial_data)
    md = generate_markdown_report(analyzer)
    assert "Financial Health & Statement Analysis Report" in md
    assert len(md) > 1000

    pdf = generate_pdf_report(analyzer)
    assert len(pdf) > 2000
    assert pdf[:4] == b"%PDF"
