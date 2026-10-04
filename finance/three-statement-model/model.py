"""Integrated three-statement model: 3 historical years + 5 forecast years.

Conventions (also in the README):

* Units: millions of the reporting currency.
* Income statement. Operating income (EBIT) is the company's reported operating income, not
  Yahoo's "EBIT" line (which also contains non-operating items). D&A is shown on its own line;
  because most companies include D&A inside COGS / SG&A, the line "Other operating items / D&A
  reclassification" = Gross profit - SG&A - R&D - D&A - EBIT reconciles to reported EBIT and is
  disclosed, never hidden. EBITDA = EBIT + D&A.
* Pre-tax income = EBIT - interest expense + interest income + other non-operating income. In
  the historical years "other non-operating" is the disclosed difference to reported pre-tax income.
* Net income (consolidated) = EBT - tax (+ discontinued operations, historical only); the share of non-controlling interests (NCI, incl.
  preferred dividends) is deducted to get net income to common shareholders.
* Balance sheet. Every reported total is kept. "Other" lines are the disclosed differences between
  a reported subtotal and the lines shown (e.g. Other current assets = Current assets - cash -
  short-term investments - receivables - inventory). Equity = common stock & APIC + retained
  earnings - treasury stock + AOCI & other; non-controlling interests are shown separately.
* Cash comes only from the cash-flow statement: Ending cash = beginning cash + CFO + CFI + CFF.
  There is no cash plug; the balance check Assets - (Liabilities + Equity) is a real test.
* Working capital (year-end balances, 365 days): AR = DSO/365 x revenue; inventory = DIO/365 x
  COGS; AP = DPO/365 x COGS. An increase in an operating asset uses cash (negative in CFO); an
  increase in an operating liability provides cash.
* PP&E: Net PP&E_t = Net PP&E_t-1 + capex - D&A (no disposals); D&A = % of beginning net PP&E
  (or % of revenue), capped so net PP&E cannot go below zero.
* Debt: term debt changes only by scheduled issuance and repayment (repayment capped at the
  balance). Revolver: if cash before the revolver is below the minimum cash balance, the
  revolver draws the shortfall (up to its capacity); surplus cash above the minimum repays the
  revolver first. If the capacity is exhausted the remaining funding gap is flagged.
* Interest: on the average of beginning and ending balances (circular: interest -> net income ->
  cash -> revolver -> interest), solved by fixed-point iteration. Alternatively beginning
  balances (no circularity). A circuit breaker switches a year to beginning balances if the
  iteration does not converge.
* Tax = max(0, EBT x tax rate): no tax credit on losses (no loss carry-forwards modelled).
* Retained earnings_t = RE_t-1 + net income to common - dividends. Buybacks increase treasury stock.
  Short-term investments, other non-current assets/liabilities, AOCI & other equity and NCI are
  held flat (NCI receives its share of net income and distributes it).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field, fields
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

N_FORECAST = 5
NAN = float("nan")


def nz(x) -> float:
    """NaN/None -> 0 (used only where a missing value genuinely means 'nothing reported')."""
    return 0.0 if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def isnum(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


@dataclass
class StatementYear:
    year: str
    is_forecast: bool = False
    period_end: str = ""
    # Income statement
    revenue: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    sga: float = 0.0
    rd: float = 0.0
    other_opex: float = 0.0              # other operating items / D&A reclassification (disclosed)
    ebitda: float = 0.0
    da: float = 0.0
    ebit: float = 0.0
    interest_expense_term: float = 0.0
    interest_expense_revolver: float = 0.0
    interest_expense: float = 0.0
    interest_income: float = 0.0
    other_nonop: float = 0.0             # other non-operating income (+) / expense (-)
    ebt: float = 0.0
    tax_expense: float = 0.0
    disc_ops: float = 0.0                # discontinued operations & other after-tax items (historical, disclosed)
    net_income: float = 0.0              # consolidated (incl. NCI)
    ni_nci: float = 0.0                  # attributable to NCI and preferred
    ni_common: float = 0.0               # attributable to common shareholders
    # Balance sheet: assets
    cash: float = 0.0
    st_investments: float = 0.0
    accounts_receivable: float = 0.0
    inventory: float = 0.0
    other_current_assets: float = 0.0
    total_current_assets: float = 0.0
    gross_ppe: float = NAN
    accumulated_depreciation: float = NAN   # positive number
    net_ppe: float = 0.0
    other_non_current_assets: float = 0.0
    total_assets: float = 0.0
    # Liabilities
    accounts_payable: float = 0.0
    other_current_liabilities: float = 0.0
    revolver_debt: float = 0.0
    total_current_liabilities: float = 0.0  # AP + other current liabilities + revolver (term debt shown separately)
    senior_debt: float = 0.0                # term debt incl. current portion
    other_non_current_liabilities: float = 0.0
    total_liabilities: float = 0.0
    # Equity
    common_stock: float = 0.0               # common stock & APIC
    retained_earnings: float = 0.0
    treasury_stock: float = 0.0             # positive number, deducted
    aoci_other: float = 0.0                 # AOCI & other equity
    total_shareholders_equity: float = 0.0
    nci: float = 0.0
    total_equity: float = 0.0
    total_liabilities_and_equity: float = 0.0
    balance_check: float = 0.0
    # Cash-flow statement
    cfo_net_income: float = 0.0
    cfo_da: float = 0.0
    cfo_change_ar: float = NAN
    cfo_change_inv: float = NAN
    cfo_change_other_ca: float = NAN
    cfo_change_ap: float = NAN
    cfo_change_other_cl: float = NAN
    cfo_change_nwc: float = 0.0
    cfo_other: float = 0.0
    cfo: float = 0.0
    cfi_capex: float = 0.0
    cfi_other: float = 0.0
    cfi: float = 0.0
    fcf: float = 0.0
    cff_debt_issued: float = 0.0
    cff_debt_repaid: float = 0.0
    cff_revolver_change: float = 0.0
    cff_dividends_paid: float = 0.0
    cff_share_buybacks: float = 0.0
    cff_nci_distributions: float = 0.0
    cff_other: float = 0.0
    cff: float = 0.0
    fx_other: float = 0.0
    net_change_cash: float = 0.0
    beginning_cash: float = NAN
    ending_cash: float = 0.0
    # Revolver schedule and solver
    cash_pre_revolver: float = NAN
    revolver_draw: float = 0.0
    revolver_repayment: float = 0.0
    funding_shortfall: float = 0.0
    circularity_iterations: int = 0
    circularity_converged: bool = True
    circularity_error: float = 0.0
    breaker_tripped: bool = False
    missing: List[str] = field(default_factory=list)   # historical lines not reported (shown as n/a)

    def recompute_totals(self) -> None:
        """Recompute subtotals from the lines (used for historical data and templates)."""
        self.gross_profit = self.revenue - self.cogs
        self.ebitda = self.ebit + self.da
        self.interest_expense = nz(self.interest_expense_term) + nz(self.interest_expense_revolver)
        self.total_current_assets = (self.cash + self.st_investments + self.accounts_receivable + self.inventory
                                     + self.other_current_assets)
        self.total_assets = self.total_current_assets + self.net_ppe + self.other_non_current_assets
        self.total_current_liabilities = self.accounts_payable + self.other_current_liabilities + self.revolver_debt
        self.total_liabilities = self.total_current_liabilities + self.senior_debt + self.other_non_current_liabilities
        self.total_shareholders_equity = (self.common_stock + self.retained_earnings - self.treasury_stock
                                          + self.aoci_other)
        self.total_equity = self.total_shareholders_equity + self.nci
        self.total_liabilities_and_equity = self.total_liabilities + self.total_equity
        self.balance_check = self.total_assets - self.total_liabilities_and_equity


DRIVER_LISTS = [
    "revenue_growth", "gross_margin", "sga_pct_rev", "rd_pct_rev", "other_opex_pct_rev", "da_pct",
    "capex_pct_rev", "tax_rate", "dso", "dio", "dpo", "other_ca_pct_rev", "other_cl_pct_rev",
    "dividend_payout_ratio", "buyback_pct_ni", "share_buybacks", "nci_pct_ni", "other_nonop",
    "debt_issuance", "debt_repayment", "debt_interest_rate", "cash_interest_rate", "revolver_interest_rate",
]

# label, attribute, kind ("pct", "days", "amount"), help
DRIVER_SPECS = [
    ("Revenue growth", "revenue_growth", "pct", "vs prior year"),
    ("Gross margin", "gross_margin", "pct", "gross profit / revenue (COGS as reported)"),
    ("SG&A % of revenue", "sga_pct_rev", "pct", ""),
    ("R&D % of revenue", "rd_pct_rev", "pct", ""),
    ("Other operating items % of revenue", "other_opex_pct_rev", "pct", "incl. the D&A reclassification"),
    ("D&A % of beginning net PP&E (or of revenue)", "da_pct", "pct", ""),
    ("Capex % of revenue", "capex_pct_rev", "pct", ""),
    ("Tax rate on EBT", "tax_rate", "pct", "no tax credit on losses"),
    ("DSO (days, on revenue)", "dso", "days", "AR = DSO/365 x revenue"),
    ("DIO (days, on COGS)", "dio", "days", "Inventory = DIO/365 x COGS"),
    ("DPO (days, on COGS)", "dpo", "days", "AP = DPO/365 x COGS"),
    ("Other current assets % of revenue", "other_ca_pct_rev", "pct", ""),
    ("Other current liabilities % of revenue", "other_cl_pct_rev", "pct", ""),
    ("Dividend payout (% of NI to common)", "dividend_payout_ratio", "pct", ""),
    ("Buybacks (% of NI to common)", "buyback_pct_ni", "pct", ""),
    ("Additional buybacks (amount)", "share_buybacks", "amount", ""),
    ("NCI share of net income", "nci_pct_ni", "pct", "distributed to NCI holders"),
    ("Other non-operating income (amount)", "other_nonop", "amount", ""),
    ("Term debt issuance (amount)", "debt_issuance", "amount", ""),
    ("Term debt mandatory repayment (amount)", "debt_repayment", "amount", ""),
    ("Interest rate on term debt", "debt_interest_rate", "pct", ""),
    ("Interest rate on cash & ST investments", "cash_interest_rate", "pct", ""),
    ("Interest rate on revolver", "revolver_interest_rate", "pct", ""),
]


def _five(v):
    return field(default_factory=lambda: [v] * N_FORECAST)


@dataclass
class ForecastDrivers:
    revenue_growth: List[float] = _five(0.05)
    gross_margin: List[float] = _five(0.40)
    sga_pct_rev: List[float] = _five(0.12)
    rd_pct_rev: List[float] = _five(0.0)
    other_opex_pct_rev: List[float] = _five(0.0)
    da_driver_type: str = "pct_ppe"          # "pct_ppe" (beginning net PP&E) or "pct_rev"
    da_pct: List[float] = _five(0.15)
    capex_pct_rev: List[float] = _five(0.05)
    tax_rate: List[float] = _five(0.21)
    dso: List[float] = _five(45.0)
    dio: List[float] = _five(30.0)
    dpo: List[float] = _five(60.0)
    other_ca_pct_rev: List[float] = _five(0.02)
    other_cl_pct_rev: List[float] = _five(0.03)
    dividend_payout_ratio: List[float] = _five(0.20)
    buyback_pct_ni: List[float] = _five(0.0)
    share_buybacks: List[float] = _five(0.0)
    nci_pct_ni: List[float] = _five(0.0)
    other_nonop: List[float] = _five(0.0)
    debt_issuance: List[float] = _five(0.0)
    debt_repayment: List[float] = _five(0.0)
    debt_interest_rate: List[float] = _five(0.05)
    cash_interest_rate: List[float] = _five(0.02)
    revolver_interest_rate: List[float] = _five(0.06)
    min_cash_balance: float = 100.0
    revolver_capacity: float = 1_000.0
    interest_calc_method: str = "average"    # "average" (circular) or "beginning"
    circuit_breaker: bool = False            # True = force beginning balances (breaks the circularity)
    max_iterations: int = 100
    convergence_tol: float = 1e-9

    def validate(self) -> None:
        for name in DRIVER_LISTS:
            v = getattr(self, name)
            if not isinstance(v, (list, tuple)) or len(v) != N_FORECAST:
                raise ValueError(f"Driver '{name}' must be a list of {N_FORECAST} numbers, got {v!r}")
            if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in v):
                raise ValueError(f"Driver '{name}' contains a non-numeric value: {v!r}")
        for name in ("dso", "dio", "dpo", "capex_pct_rev", "da_pct", "tax_rate", "dividend_payout_ratio",
                     "buyback_pct_ni", "share_buybacks", "debt_issuance", "debt_repayment"):
            if any(x < 0 for x in getattr(self, name)):
                raise ValueError(f"Driver '{name}' cannot be negative.")
        if any(g <= -1 for g in self.revenue_growth):
            raise ValueError("Revenue growth must be above -100%.")
        if self.min_cash_balance < 0 or self.revolver_capacity < 0:
            raise ValueError("Minimum cash and revolver capacity cannot be negative.")
        if self.interest_calc_method not in ("average", "beginning"):
            raise ValueError("interest_calc_method must be 'average' or 'beginning'.")
        if self.da_driver_type not in ("pct_ppe", "pct_rev"):
            raise ValueError("da_driver_type must be 'pct_ppe' or 'pct_rev'.")

    def copy(self) -> "ForecastDrivers":
        return copy.deepcopy(self)


def _mean(vals, default):
    v = [float(x) for x in vals if isnum(x)]
    return float(np.mean(v)) if v else default


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def last_debt(h: List[StatementYear]) -> float:
    return h[-1].senior_debt + h[-1].revolver_debt


def baseline_drivers(h: List[StatementYear], notes: Optional[List[str]] = None) -> ForecastDrivers:
    """Default drivers from the 3 historical years (averages unless stated). Every fallback
    assumption is recorded in `notes`."""
    notes = notes if notes is not None else []
    rev = [y.revenue for y in h]
    g = [rev[i] / rev[i - 1] - 1 for i in range(1, len(h)) if rev[i - 1] > 0]
    g0 = _clip(_mean(g, 0.05), -0.20, 0.30)
    pr = lambda attr: _mean([nz(getattr(y, attr)) / y.revenue for y in h if y.revenue > 0], 0.0)
    gm = _clip(pr("gross_profit"), -0.5, 0.95)
    da_rates = [h[i].da / h[i - 1].net_ppe for i in range(1, len(h)) if h[i - 1].net_ppe > 0 and isnum(h[i].da)]
    da = _clip(_mean(da_rates, 0.10), 0.0, 1.0)
    capex = _clip(_mean([-y.cfi_capex / y.revenue for y in h if y.revenue > 0 and y.cfi_capex != 0], 0.05), 0.0, 0.5)
    # effective rate from years with positive pre-tax income and a tax charge (benefit years are excluded)
    tr = [y.tax_expense / y.ebt for y in h if isnum(y.tax_expense) and y.ebt > 0 and y.tax_expense > 0]
    tax = _mean(tr, NAN)
    if math.isnan(tax):
        tax = 0.21
        notes.append("Tax rate: no year with positive pre-tax income and a tax charge; 21% assumed.")
    tax = _clip(tax, 0.0, 0.5)
    days = lambda num, den: _mean([nz(getattr(y, num)) / getattr(y, den) * 365 for y in h if getattr(y, den) > 0], 0.0)
    nic = [y.ni_common for y in h]
    payout = _clip(_mean([-y.cff_dividends_paid / y.ni_common for y in h if y.ni_common > 0], 0.0), 0.0, 1.5)
    bb = _clip(_mean([-y.cff_share_buybacks / y.ni_common for y in h if y.ni_common > 0], 0.0), 0.0, 1.5)
    nci_pct = _mean([y.ni_nci / y.net_income for y in h if y.net_income > 0], 0.0)
    # interest rate on average debt
    rates = []
    for i in range(1, len(h)):
        avg_debt = (h[i - 1].senior_debt + h[i].senior_debt) / 2
        if isnum(h[i].interest_expense_term) and h[i].interest_expense_term > 0 and avg_debt > 0:
            rates.append(h[i].interest_expense_term / avg_debt)
    debt_rate = _mean(rates, NAN)
    if math.isnan(debt_rate):
        debt_rate = 0.05
        notes.append("Interest rate on debt: interest expense not reported; 5.0% assumed.")
    debt_rate = _clip(debt_rate, 0.0, 0.15)
    if debt_rate < 0.02 and last_debt(h) > 0:
        notes.append(f"Interest rate on debt from the history is only {debt_rate:.1%}: reported interest expense may "
                     f"exclude interest shown elsewhere (e.g. a finance arm's interest inside cost of sales). Review it.")
    crates = []
    for i in range(1, len(h)):
        avg_c = (h[i - 1].cash + h[i - 1].st_investments + h[i].cash + h[i].st_investments) / 2
        if isnum(h[i].interest_income) and h[i].interest_income > 0 and avg_c > 0:
            crates.append(h[i].interest_income / avg_c)
    cash_rate = _mean(crates, NAN)
    if math.isnan(cash_rate):
        cash_rate = 0.03
        notes.append("Interest rate on cash: interest income not reported; 3.0% assumed.")
    cash_rate = _clip(cash_rate, 0.0, 0.10)
    last = h[-1]
    notes.append("Minimum cash: 50% of the latest cash balance (assumption). Revolver capacity: 10% of latest revenue (assumption).")
    return ForecastDrivers(
        revenue_growth=[g0, g0 * 0.9, g0 * 0.8, g0 * 0.75, g0 * 0.75],
        gross_margin=[gm] * 5, sga_pct_rev=[pr("sga")] * 5, rd_pct_rev=[pr("rd")] * 5,
        other_opex_pct_rev=[pr("other_opex")] * 5, da_driver_type="pct_ppe", da_pct=[da] * 5,
        capex_pct_rev=[capex] * 5, tax_rate=[tax] * 5,
        dso=[days("accounts_receivable", "revenue")] * 5, dio=[days("inventory", "cogs")] * 5,
        dpo=[days("accounts_payable", "cogs")] * 5,
        other_ca_pct_rev=[pr("other_current_assets")] * 5, other_cl_pct_rev=[pr("other_current_liabilities")] * 5,
        dividend_payout_ratio=[payout] * 5, buyback_pct_ni=[bb] * 5, share_buybacks=[0.0] * 5,
        nci_pct_ni=[_clip(nci_pct, 0.0, 1.0)] * 5, other_nonop=[0.0] * 5,
        debt_issuance=[0.0] * 5, debt_repayment=[0.0] * 5,
        debt_interest_rate=[debt_rate] * 5, cash_interest_rate=[cash_rate] * 5,
        revolver_interest_rate=[debt_rate + 0.01] * 5,
        min_cash_balance=round(max(0.0, last.cash) * 0.5, 1),
        revolver_capacity=round(0.10 * last.revenue, 1),
    )


# ======================================================================= forecast engine

def _forecast_year(i: int, label: str, p: StatementYear, d: ForecastDrivers) -> StatementYear:
    y = StatementYear(year=label, is_forecast=True)
    # --- operating lines (independent of the circularity)
    y.revenue = p.revenue * (1 + d.revenue_growth[i])
    y.cogs = y.revenue * (1 - d.gross_margin[i])
    y.gross_profit = y.revenue - y.cogs
    y.sga = y.revenue * d.sga_pct_rev[i]
    y.rd = y.revenue * d.rd_pct_rev[i]
    y.other_opex = y.revenue * d.other_opex_pct_rev[i]
    y.ebitda = y.gross_profit - y.sga - y.rd - y.other_opex
    capex = y.revenue * d.capex_pct_rev[i]
    da = (p.net_ppe * d.da_pct[i]) if d.da_driver_type == "pct_ppe" else (y.revenue * d.da_pct[i])
    y.da = min(max(da, 0.0), max(p.net_ppe + capex, 0.0))
    y.ebit = y.ebitda - y.da
    y.net_ppe = p.net_ppe + capex - y.da
    y.gross_ppe = p.gross_ppe + capex if isnum(p.gross_ppe) else NAN
    y.accumulated_depreciation = p.accumulated_depreciation + y.da if isnum(p.accumulated_depreciation) else NAN
    # --- working capital
    y.accounts_receivable = d.dso[i] / 365 * y.revenue
    y.inventory = d.dio[i] / 365 * y.cogs
    y.accounts_payable = d.dpo[i] / 365 * y.cogs
    y.other_current_assets = d.other_ca_pct_rev[i] * y.revenue
    y.other_current_liabilities = d.other_cl_pct_rev[i] * y.revenue
    y.cfo_change_ar = -(y.accounts_receivable - p.accounts_receivable)
    y.cfo_change_inv = -(y.inventory - p.inventory)
    y.cfo_change_other_ca = -(y.other_current_assets - p.other_current_assets)
    y.cfo_change_ap = y.accounts_payable - p.accounts_payable
    y.cfo_change_other_cl = y.other_current_liabilities - p.other_current_liabilities
    y.cfo_change_nwc = (y.cfo_change_ar + y.cfo_change_inv + y.cfo_change_other_ca
                        + y.cfo_change_ap + y.cfo_change_other_cl)
    # --- items held flat
    y.st_investments = p.st_investments
    y.other_non_current_assets = p.other_non_current_assets
    y.other_non_current_liabilities = p.other_non_current_liabilities
    y.common_stock = p.common_stock
    y.aoci_other = p.aoci_other
    # --- term debt
    issue = d.debt_issuance[i]
    repay = min(d.debt_repayment[i], p.senior_debt + issue)
    y.senior_debt = p.senior_debt + issue - repay
    y.cff_debt_issued, y.cff_debt_repaid = issue, -repay
    y.other_nonop = d.other_nonop[i]

    def solve(end_cash, end_rev, use_avg):
        bal = (lambda b, e: (b + e) / 2) if use_avg else (lambda b, e: b)
        y.interest_expense_term = d.debt_interest_rate[i] * bal(p.senior_debt, y.senior_debt)
        y.interest_expense_revolver = d.revolver_interest_rate[i] * bal(p.revolver_debt, end_rev)
        y.interest_expense = y.interest_expense_term + y.interest_expense_revolver
        y.interest_income = d.cash_interest_rate[i] * max(0.0, bal(p.cash + p.st_investments, end_cash + y.st_investments))
        y.ebt = y.ebit - y.interest_expense + y.interest_income + y.other_nonop
        y.tax_expense = max(0.0, y.ebt * d.tax_rate[i])
        y.net_income = y.ebt - y.tax_expense
        y.ni_nci = d.nci_pct_ni[i] * y.net_income
        y.ni_common = y.net_income - y.ni_nci
        y.cfo_net_income, y.cfo_da = y.net_income, y.da
        y.cfo = y.net_income + y.da + y.cfo_change_nwc
        y.cfi_capex = -capex
        y.cfi = -capex
        y.fcf = y.cfo - capex
        div = d.dividend_payout_ratio[i] * max(0.0, y.ni_common)
        bb = d.buyback_pct_ni[i] * max(0.0, y.ni_common) + d.share_buybacks[i]
        nci_dist = max(0.0, y.ni_nci)
        y.cff_dividends_paid, y.cff_share_buybacks, y.cff_nci_distributions = -div, -bb, -nci_dist
        cff_pre = issue - repay - div - bb - nci_dist
        y.cash_pre_revolver = p.cash + y.cfo + y.cfi + cff_pre
        if y.cash_pre_revolver < d.min_cash_balance:
            room = max(0.0, d.revolver_capacity - p.revolver_debt)
            draw, rep = min(d.min_cash_balance - y.cash_pre_revolver, room), 0.0
        else:
            draw, rep = 0.0, min(p.revolver_debt, y.cash_pre_revolver - d.min_cash_balance)
        y.revolver_draw, y.revolver_repayment = draw, rep
        y.cff_revolver_change = draw - rep
        y.cff = cff_pre + y.cff_revolver_change
        return y.cash_pre_revolver + draw - rep, p.revolver_debt + draw - rep

    use_avg = d.interest_calc_method == "average" and not d.circuit_breaker
    end_cash, end_rev = p.cash, p.revolver_debt
    if use_avg:
        prev_int = None
        for it in range(1, d.max_iterations + 1):
            end_cash, end_rev = solve(end_cash, end_rev, True)
            net_int = y.interest_expense - y.interest_income
            err = abs(net_int - prev_int) if prev_int is not None else float("inf")
            prev_int = net_int
            y.circularity_iterations, y.circularity_error = it, err
            if not math.isfinite(net_int):
                break
            if err <= d.convergence_tol * max(1.0, abs(net_int)):
                break
        # one final pass so every line is consistent with the converged balances
        end_cash, end_rev = solve(end_cash, end_rev, True)
        final_err = abs((y.interest_expense - y.interest_income) - prev_int)
        y.circularity_converged = math.isfinite(final_err) and final_err <= 1e-6 * max(1.0, abs(prev_int))
        if not y.circularity_converged:            # circuit breaker trips: beginning balances
            y.breaker_tripped = True
            end_cash, end_rev = solve(p.cash, p.revolver_debt, False)
    else:
        end_cash, end_rev = solve(p.cash, p.revolver_debt, False)
        y.circularity_iterations, y.circularity_error = 1, 0.0
    y.cash, y.revolver_debt = end_cash, end_rev
    y.funding_shortfall = max(0.0, d.min_cash_balance - end_cash) if y.cash_pre_revolver < d.min_cash_balance else 0.0
    y.net_change_cash = y.cfo + y.cfi + y.cff
    y.beginning_cash, y.ending_cash = p.cash, p.cash + y.net_change_cash
    # --- equity roll-forward
    y.retained_earnings = p.retained_earnings + y.ni_common + y.cff_dividends_paid
    y.treasury_stock = p.treasury_stock - y.cff_share_buybacks
    y.nci = p.nci + y.ni_nci + y.cff_nci_distributions
    y.recompute_totals()
    y.ebitda = y.ebit + y.da
    return y


class ThreeStatementModel:
    def __init__(self, historical_years: List[StatementYear], drivers: Optional[ForecastDrivers] = None,
                 company_name: str = "Company", ticker: str = "CUSTOM"):
        if len(historical_years) != 3:
            raise ValueError(f"The model needs exactly 3 historical years, got {len(historical_years)}.")
        self.historical_years = historical_years
        self.company_name, self.ticker = company_name, ticker
        self.driver_notes: List[str] = []
        self.drivers = drivers if drivers is not None else baseline_drivers(historical_years, self.driver_notes)
        self.solve()

    def forecast_labels(self) -> List[str]:
        try:
            last = int(str(self.historical_years[-1].year)[-4:])
            return [f"{last + k}E" for k in range(1, N_FORECAST + 1)]
        except ValueError:
            return [f"Y+{k}" for k in range(1, N_FORECAST + 1)]

    def solve(self) -> None:
        self.drivers.validate()
        prev = self.historical_years[-1]
        self.forecast_years = []
        for i, lab in enumerate(self.forecast_labels()):
            prev = _forecast_year(i, lab, prev, self.drivers)
            self.forecast_years.append(prev)
        self.all_years = self.historical_years + self.forecast_years

    # ------------------------------------------------------------- checks
    def verify_balance_checks(self, tol: float = 0.01) -> Dict:
        det = [dict(year=y.year, is_forecast=y.is_forecast, assets=y.total_assets,
                    liabilities_equity=y.total_liabilities_and_equity, difference=y.balance_check,
                    is_balanced=abs(y.balance_check) < tol) for y in self.all_years]
        return {"all_balanced": all(x["is_balanced"] for x in det),
                "forecast_balanced": all(x["is_balanced"] for x in det if x["is_forecast"]),
                "max_error": max(abs(x["difference"]) for x in det), "details": det}

    def integrity_checks(self) -> pd.DataFrame:
        """Independent ties for each forecast year (all should be 0)."""
        rows = []
        prev = self.historical_years[-1]
        for y in self.forecast_years:
            rows.append({
                "year": y.year,
                "Balance check (A - L - E)": y.balance_check,
                "Cash: BS - CFS ending cash": y.cash - y.ending_cash,
                "RE roll-forward": y.retained_earnings - (prev.retained_earnings + y.ni_common + y.cff_dividends_paid),
                "PP&E roll-forward": y.net_ppe - (prev.net_ppe - y.cfi_capex - y.da),
                "Debt roll-forward": (y.senior_debt + y.revolver_debt) - (prev.senior_debt + prev.revolver_debt
                                                                          + y.cff_debt_issued + y.cff_debt_repaid + y.cff_revolver_change),
                "NWC change: BS vs CFS": (_nwc(y) - _nwc(prev)) + y.cfo_change_nwc,
            })
            prev = y
        return pd.DataFrame(rows).set_index("year")

    def warnings(self) -> List[str]:
        out = []
        for y in self.forecast_years:
            if y.funding_shortfall > 0.005:
                out.append(f"{y.year}: revolver capacity exhausted - cash is {y.funding_shortfall:,.1f} below the minimum"
                           + (" and negative." if y.cash < 0 else "."))
            if y.breaker_tripped:
                out.append(f"{y.year}: interest iteration did not converge; circuit breaker used beginning balances.")
        return out


def _nwc(y: StatementYear) -> float:
    return (y.accounts_receivable + y.inventory + y.other_current_assets
            - y.accounts_payable - y.other_current_liabilities)


# ======================================================================= scenarios

SCENARIO_DELTAS = {
    "Bull": dict(revenue_growth=+0.03, gross_margin=+0.01, sga_pct_rev=-0.005, dso=-3, dio=-3, dpo=+3),
    "Bear": dict(revenue_growth=-0.05, gross_margin=-0.02, sga_pct_rev=+0.01, dso=+5, dio=+5, dpo=-5,
                 debt_interest_rate=+0.015, revolver_interest_rate=+0.02),
}


def scenario_drivers(base: ForecastDrivers, name: str) -> ForecastDrivers:
    """Bull / Bear = Base plus the additive deltas in SCENARIO_DELTAS (days never below 0)."""
    d = base.copy()
    if name == "Base":
        return d
    for attr, delta in SCENARIO_DELTAS[name].items():
        floor = 0.0 if attr in ("dso", "dio", "dpo", "sga_pct_rev", "debt_interest_rate", "revolver_interest_rate") else -0.99
        setattr(d, attr, [max(floor, v + delta) for v in getattr(base, attr)])
    return d


def run_scenarios(hist: List[StatementYear], base: ForecastDrivers, company: str = "Company",
                  ticker: str = "CUSTOM") -> Dict[str, ThreeStatementModel]:
    return {n: ThreeStatementModel(copy.deepcopy(hist), scenario_drivers(base, n), company, ticker)
            for n in ("Base", "Bull", "Bear")}


def scenario_comparison(models: Dict[str, ThreeStatementModel]) -> pd.DataFrame:
    rows = []
    for name, m in models.items():
        f, h = m.forecast_years, m.historical_years[-1]
        rows.append({
            "Scenario": name,
            "Revenue CAGR (5y)": (f[-1].revenue / h.revenue) ** (1 / 5) - 1 if h.revenue > 0 else NAN,
            "Year-5 revenue": f[-1].revenue, "Year-5 EBIT margin": f[-1].ebit / f[-1].revenue,
            "Year-5 net income": f[-1].ni_common, "Cumulative FCF (5y)": sum(y.fcf for y in f),
            "Year-5 cash": f[-1].cash, "Year-5 revolver": f[-1].revolver_debt,
            "Year-5 total debt": f[-1].senior_debt + f[-1].revolver_debt,
            "Max revolver": max(y.revolver_debt for y in f),
            "Max balance-check error": max(abs(y.balance_check) for y in f),
        })
    return pd.DataFrame(rows).set_index("Scenario")


# ======================================================================= presentation rows

IS_ROWS = [
    ("Revenue", "revenue", 1, "total"), ("Cost of goods sold", "cogs", -1, ""), ("Gross profit", "gross_profit", 1, "total"),
    ("SG&A", "sga", -1, ""), ("R&D", "rd", -1, ""),
    ("Other operating items / D&A reclassification", "other_opex", -1, ""),
    ("EBITDA", "ebitda", 1, "total"), ("Depreciation & amortization", "da", -1, ""),
    ("Operating income (EBIT, as reported)", "ebit", 1, "total"),
    ("Interest expense - term debt", "interest_expense_term", -1, ""), ("Interest expense - revolver", "interest_expense_revolver", -1, ""),
    ("Interest income", "interest_income", 1, ""), ("Other non-operating income / (expense)", "other_nonop", 1, ""),
    ("Pre-tax income (EBT)", "ebt", 1, "total"), ("Income tax", "tax_expense", -1, ""),
    ("Discontinued operations & other (after tax)", "disc_ops", 1, ""),
    ("Net income (consolidated)", "net_income", 1, "total"), ("Attributable to NCI & preferred", "ni_nci", -1, ""),
    ("Net income to common shareholders", "ni_common", 1, "grand"),
]
BS_ROWS = [
    ("Cash & cash equivalents", "cash", 1, ""), ("Short-term investments", "st_investments", 1, ""),
    ("Accounts receivable", "accounts_receivable", 1, ""), ("Inventory", "inventory", 1, ""),
    ("Other current assets", "other_current_assets", 1, ""), ("Total current assets", "total_current_assets", 1, "total"),
    ("Gross PP&E", "gross_ppe", 1, "memo"), ("Accumulated depreciation", "accumulated_depreciation", -1, "memo"),
    ("Net PP&E", "net_ppe", 1, ""), ("Other non-current assets", "other_non_current_assets", 1, ""),
    ("TOTAL ASSETS", "total_assets", 1, "grand"),
    ("Accounts payable", "accounts_payable", 1, ""), ("Other current liabilities", "other_current_liabilities", 1, ""),
    ("Revolver", "revolver_debt", 1, ""), ("Current liabilities (excl. term debt)", "total_current_liabilities", 1, "total"),
    ("Term debt (incl. current portion)", "senior_debt", 1, ""), ("Other non-current liabilities", "other_non_current_liabilities", 1, ""),
    ("TOTAL LIABILITIES", "total_liabilities", 1, "total"),
    ("Common stock & APIC", "common_stock", 1, ""), ("Retained earnings", "retained_earnings", 1, ""),
    ("Treasury stock", "treasury_stock", -1, ""), ("AOCI & other equity", "aoci_other", 1, ""),
    ("Shareholders' equity", "total_shareholders_equity", 1, "total"), ("Non-controlling interests", "nci", 1, ""),
    ("TOTAL EQUITY", "total_equity", 1, "total"), ("TOTAL LIABILITIES & EQUITY", "total_liabilities_and_equity", 1, "grand"),
    ("Balance check (A - L - E)", "balance_check", 1, "check"),
]
CFS_ROWS = [
    ("Net income (consolidated)", "cfo_net_income", 1, ""), ("Depreciation & amortization", "cfo_da", 1, ""),
    ("(Increase) / decrease in receivables", "cfo_change_ar", 1, ""), ("(Increase) / decrease in inventory", "cfo_change_inv", 1, ""),
    ("(Increase) / decrease in other current assets", "cfo_change_other_ca", 1, ""),
    ("Increase / (decrease) in payables", "cfo_change_ap", 1, ""),
    ("Increase / (decrease) in other current liabilities", "cfo_change_other_cl", 1, ""),
    ("Change in working capital", "cfo_change_nwc", 1, "sub"), ("Other operating items (reported)", "cfo_other", 1, ""),
    ("Cash from operations (CFO)", "cfo", 1, "total"),
    ("Capital expenditure", "cfi_capex", 1, ""), ("Other investing (reported)", "cfi_other", 1, ""),
    ("Cash from investing (CFI)", "cfi", 1, "total"),
    ("Term debt issued", "cff_debt_issued", 1, ""), ("Term debt repaid", "cff_debt_repaid", 1, ""),
    ("Revolver draw / (repayment)", "cff_revolver_change", 1, ""), ("Dividends", "cff_dividends_paid", 1, ""),
    ("Share buybacks", "cff_share_buybacks", 1, ""), ("Distributions to NCI", "cff_nci_distributions", 1, ""),
    ("Other financing (reported)", "cff_other", 1, ""), ("Cash from financing (CFF)", "cff", 1, "total"),
    ("FX & other (reported)", "fx_other", 1, ""), ("Net change in cash", "net_change_cash", 1, "total"),
    ("Beginning cash", "beginning_cash", 1, ""), ("Ending cash", "ending_cash", 1, "grand"),
    ("Free cash flow (CFO - capex)", "fcf", 1, "memo"),
]


def statement_frame(model: ThreeStatementModel, rows) -> pd.DataFrame:
    """Statement as a DataFrame in presentation signs (costs negative). NaN = not reported."""
    data = {}
    for label, attr, sign, _ in rows:
        vals = []
        for y in model.all_years:
            v = getattr(y, attr)
            vals.append(NAN if not isnum(v) or attr in y.missing else sign * float(v))
        data[label] = vals
    return pd.DataFrame(data, index=[y.year for y in model.all_years]).T


# ======================================================================= stress presets

def revolver_stress(base: ForecastDrivers, special_buyback: float = 55_000.0, buyback_pct_ni: float = 0.80) -> ForecastDrivers:
    """Revolver stress test: a one-off special buyback in year 1 that cash cannot cover, so the
    revolver draws to protect minimum cash and is repaid from later surpluses.
    The defaults are sized for Apple (millions of USD); scale them for other companies."""
    d = base.copy()
    d.share_buybacks = [base.share_buybacks[0] + special_buyback] + list(base.share_buybacks[1:])
    d.buyback_pct_ni = [buyback_pct_ni] * N_FORECAST
    return d
