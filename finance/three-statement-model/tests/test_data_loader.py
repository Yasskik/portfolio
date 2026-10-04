"""Historical mapping: Yahoo snapshot and the upload template."""
import numpy as np
import pandas as pd
import pytest

import data_loader as dl
from tests.conftest import TICKERS

SNAP = dl.SNAPSHOT_DIR


def raw(t, stmt):
    return pd.read_csv(SNAP / f"{t}_{stmt}.csv", index_col=0)


@pytest.mark.parametrize("t", TICKERS)
def test_snapshot_loads_three_years_and_balances_without_plug(hist, t):
    h = hist[t]
    assert len(h.years) == 3
    b = raw(t, "balance")
    for y in h.years:
        col = [c for c in b.columns if abs((pd.Timestamp(c) - pd.Timestamp(y.period_end)).days) <= 20][0]
        ta = b.loc["Total Assets", col] / 1e6
        tl = b.loc["Total Liabilities Net Minority Interest", col] / 1e6
        te = b.loc["Total Equity Gross Minority Interest", col] / 1e6
        assert y.total_assets == pytest.approx(ta)
        assert y.total_liabilities == pytest.approx(tl)
        assert y.total_equity == pytest.approx(te)
        assert y.balance_check == pytest.approx(ta - tl - te, abs=1e-6)   # reported difference, not forced
        assert abs(y.balance_check) < 0.5


def test_ebit_is_operating_income_not_yahoo_ebit(hist):
    i = raw("KO", "income")
    col = i.columns[0]
    y = hist["KO"].years[-1]
    assert y.ebit == pytest.approx(i.loc["Operating Income", col] / 1e6)          # 14,911
    assert y.ebit != pytest.approx(i.loc["EBIT", col] / 1e6)                      # Yahoo EBIT 17,652


@pytest.mark.parametrize("t", TICKERS)
def test_cash_and_short_term_investments_not_double_counted(hist, t):
    b = raw(t, "balance")
    y = hist[t].years[-1]
    col = [c for c in b.columns if abs((pd.Timestamp(c) - pd.Timestamp(y.period_end)).days) <= 20][0]
    combined = b.loc["Cash Cash Equivalents And Short Term Investments", col] / 1e6
    assert y.cash + y.st_investments == pytest.approx(combined)
    ca = b.loc["Current Assets", col] / 1e6
    assert y.total_current_assets == pytest.approx(ca)


@pytest.mark.parametrize("t", TICKERS)
def test_components_reproduce_reported_totals(hist, t):
    for y in hist[t].years:
        assert y.cash + y.st_investments + y.accounts_receivable + y.inventory + y.other_current_assets == pytest.approx(y.total_current_assets)
        assert y.total_current_assets + y.net_ppe + y.other_non_current_assets == pytest.approx(y.total_assets)
        assert (y.accounts_payable + y.other_current_liabilities + y.revolver_debt + y.senior_debt
                + y.other_non_current_liabilities) == pytest.approx(y.total_liabilities)
        assert y.common_stock + y.retained_earnings - y.treasury_stock + y.aoci_other == pytest.approx(y.total_shareholders_equity)
        # income statement foots to reported operating income and pre-tax income
        assert y.revenue - y.cogs - y.sga - y.rd - y.other_opex - y.da == pytest.approx(y.ebit)
        assert y.ebit - np.nan_to_num(y.interest_expense_term) + np.nan_to_num(y.interest_income) + y.other_nonop == pytest.approx(y.ebt)


def test_minority_interest_is_kept_in_equity(hist):
    y = hist["KO"].years[-1]
    assert y.nci == pytest.approx(34275 - 32169)
    assert y.total_equity == pytest.approx(y.total_shareholders_equity + y.nci)


def test_mapping_table_and_source(hist):
    h = hist["AAPL"]
    assert h.mapping is not None
    assert set(h.mapping.loc["ebit"]) == {"Operating Income"}
    assert set(h.mapping.loc["total_liabilities"]) == {"Total Liabilities Net Minority Interest"}
    assert "snapshot" in h.source.lower()


def test_unknown_snapshot_ticker():
    with pytest.raises(ValueError):
        dl.load_snapshot("ZZZZ")


# ---------------------------------------------------------------- templates
def _csv(df):
    return df.to_csv().encode()


def test_sample_template_csv_and_xlsx_load_and_balance():
    for f in ("sample_historical.csv", "sample_company.xlsx"):
        h = dl.load_template((dl.TEMPLATE_DIR / f).read_bytes(), f)
        assert [y.year for y in h.years] == ["FY2023", "FY2024", "FY2025"]
        assert [y.revenue for y in h.years] == [1000, 1120, 1250]
        assert all(y.balance_check == pytest.approx(0) for y in h.years)
        assert [y.senior_debt for y in h.years] == [200, 180, 160]
        assert h.years[-1].cff_dividends_paid == -40


def test_template_does_not_balance_is_shown_not_plugged():
    df = dl.template_frame(True)
    df.loc["Total assets", "FY2025"] += 10
    h = dl.load_template(_csv(df), "x.csv")
    assert h.years[-1].balance_check == pytest.approx(10)
    assert any("does not balance" in w for w in h.warnings)


def test_template_exact_label_matching_and_unknown_rows_warned():
    df = dl.template_frame(True)
    extra = pd.DataFrame([[999, 999, 999], [5, 5, 5]], index=["Senior Debt Issuance", "EBITDA"], columns=df.columns)
    h = dl.load_template(_csv(pd.concat([df, extra])), "x.csv")
    assert h.years[-1].senior_debt == 160              # not 999
    assert h.years[-1].ebit == 320                     # EBITDA did not overwrite EBIT
    assert any("not recognised" in w and "Senior Debt Issuance" in w for w in h.warnings)


def test_template_missing_optional_lines_are_reported():
    df = dl.template_frame(True).drop(index=["R&D", "Inventory"])
    h = dl.load_template(_csv(df), "x.csv")
    assert h.years[0].rd == 0 and "rd" in h.years[0].missing
    assert any("Not provided" in w for w in h.warnings)


def test_template_missing_required_line_raises():
    df = dl.template_frame(True).drop(index=["Total assets"])
    with pytest.raises(ValueError, match="Total assets"):
        dl.load_template(_csv(df), "x.csv")


def test_template_needs_three_years():
    df = dl.template_frame(True)[["FY2024", "FY2025"]]
    with pytest.raises(ValueError, match="3 year columns"):
        dl.load_template(_csv(df), "x.csv")
