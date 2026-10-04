"""One regression test per bug found when reviewing the first version."""
import math

import pandas as pd
import pytest

import data_loader as dl
import model as M
from tests.conftest import TICKERS, build


# 1. Equity was common stock + RE only: AOCI, treasury stock and NCI were dropped, so the forecast
#    balance sheet was off every year (AAPL -5,571; KO -47,867; T +105,103; F +13,430).
@pytest.mark.parametrize("t", TICKERS)
def test_bug1_forecast_balances_with_full_equity(base_models, t):
    m = base_models[t]
    assert max(abs(y.balance_check) for y in m.forecast_years) < 1e-6
    h = m.historical_years[-1]
    f = m.forecast_years[0]
    assert f.aoci_other == h.aoci_other and f.nci >= 0
    assert f.total_equity == pytest.approx(f.common_stock + f.retained_earnings - f.treasury_stock + f.aoci_other + f.nci)


def test_bug1_treasury_stock_and_nci_carried(base_models):
    ko = base_models["KO"].historical_years[-1]
    assert ko.treasury_stock > 50_000 and ko.nci > 2_000       # KO has large treasury stock and NCI


# 2. Historical equity was forced to TA - TL ("reconciled minority interest/OCI into equity").
def test_bug2_no_hidden_historical_plug():
    df = dl.template_frame(True)
    df.loc["Total shareholders' equity", "FY2025"] -= 7
    h = dl.load_template(df.to_csv().encode(), "x.csv")
    y = h.years[-1]
    assert y.total_shareholders_equity == pytest.approx(df.loc["Total shareholders' equity", "FY2025"])
    assert y.balance_check == pytest.approx(7)
    assert any("Shown, not plugged" in w for w in h.warnings)


# 3. Invented sample data and invented defaults.
def test_bug3_no_fabricated_data_or_silent_defaults(hist):
    assert not hasattr(dl, "SAMPLE_DATASETS")
    for t in TICKERS:
        for y in hist[t].years:
            if math.isnan(y.gross_ppe):
                assert "gross_ppe" in y.missing                 # not net PP&E x 1.5
            else:
                assert y.gross_ppe - y.accumulated_depreciation == pytest.approx(y.net_ppe)
    notes = []
    df = dl.template_frame(True)
    df.loc["Income tax"] = float("nan")
    df.loc["Net income (consolidated)"] = float("nan")
    h = dl.load_template(df.to_csv().encode(), "x.csv")
    M.baseline_drivers(h.years, notes)
    assert any("21% assumed" in n for n in notes)               # the fallback is disclosed


# 4. D&A was subtracted again although Yahoo's COGS/opex already include it; EBITDA came from
#    "Normalized EBITDA"; other non-operating items were missing.
@pytest.mark.parametrize("t", TICKERS)
def test_bug4_income_statement_foots(base_models, t):
    m = base_models[t]
    for y in m.historical_years:
        assert y.ebitda == pytest.approx(y.ebit + y.da)
        assert y.gross_profit - y.sga - y.rd - y.other_opex - y.da == pytest.approx(y.ebit)
    for y in m.forecast_years:
        assert y.ebit == pytest.approx(y.ebitda - y.da)
        assert y.ebt == pytest.approx(y.ebit - y.interest_expense + y.interest_income + y.other_nonop)


# 5. Accumulated depreciation arrived negative from Yahoo.
def test_bug5_accumulated_depreciation_positive(hist):
    for t in TICKERS:
        for y in hist[t].years:
            if not math.isnan(y.accumulated_depreciation):
                assert y.accumulated_depreciation > 0
                assert y.gross_ppe - y.accumulated_depreciation == pytest.approx(y.net_ppe)


def test_bug5_gross_ppe_and_accumulated_depreciation_roll_forward(base_models):
    m = base_models["AAPL"]
    prev = m.historical_years[-1]
    for y in m.forecast_years:
        assert y.gross_ppe == pytest.approx(prev.gross_ppe - y.cfi_capex)
        assert y.accumulated_depreciation == pytest.approx(prev.accumulated_depreciation + y.da)
        assert y.gross_ppe - y.accumulated_depreciation == pytest.approx(y.net_ppe)
        prev = y


# 6. Template rows were matched by substring ("Senior Debt" grabbed "Senior Debt Issuance") and
#    dividends were not read (payout fell back to 15%).
def test_bug6_template_debt_and_dividends_read():
    h = dl.load_template((dl.TEMPLATE_DIR / "sample_historical.csv").read_bytes(), "sample.csv")
    assert h.years[-1].senior_debt == 160
    m = M.ThreeStatementModel(h.years)
    exp = (30 / h.years[0].ni_common + 35 / h.years[1].ni_common + 40 / h.years[2].ni_common) / 3
    assert m.drivers.dividend_payout_ratio[0] == pytest.approx(exp)
    assert m.forecast_years[0].interest_expense_term > 0       # debt now carries interest


# 7. The D&A baseline used same-year PP&E although the forecast applies it to beginning PP&E.
def test_bug7_da_rate_on_beginning_ppe(hist):
    h = hist["AAPL"].years
    d = M.baseline_drivers(h)
    exp = (h[1].da / h[0].net_ppe + h[2].da / h[1].net_ppe) / 2
    assert d.da_pct[0] == pytest.approx(exp)


# 8a. Unlimited revolver (1e12) and min cash without disclosure.
def test_bug8_revolver_capacity_finite_and_disclosed(base_models):
    m = base_models["AAPL"]
    assert m.drivers.revolver_capacity == pytest.approx(round(0.10 * m.historical_years[-1].revenue, 1))
    assert any("Revolver capacity" in n for n in m.driver_notes)


# 8b. Interest income was earned on cash only, ignoring short-term investments.
def test_bug8_interest_income_on_cash_and_sti(base_models):
    m = base_models["AAPL"]
    p, y = m.historical_years[-1], m.forecast_years[0]
    assert p.st_investments > 0
    avg = (p.cash + p.st_investments + y.cash + y.st_investments) / 2
    assert y.interest_income == pytest.approx(m.drivers.cash_interest_rate[0] * avg)


# 8c. Absolute convergence tolerance 1e-4: now relative, and every year reports convergence.
def test_bug8_relative_convergence(base_models):
    for t, m in base_models.items():
        for y in m.forecast_years:
            assert y.circularity_converged
            assert y.circularity_error <= 1e-9 * max(1.0, abs(y.interest_expense - y.interest_income))


# 8d. Capacity exhaustion was not flagged.
def test_bug8_shortfall_flagged(hist, base_models):
    m = build(hist["F"], M.scenario_drivers(base_models["F"].drivers, "Bear"))
    assert any(y.funding_shortfall > 0 for y in m.forecast_years)
    assert m.warnings()


# 8e. The Yahoo loader failed when fewer than 3 common periods existed; it must raise a clear error.
def test_bug8_too_few_years_clear_error():
    snap = dl.SNAPSHOT_DIR
    fin = pd.read_csv(snap / "AAPL_income.csv", index_col=0).iloc[:, :2]
    bs = pd.read_csv(snap / "AAPL_balance.csv", index_col=0).iloc[:, :2]
    cf = pd.read_csv(snap / "AAPL_cashflow.csv", index_col=0).iloc[:, :2]
    with pytest.raises(ValueError):
        dl.from_yahoo_frames(fin, bs, cf, "AAPL", "Apple", "USD", "test", "")
