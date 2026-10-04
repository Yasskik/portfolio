"""
Financial Statement Analyzer - core engine (analyzer.py)
--------------------------------------------------------
Loads annual financial statements (Yahoo Finance via ``yfinance`` or an uploaded
CSV / Excel template) and calculates:

* liquidity, profitability, solvency, efficiency, cash-flow-quality and growth ratios
* DuPont analysis (3-step and 5-step, both multiply back exactly to ROE)
* Altman Z-score (original 1968 public-manufacturer model) and Altman Z''
  (1995 non-manufacturer model)
* Piotroski F-score (all 9 signals, as defined in Piotroski 2000)
* common-size (vertical) and trend (horizontal) statements
* a rule-based, plain-English financial health report

Conventions (also documented in README.md and GUIDE.md)
------------------------------------------------------
* Balance-sheet ratios use **year-end (ending) balances** unless the row label
  says "avg." (average of this year-end and last year-end). The first year has
  no prior balance, so every "avg." ratio is n/a for it.
* "EBIT" means **Operating Income** as reported (not Yahoo's derived ``EBIT``
  line, which is pre-tax income plus interest expense).
* Days ratios use **365 days**.
* Capex is treated as a cash **outflow** whatever its sign in the source
  (Yahoo reports it as a negative number): FCF = CFO - |Capex|.
* Missing data stays missing: a ratio whose inputs are not reported is ``None``
  (shown as "n/a"). Nothing is filled with zeros or guesses.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:  # yfinance is only needed for live data; tests run offline
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

DAYS_IN_YEAR = 365.0

# =====================================================================
# Line-item aliases (first match wins, so the order matters)
# =====================================================================
STATEMENT_ALIASES: Dict[str, Dict[str, List[str]]] = {
    "income": {
        "revenue": ["Total Revenue", "Operating Revenue", "Revenue", "Revenues", "Total Revenues",
                    "Sales", "Total Sales", "Net Sales"],
        "cost_of_revenue": ["Cost Of Revenue", "Reconciled Cost Of Revenue", "Cost of Goods Sold",
                            "Cost Of Goods Sold", "COGS", "Cost of Sales"],
        "gross_profit": ["Gross Profit"],
        "operating_expense": ["Operating Expense", "Operating Expenses", "Total Operating Expenses"],
        "operating_income": ["Operating Income", "Operating Profit", "Total Operating Income As Reported"],
        "interest_expense": ["Interest Expense", "Interest Expense Non Operating", "Finance Costs"],
        "pretax_income": ["Pretax Income", "Income Before Tax", "Earnings Before Tax", "EBT",
                          "Income Before Taxes", "Pre-Tax Income"],
        "tax_provision": ["Tax Provision", "Income Tax Expense", "Provision For Income Taxes", "Income Tax"],
        "net_income": ["Net Income", "Net Income Common Stockholders",
                       "Net Income From Continuing Operation Net Minority Interest",
                       "Net Income Continuous Operations", "Net Profit"],
        "diluted_eps": ["Diluted EPS", "EPS Diluted", "Diluted Earnings Per Share"],
        "shares_diluted": ["Diluted Average Shares", "Diluted Shares", "Basic Average Shares"],
    },
    "balance_sheet": {
        "cash_and_equivalents": ["Cash And Cash Equivalents", "Cash and Cash Equivalents",
                                 "Cash & Cash Equivalents", "Cash"],
        "short_term_investments": ["Other Short Term Investments", "Short Term Investments",
                                   "Marketable Securities"],
        "cash_and_sti": ["Cash Cash Equivalents And Short Term Investments"],
        "receivables": ["Receivables", "Total Receivables", "Accounts Receivable", "Trade Receivables"],
        "accounts_receivable": ["Accounts Receivable", "Trade Receivables", "Receivables"],
        "inventory": ["Inventory", "Inventories", "Total Inventory", "Merchandise Inventory"],
        "current_assets": ["Current Assets", "Total Current Assets"],
        "net_ppe": ["Net PPE", "Property Plant Equipment Net", "Net Property Plant And Equipment"],
        "goodwill_and_intangibles": ["Goodwill And Other Intangible Assets", "Goodwill"],
        "total_assets": ["Total Assets"],
        "accounts_payable": ["Accounts Payable", "Trade Payables", "Trade and Other Payables", "Payables"],
        "current_debt": ["Current Debt And Capital Lease Obligation", "Current Debt", "Short Term Debt",
                         "Current Borrowings"],
        "current_liabilities": ["Current Liabilities", "Total Current Liabilities"],
        "long_term_debt": ["Long Term Debt And Capital Lease Obligation", "Long Term Debt",
                           "Non Current Debt", "Long Term Borrowings"],
        "total_debt": ["Total Debt", "Total Borrowings"],
        "total_liabilities": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
        "stockholders_equity": ["Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity",
                                "Total Shareholders Equity", "Shareholders Equity", "Total Equity",
                                "Total Equity Gross Minority Interest"],
        "total_equity_incl_minority": ["Total Equity Gross Minority Interest", "Total Equity"],
        "retained_earnings": ["Retained Earnings", "Accumulated Deficit", "Retained Earnings (Accumulated Deficit)"],
        "working_capital": ["Working Capital", "Net Working Capital"],
        "shares_outstanding": ["Ordinary Shares Number", "Share Issued", "Shares Outstanding",
                               "Common Shares Outstanding"],
    },
    "cashflow": {
        "operating_cash_flow": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
                                "Net Cash Provided By Operating Activities", "Cash Flow From Operations", "CFO"],
        "capital_expenditure": ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE",
                                "Purchase Of Property Plant And Equipment", "CapEx"],
        "free_cash_flow": ["Free Cash Flow", "FCF"],
        "investing_cash_flow": ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities",
                                "Net Cash Used In Investing Activities"],
        "financing_cash_flow": ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities",
                                "Net Cash Used In Financing Activities"],
        "depreciation_amortization": ["Depreciation And Amortization", "Depreciation Amortization Depletion",
                                      "Reconciled Depreciation", "Depreciation"],
        "dividends_paid": ["Cash Dividends Paid", "Common Stock Dividend Paid", "Dividends Paid"],
        "share_repurchases": ["Repurchase Of Capital Stock", "Common Stock Payments", "Share Buybacks"],
    },
}

# Rows that make no sense as "% of revenue" / "% of assets" (counts, per-share data, rates)
_NON_MONETARY_HINTS = ("shares", "eps", "share issued", "rate for calcs", "shares number")

# Industries whose balance sheets don't fit ratio models built for operating companies
FINANCIAL_INDUSTRY_HINTS = ("bank", "insurance", "capital markets", "asset management", "mortgage",
                            "savings", "thrift", "financial conglomerates", "shell companies")


def _safe_float(val: Any) -> Optional[float]:
    """Convert to float; return None for None / NaN / inf / text."""
    if val is None:
        return None
    try:
        f = float(val)
    except (ValueError, TypeError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _safe_div(n: Optional[float], d: Optional[float], default: Optional[float] = None) -> Optional[float]:
    """n / d, or ``default`` if either is missing or d is zero."""
    n, d = _safe_float(n), _safe_float(d)
    if n is None or d is None or d == 0.0:
        return default
    res = n / d
    return default if (math.isnan(res) or math.isinf(res)) else res


def _avg(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return (a + b) / 2.0 if (a is not None and b is not None) else None


def _all(*vals) -> bool:
    return all(v is not None for v in vals)


# =====================================================================
# FinancialData container
# =====================================================================
class FinancialData:
    """Normalised statements for one company; columns are fiscal years ('2022', '2023', ...)."""

    def __init__(
        self,
        symbol: str,
        company_name: str,
        income_statement: pd.DataFrame,
        balance_sheet: pd.DataFrame,
        cash_flow: pd.DataFrame,
        currency: str = "USD",
        sector: str = "General",
        industry: str = "General",
        market_cap: Optional[float] = None,
        share_price: Optional[float] = None,
        market_value_by_year: Optional[Dict[str, float]] = None,
        price_by_year: Optional[Dict[str, float]] = None,
        source: str = "upload",
    ):
        self.symbol = (symbol or "CUSTOM").upper().strip()
        self.company_name = company_name or self.symbol
        self.currency = currency or "USD"
        self.sector = sector or "General"
        self.industry = industry or "General"
        self.market_cap = _safe_float(market_cap)
        self.share_price = _safe_float(share_price)
        self.source = source

        self.income_statement = self._normalize_df(income_statement)
        self.balance_sheet = self._normalize_df(balance_sheet)
        self.cash_flow = self._normalize_df(cash_flow)

        years = set(self.income_statement.columns) | set(self.balance_sheet.columns) | set(self.cash_flow.columns)
        self.years: List[str] = sorted(years, key=str)
        self.income_statement = self.income_statement.reindex(columns=self.years)
        self.balance_sheet = self.balance_sheet.reindex(columns=self.years)
        self.cash_flow = self.cash_flow.reindex(columns=self.years)

        # Fiscal-year-end price per year (for Altman X4). Market value = price x shares outstanding.
        self.price_by_year: Dict[str, float] = {str(k): v for k, v in (price_by_year or {}).items()
                                                 if _safe_float(v) is not None}
        self.market_value_by_year: Dict[str, float] = {str(k): v for k, v in (market_value_by_year or {}).items()
                                                        if _safe_float(v) is not None}
        if not self.market_value_by_year and self.market_cap and self.years and source != "yahoo":
            # Uploaded data: the user-supplied market cap is applied to the latest year only.
            self.market_value_by_year = {self.years[-1]: self.market_cap}

    # -----------------------------------------------------------------
    @property
    def is_financial(self) -> bool:
        """Banks / insurers: liquidity, gross margin, Altman Z and Piotroski don't apply."""
        if any(h in str(self.industry).lower() for h in FINANCIAL_INDUSTRY_HINTS):
            return True
        # financial-sector company that reports no classified balance sheet (no current assets)
        if "financial" in str(self.sector).lower() and self.years:
            return self.get_raw_value("balance_sheet", "current_assets", self.years[-1]) is None
        return False

    @staticmethod
    def _normalize_df(df: Optional[pd.DataFrame]) -> pd.DataFrame:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()
        out = df.copy()
        out.index = [str(i).strip() for i in out.index]
        cols = []
        for c in out.columns:
            if isinstance(c, (pd.Timestamp, np.datetime64)):
                cols.append(str(pd.to_datetime(c).year))
            else:
                s = str(c).strip()
                if s.endswith(".0") and s[:-2].isdigit():
                    s = s[:-2]
                digits = "".join(ch for ch in s if ch.isdigit())
                cols.append(digits[:4] if len(digits) >= 4 else s)
        out.columns = cols
        out = out.loc[:, ~out.columns.duplicated()]
        out = out[[c for c in out.columns if len(c) == 4 and c.isdigit()]]
        for c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.loc[~out.index.duplicated()]
        # Yahoo often adds an extra oldest column holding only 1-6 values. A year with
        # under 30% of the best-filled column's data is a stub and is dropped.
        if not out.empty:
            counts = out.notna().sum()
            keep = [c for c in out.columns if counts[c] >= max(1, 0.3 * counts.max())]
            out = out[keep]
        return out

    def _df(self, statement: str) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
        if statement == "income":
            return self.income_statement, STATEMENT_ALIASES["income"]
        if statement in ("balance_sheet", "balance"):
            return self.balance_sheet, STATEMENT_ALIASES["balance_sheet"]
        if statement in ("cashflow", "cash_flow"):
            return self.cash_flow, STATEMENT_ALIASES["cashflow"]
        return pd.DataFrame(), {}

    def _lookup(self, statement: str, aliases: List[str], year: str) -> Optional[float]:
        df, _ = self._df(statement)
        if df.empty or year not in df.columns:
            return None
        lower = {str(i).lower(): i for i in df.index}
        for alias in aliases:
            idx = alias if alias in df.index else lower.get(alias.lower())
            if idx is not None:
                f = _safe_float(df.loc[idx, year])
                if f is not None:
                    return f
        return None

    def get_raw_value(self, statement: str, item_key: str, year: str) -> Optional[float]:
        """One canonical line item for one year (None if not reported and not derivable)."""
        year = str(year)
        stmt = {"balance": "balance_sheet", "cash_flow": "cashflow"}.get(statement, statement)
        _, alias_map = self._df(stmt)
        if item_key == "ebit":  # EBIT = Operating Income throughout this project
            return self.get_raw_value("income", "operating_income", year)

        # Items computed first so the Python engine and the Excel formulas agree
        if stmt == "balance_sheet" and item_key == "working_capital":
            ca = self.get_raw_value(stmt, "current_assets", year)
            cl = self.get_raw_value(stmt, "current_liabilities", year)
            if _all(ca, cl):
                return ca - cl
        if stmt == "cashflow" and item_key == "free_cash_flow":
            ocf = self.get_raw_value(stmt, "operating_cash_flow", year)
            capex = self.get_raw_value(stmt, "capital_expenditure", year)
            if _all(ocf, capex):
                return ocf - abs(capex)

        aliases = list(alias_map.get(item_key, [item_key]))
        if stmt == "income" and item_key == "operating_income" and self.source != "yahoo":
            aliases.append("EBIT")  # uploads may label the line "EBIT"
        val = self._lookup(stmt, aliases, year)
        if val is not None:
            return val

        # Fallback derivations (only from reported numbers)
        if stmt == "income":
            if item_key == "gross_profit":
                rev = self.get_raw_value("income", "revenue", year)
                cogs = self.get_raw_value("income", "cost_of_revenue", year)
                if _all(rev, cogs):
                    return rev - cogs
            if item_key == "operating_income":
                gp = self._lookup("income", alias_map["gross_profit"], year)
                opex = self.get_raw_value("income", "operating_expense", year)
                if _all(gp, opex):
                    return gp - opex
        elif stmt == "balance_sheet":
            if item_key == "cash_and_sti":
                cash = self.get_raw_value(stmt, "cash_and_equivalents", year)
                sti = self.get_raw_value(stmt, "short_term_investments", year)
                if cash is not None:
                    return cash + (sti or 0.0)  # short-term investments not reported -> none held
            if item_key == "total_debt":
                cd = self.get_raw_value(stmt, "current_debt", year)
                ltd = self.get_raw_value(stmt, "long_term_debt", year)
                if cd is not None or ltd is not None:
                    return (cd or 0.0) + (ltd or 0.0)
            if item_key == "total_liabilities":
                ta = self.get_raw_value(stmt, "total_assets", year)
                eq = self._lookup(stmt, alias_map["total_equity_incl_minority"], year)
                if eq is None:
                    eq = self.get_raw_value(stmt, "stockholders_equity", year)
                if _all(ta, eq):
                    return ta - eq
        return None

    def get_series(self, statement: str, item_key: str) -> pd.Series:
        return pd.Series({y: self.get_raw_value(statement, item_key, y) for y in self.years},
                         index=self.years, name=item_key, dtype=object)

    def get_market_value(self, year: str) -> Optional[float]:
        """Market value of equity at fiscal year end (price x shares), or None."""
        year = str(year)
        if year in self.market_value_by_year:
            return _safe_float(self.market_value_by_year[year])
        price = _safe_float(self.price_by_year.get(year))
        shares = self.get_raw_value("balance_sheet", "shares_outstanding", year)
        if _all(price, shares):
            return price * shares
        return None

    def prev_year(self, year: str) -> Optional[str]:
        i = self.years.index(year) if year in self.years else -1
        return self.years[i - 1] if i > 0 else None

    # -----------------------------------------------------------------
    @classmethod
    def from_yfinance(cls, ticker_str: str) -> "FinancialData":
        """Annual statements + metadata + fiscal-year-end prices from Yahoo Finance."""
        if yf is None:
            raise RuntimeError("yfinance is not installed")
        sym = ticker_str.upper().strip()
        ticker = yf.Ticker(sym)
        try:
            info = ticker.info or {}
        except Exception:
            info = {}
        inc, bs, cf = ticker.financials, ticker.balance_sheet, ticker.cashflow

        # Close price on the last trading day on/before each balance-sheet date
        price_by_year: Dict[str, float] = {}
        try:
            dates = sorted(pd.Timestamp(c) for c in bs.columns)
            if dates:
                hist = ticker.history(start=dates[0] - pd.Timedelta(days=10),
                                      end=dates[-1] + pd.Timedelta(days=2), auto_adjust=False)
                if not hist.empty:
                    idx = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
                    close = pd.Series(hist["Close"].values, index=idx)
                    for d in dates:
                        s = close[close.index <= d + pd.Timedelta(hours=23)]
                        if not s.empty and (d - s.index[-1]).days <= 7:
                            price_by_year[str(d.year)] = float(s.iloc[-1])
        except Exception:
            price_by_year = {}

        return cls(
            symbol=sym,
            company_name=info.get("longName") or info.get("shortName") or sym,
            income_statement=inc,
            balance_sheet=bs,
            cash_flow=cf,
            currency=info.get("financialCurrency") or info.get("currency") or "USD",
            sector=info.get("sector") or "General",
            industry=info.get("industry") or "General",
            market_cap=_safe_float(info.get("marketCap")),
            share_price=_safe_float(info.get("currentPrice") or info.get("regularMarketPrice")
                                    or info.get("previousClose")),
            price_by_year=price_by_year,
            source="yahoo",
        )

    # -----------------------------------------------------------------
    def to_snapshot(self) -> Dict[str, Any]:
        """JSON-serialisable copy (used for offline tests and the offline fallback)."""
        def frame(df):
            return {str(i): {y: _safe_float(df.loc[i, y]) for y in df.columns if _safe_float(df.loc[i, y]) is not None}
                    for i in df.index}
        return {"symbol": self.symbol, "company_name": self.company_name, "currency": self.currency,
                "sector": self.sector, "industry": self.industry, "market_cap": self.market_cap,
                "share_price": self.share_price, "price_by_year": self.price_by_year, "source": self.source,
                "income": frame(self.income_statement), "balance_sheet": frame(self.balance_sheet),
                "cashflow": frame(self.cash_flow)}

    @classmethod
    def from_snapshot(cls, snap: Dict[str, Any]) -> "FinancialData":
        def df(d):
            return pd.DataFrame.from_dict(d, orient="index") if d else pd.DataFrame()
        return cls(symbol=snap["symbol"], company_name=snap.get("company_name"), income_statement=df(snap.get("income")),
                   balance_sheet=df(snap.get("balance_sheet")), cash_flow=df(snap.get("cashflow")),
                   currency=snap.get("currency", "USD"), sector=snap.get("sector", "General"),
                   industry=snap.get("industry", "General"), market_cap=snap.get("market_cap"),
                   share_price=snap.get("share_price"), price_by_year=snap.get("price_by_year"),
                   source=snap.get("source", "yahoo"))

    @classmethod
    def from_excel_or_csv(
        cls,
        filepath_or_buffer: Any,
        symbol: str = "CUSTOM",
        company_name: str = "Uploaded Company",
        currency: str = "USD",
        market_cap: Optional[float] = None,
        sector: str = "General",
        industry: str = "General",
    ) -> "FinancialData":
        """
        Load statements from the templates in ``templates/``:
        * .xlsx with sheets 'Income Statement', 'Balance Sheet', 'Cash Flow'
          (column A = line item, then one column per fiscal year), or
        * .csv with columns Statement, Line Item, <year>, <year>, ...
        """
        inc_df, bs_df, cf_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        name = filepath_or_buffer if isinstance(filepath_or_buffer, str) else getattr(filepath_or_buffer, "name", "")
        if str(name).lower().endswith((".xlsx", ".xls")):
            xl = pd.ExcelFile(filepath_or_buffer)
            sheets = {s.lower().replace(" ", "").replace("_", ""): s for s in xl.sheet_names}
            for key, candidates in (("income", ["incomestatement", "income", "is"]),
                                    ("balance", ["balancesheet", "balance", "bs"]),
                                    ("cashflow", ["cashflow", "cashflowstatement", "cf", "cashflows"])):
                found = next((sheets[c] for c in candidates if c in sheets), None)
                if not found:
                    continue
                sdf = pd.read_excel(xl, sheet_name=found)
                if sdf.empty:
                    continue
                sdf = sdf.set_index(sdf.columns[0])
                if key == "income":
                    inc_df = sdf
                elif key == "balance":
                    bs_df = sdf
                else:
                    cf_df = sdf
        else:
            raw = pd.read_csv(filepath_or_buffer)
            raw.columns = [str(c).strip() for c in raw.columns]
            lower = [c.lower() for c in raw.columns]
            if "statement" in lower:
                stmt_col = raw.columns[lower.index("statement")]
                item_col = next(c for c in raw.columns if c != stmt_col)
                for stmt_type, sub in raw.groupby(stmt_col):
                    sname = str(stmt_type).lower().strip()
                    sub = sub.drop(columns=[stmt_col]).set_index(item_col)
                    if "income" in sname or sname == "is":
                        inc_df = sub
                    elif "balance" in sname or sname == "bs":
                        bs_df = sub
                    elif "cash" in sname or sname == "cf":
                        cf_df = sub
            else:
                inc_df = raw.set_index(raw.columns[0])
        return cls(symbol=symbol, company_name=company_name, income_statement=inc_df, balance_sheet=bs_df,
                   cash_flow=cf_df, currency=currency, market_cap=market_cap, sector=sector,
                   industry=industry, source="upload")


# =====================================================================
# Analyzer
# =====================================================================
def _zone(z: Optional[float], safe: float, distress: float) -> str:
    if z is None:
        return "n/a"
    if z > safe:
        return "Safe Zone"
    if z >= distress:
        return "Grey Zone"
    return "Distress Zone"


class FinancialAnalyzer:
    """All ratio families, DuPont, Altman, Piotroski, common-size, trend and the health report."""

    def __init__(self, data: FinancialData):
        self.data = data
        self.years = data.years

    # shorthand
    def _v(self, stmt: str, key: str, y: Optional[str]) -> Optional[float]:
        return None if y is None else self.data.get_raw_value(stmt, key, y)

    def _avg_bal(self, key: str, y: str) -> Optional[float]:
        return _avg(self._v("balance_sheet", key, y), self._v("balance_sheet", key, self.data.prev_year(y)))

    # 1. Liquidity --------------------------------------------------------
    def calculate_liquidity_ratios(self) -> pd.DataFrame:
        """Current = CA/CL; Quick = (Cash + ST investments + Receivables)/CL; Cash = (Cash + ST inv.)/CL."""
        rec: Dict[str, Dict[str, Optional[float]]] = {}
        for y in self.years:
            ca = self._v("balance_sheet", "current_assets", y)
            cl = self._v("balance_sheet", "current_liabilities", y)
            cash_sti = self._v("balance_sheet", "cash_and_sti", y)
            receivables = self._v("balance_sheet", "receivables", y)
            rec[y] = {
                "Current Ratio": _safe_div(ca, cl),
                "Quick Ratio": _safe_div(cash_sti + receivables, cl) if _all(cash_sti, receivables) else None,
                "Cash Ratio": _safe_div(cash_sti, cl),
            }
        return pd.DataFrame(rec, index=["Current Ratio", "Quick Ratio", "Cash Ratio"], columns=self.years)

    # 2. Profitability ----------------------------------------------------
    def effective_tax_rate(self, y: str) -> Optional[float]:
        """Tax provision / pre-tax income. 0% if pre-tax income <= 0; None if not usable."""
        pretax = self._v("income", "pretax_income", y)
        tax = self._v("income", "tax_provision", y)
        if not _all(pretax, tax):
            return None
        if pretax <= 0:
            return 0.0
        rate = tax / pretax
        return rate if 0.0 <= rate <= 1.0 else None

    def calculate_profitability_ratios(self) -> pd.DataFrame:
        """Margins on revenue; ROA/ROE on ending and average balances; ROIC = NOPAT / (Debt + Equity)."""
        rows = ["Gross Margin", "Operating Margin", "Net Profit Margin", "Effective Tax Rate",
                "Return on Assets (ROA)", "ROA (avg. assets)", "Return on Equity (ROE)", "ROE (avg. equity)",
                "Return on Invested Capital (ROIC)"]
        rec = {}
        for y in self.years:
            rev = self._v("income", "revenue", y)
            ni = self._v("income", "net_income", y)
            op = self._v("income", "operating_income", y)
            ta = self._v("balance_sheet", "total_assets", y)
            eq = self._v("balance_sheet", "stockholders_equity", y)
            debt = self._v("balance_sheet", "total_debt", y)
            t = self.effective_tax_rate(y)
            nopat = op * (1 - t) if _all(op, t) else None
            ic = debt + eq if _all(debt, eq) else None
            rec[y] = {
                "Gross Margin": _safe_div(self._v("income", "gross_profit", y), rev),
                "Operating Margin": _safe_div(op, rev),
                "Net Profit Margin": _safe_div(ni, rev),
                "Effective Tax Rate": t,
                "Return on Assets (ROA)": _safe_div(ni, ta),
                "ROA (avg. assets)": _safe_div(ni, self._avg_bal("total_assets", y)),
                "Return on Equity (ROE)": _safe_div(ni, eq),
                "ROE (avg. equity)": _safe_div(ni, self._avg_bal("stockholders_equity", y)),
                "Return on Invested Capital (ROIC)": _safe_div(nopat, ic) if (ic is not None and ic > 0) else None,
            }
        return pd.DataFrame(rec, index=rows, columns=self.years)

    # 3. Solvency ---------------------------------------------------------
    def calculate_solvency_ratios(self) -> pd.DataFrame:
        """D/E, D/A, Equity multiplier (TA/Equity), Interest coverage = Operating income / |Interest expense|."""
        rows = ["Debt-to-Equity", "Debt-to-Assets", "Financial Leverage (Multiplier)", "Interest Coverage"]
        rec = {}
        for y in self.years:
            debt = self._v("balance_sheet", "total_debt", y)
            eq = self._v("balance_sheet", "stockholders_equity", y)
            ta = self._v("balance_sheet", "total_assets", y)
            op = self._v("income", "operating_income", y)
            interest = self._v("income", "interest_expense", y)
            rec[y] = {
                "Debt-to-Equity": _safe_div(debt, eq),
                "Debt-to-Assets": _safe_div(debt, ta),
                "Financial Leverage (Multiplier)": _safe_div(ta, eq),
                # interest expense may be stored as a positive or negative number -> use its size
                "Interest Coverage": _safe_div(op, abs(interest)) if interest is not None else None,
            }
        return pd.DataFrame(rec, index=rows, columns=self.years)

    # 4. Efficiency -------------------------------------------------------
    def calculate_efficiency_ratios(self) -> pd.DataFrame:
        """Turnover ratios and working-capital days (365-day year, ending balances unless 'avg.')."""
        rows = ["Asset Turnover", "Asset Turnover (avg. assets)", "Inventory Turnover",
                "Inventory Turnover (avg. inventory)", "Days Sales Outstanding (DSO)",
                "Days Inventory Outstanding (DIO)", "Days Payable Outstanding (DPO)", "Cash Conversion Cycle (CCC)"]
        rec = {}
        for y in self.years:
            rev = self._v("income", "revenue", y)
            cogs = self._v("income", "cost_of_revenue", y)
            ta = self._v("balance_sheet", "total_assets", y)
            inv = self._v("balance_sheet", "inventory", y)
            ar = self._v("balance_sheet", "accounts_receivable", y)
            ap = self._v("balance_sheet", "accounts_payable", y)
            pos_rev = rev if (rev is not None and rev > 0) else None
            pos_cogs = cogs if (cogs is not None and cogs > 0) else None
            if self.data.is_financial:  # a bank's receivables are loans, not trade receivables
                ar = None
            dso = _safe_div(ar, pos_rev) * DAYS_IN_YEAR if _all(ar, pos_rev) else None
            dio = _safe_div(inv, pos_cogs) * DAYS_IN_YEAR if _all(inv, pos_cogs) else None
            dpo = _safe_div(ap, pos_cogs) * DAYS_IN_YEAR if _all(ap, pos_cogs) else None
            if _all(dso, dio, dpo):
                ccc = dso + dio - dpo
            elif _all(dso, dpo) and inv is None:
                ccc = dso - dpo  # no inventory reported (service company): DIO counts as 0
            else:
                ccc = None
            rec[y] = {
                "Asset Turnover": _safe_div(rev, ta),
                "Asset Turnover (avg. assets)": _safe_div(rev, self._avg_bal("total_assets", y)),
                "Inventory Turnover": _safe_div(cogs, inv) if (inv is not None and inv > 0) else None,
                "Inventory Turnover (avg. inventory)": _safe_div(cogs, self._avg_bal("inventory", y)),
                "Days Sales Outstanding (DSO)": dso,
                "Days Inventory Outstanding (DIO)": dio,
                "Days Payable Outstanding (DPO)": dpo,
                "Cash Conversion Cycle (CCC)": ccc,
            }
        return pd.DataFrame(rec, index=rows, columns=self.years)

    # 5. Cash-flow quality ------------------------------------------------
    def calculate_cash_flow_quality(self) -> pd.DataFrame:
        """CFO/NI, FCF = CFO - |Capex|, FCF margin, Capex/Revenue, Sloan accruals = (NI - CFO)/Total assets."""
        rows = ["Operating Cash Flow / Net Income", "Free Cash Flow", "FCF Margin", "Capex / Revenue",
                "Sloan Accrual Ratio"]
        rec = {}
        for y in self.years:
            ocf = self._v("cashflow", "operating_cash_flow", y)
            capex = self._v("cashflow", "capital_expenditure", y)
            ni = self._v("income", "net_income", y)
            rev = self._v("income", "revenue", y)
            ta = self._v("balance_sheet", "total_assets", y)
            fcf = self._v("cashflow", "free_cash_flow", y)
            rec[y] = {
                "Operating Cash Flow / Net Income": _safe_div(ocf, ni) if (ni is not None and ni > 0) else None,
                "Free Cash Flow": fcf,
                "FCF Margin": _safe_div(fcf, rev),
                "Capex / Revenue": _safe_div(abs(capex), rev) if capex is not None else None,
                "Sloan Accrual Ratio": _safe_div(ni - ocf, ta) if _all(ni, ocf) else None,
            }
        return pd.DataFrame(rec, index=rows, columns=self.years)

    # 6. Growth -----------------------------------------------------------
    def calculate_growth_metrics(self) -> pd.DataFrame:
        """Year-over-year growth: (this year - last year) / |last year|."""
        series = {
            "Revenue YoY Growth": self.data.get_series("income", "revenue"),
            "Operating Income YoY Growth": self.data.get_series("income", "operating_income"),
            "Net Income YoY Growth": self.data.get_series("income", "net_income"),
            "Diluted EPS YoY Growth": self.data.get_series("income", "diluted_eps"),
            "Free Cash Flow YoY Growth": self.data.get_series("cashflow", "free_cash_flow"),
        }
        rec = {}
        for name, s in series.items():
            out = {}
            for i, y in enumerate(self.years):
                cur = _safe_float(s.get(y))
                prev = _safe_float(s.get(self.years[i - 1])) if i > 0 else None
                out[y] = (cur - prev) / abs(prev) if (_all(cur, prev) and prev != 0) else None
            rec[name] = out
        return pd.DataFrame(rec).T.reindex(columns=self.years)

    # 7. DuPont -----------------------------------------------------------
    def calculate_dupont_analysis(self) -> Dict[str, pd.DataFrame]:
        """
        3-step: ROE = (NI/Revenue) x (Revenue/Assets) x (Assets/Equity)
        5-step: ROE = (NI/EBT) x (EBT/EBIT) x (EBIT/Revenue) x (Revenue/Assets) x (Assets/Equity)
        EBIT = Operating Income; ending balances, so both products equal NI / ending equity exactly.
        """
        three, five = {}, {}
        for y in self.years:
            rev = self._v("income", "revenue", y)
            ni = self._v("income", "net_income", y)
            ebit = self._v("income", "operating_income", y)
            ebt = self._v("income", "pretax_income", y)
            ta = self._v("balance_sheet", "total_assets", y)
            eq = self._v("balance_sheet", "stockholders_equity", y)
            npm, at, fl = _safe_div(ni, rev), _safe_div(rev, ta), _safe_div(ta, eq)
            roe = _safe_div(ni, eq)
            three[y] = {
                "Net Profit Margin": npm,
                "Asset Turnover": at,
                "Financial Leverage": fl,
                "3-Step DuPont ROE": npm * at * fl if _all(npm, at, fl) else None,
                "Actual Reported ROE": roe,
            }
            tb, ib, om = _safe_div(ni, ebt), _safe_div(ebt, ebit), _safe_div(ebit, rev)
            five[y] = {
                "Tax Burden (NI / EBT)": tb,
                "Interest Burden (EBT / EBIT)": ib,
                "Operating Margin (EBIT / Rev)": om,
                "Asset Turnover (Rev / Assets)": at,
                "Financial Leverage (Assets / Eq)": fl,
                "5-Step DuPont ROE": tb * ib * om * at * fl if _all(tb, ib, om, at, fl) else None,
                "Actual Reported ROE": roe,
            }
        return {"three_step": pd.DataFrame(three, columns=self.years),
                "five_step": pd.DataFrame(five, columns=self.years)}

    # 8. Altman -----------------------------------------------------------
    ALTMAN_NOTE = ("Z = original Altman (1968) model for publicly traded manufacturers, X4 uses the market value "
                   "of equity at fiscal year end. Z'' = Altman (1995) model for non-manufacturers and emerging "
                   "markets, X4 uses book equity and there is no sales term. Neither model is designed for banks "
                   "or insurers.")

    def calculate_altman_z_score(self) -> pd.DataFrame:
        """
        Z   = 1.2 X1 + 1.4 X2 + 3.3 X3 + 0.6 X4 + 0.999 X5   (safe > 2.99, grey 1.81-2.99, distress < 1.81)
        Z'' = 6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4''        (safe > 2.60, grey 1.10-2.60, distress < 1.10)
        X1 = Working capital / TA, X2 = Retained earnings / TA, X3 = EBIT (operating income) / TA,
        X4 = Market value of equity / Total liabilities, X4'' = Book equity / Total liabilities, X5 = Sales / TA.
        """
        rec = {}
        fin = self.data.is_financial
        for y in self.years:
            ta = self._v("balance_sheet", "total_assets", y)
            tl = self._v("balance_sheet", "total_liabilities", y)
            mve = self.data.get_market_value(y)
            x1 = _safe_div(self._v("balance_sheet", "working_capital", y), ta)
            x2 = _safe_div(self._v("balance_sheet", "retained_earnings", y), ta)
            x3 = _safe_div(self._v("income", "operating_income", y), ta)
            x4 = _safe_div(mve, tl)
            x4b = _safe_div(self._v("balance_sheet", "stockholders_equity", y), tl)
            x5 = _safe_div(self._v("income", "revenue", y), ta)
            z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 0.999 * x5 if _all(x1, x2, x3, x4, x5) else None
            z2 = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4b if _all(x1, x2, x3, x4b) else None
            if fin:
                z = z2 = None
            na_zone = "Not applicable (financial company)" if fin else "n/a"
            rec[y] = {
                "X1 (Working Capital / Assets)": x1,
                "X2 (Retained Earnings / Assets)": x2,
                "X3 (EBIT / Assets)": x3,
                "X4 (Market Value of Equity / Liabilities)": x4,
                "X4'' (Book Equity / Liabilities)": x4b,
                "X5 (Revenue / Assets)": x5,
                "Market Value of Equity": mve,
                "Altman Z-Score": z,
                "Zone (Original)": _zone(z, 2.99, 1.81) if z is not None else na_zone,
                "Altman Z''-Score (Non-Mfg)": z2,
                "Zone (Non-Mfg)": _zone(z2, 2.60, 1.10) if z2 is not None else na_zone,
            }
        return pd.DataFrame(rec, columns=self.years)

    # 9. Piotroski --------------------------------------------------------
    PIOTROSKI_CRITERIA = [
        "1. Positive ROA (NI / beginning assets > 0)",
        "2. Positive Operating Cash Flow (CFO > 0)",
        "3. Higher ROA than last year",
        "4. Quality of Earnings (CFO > Net Income)",
        "5. Lower Long-Term Debt / avg. Assets",
        "6. Higher Current Ratio",
        "7. No New Shares Issued",
        "8. Higher Gross Margin",
        "9. Higher Asset Turnover (Sales / beginning assets)",
    ]

    def calculate_piotroski_f_score(self) -> Dict[str, Any]:
        """
        Piotroski (2000) F-score, one point per signal, for year t versus t-1:
          1 ROA_t = NI_t / TA_(t-1) > 0          2 CFO_t > 0
          3 ROA_t > ROA_(t-1)                    4 CFO_t > NI_t (accruals)
          5 LTD_t / avgTA_t < LTD_(t-1) / avgTA_(t-1)   (both zero also scores 1)
          6 Current ratio_t > Current ratio_(t-1)
          7 Shares outstanding_t <= shares_(t-1) (no new equity issued)
          8 Gross margin_t > Gross margin_(t-1)
          9 Sales_t / TA_(t-1) > Sales_(t-1) / TA_(t-2)
        A signal whose inputs are missing is None ("n/a"), never 0. The total is only
        reported when all 9 signals can be measured.
        """
        ys = self.years

        def g(stmt, key, i):
            return self._v(stmt, key, ys[i]) if 0 <= i < len(ys) else None

        def shares(i):
            s = g("balance_sheet", "shares_outstanding", i)
            return s if s is not None else g("income", "shares_diluted", i)

        def roa(i):  # NI / beginning-of-year total assets
            return _safe_div(g("income", "net_income", i), g("balance_sheet", "total_assets", i - 1))

        def turn(i):
            return _safe_div(g("income", "revenue", i), g("balance_sheet", "total_assets", i - 1))

        def lev(i):
            ltd = g("balance_sheet", "long_term_debt", i)
            if ltd is None and 0 <= i < len(ys) and g("balance_sheet", "total_assets", i) is not None \
                    and not g("balance_sheet", "total_debt", i):
                ltd = 0.0  # balance sheet reported but no debt at all -> leverage is zero
            avg_ta = _avg(g("balance_sheet", "total_assets", i), g("balance_sheet", "total_assets", i - 1))
            return _safe_div(ltd, avg_ta) if ltd is not None else None

        def cr(i):
            return _safe_div(g("balance_sheet", "current_assets", i), g("balance_sheet", "current_liabilities", i))

        def gm(i):
            return _safe_div(g("income", "gross_profit", i), g("income", "revenue", i))

        def gt(a, b):
            return None if not _all(a, b) else int(a > b)

        detailed, scores, labels = {}, {}, {}
        for i, y in enumerate(ys):
            ni, cfo = g("income", "net_income", i), g("cashflow", "operating_cash_flow", i)
            r = roa(i)
            l_now, l_prev = lev(i), lev(i - 1)
            if _all(l_now, l_prev):
                f5 = int(l_now < l_prev or (l_now == 0 and l_prev == 0))
            else:
                f5 = None
            s_now, s_prev = shares(i), shares(i - 1)
            f = [
                None if r is None else int(r > 0),
                None if cfo is None else int(cfo > 0),
                gt(r, roa(i - 1)),
                gt(cfo, ni),
                f5,
                gt(cr(i), cr(i - 1)),
                None if not _all(s_now, s_prev) else int(s_now <= s_prev),
                gt(gm(i), gm(i - 1)),
                gt(turn(i), turn(i - 1)),
            ]
            if self.data.is_financial:
                f = [None] * 9
            available = sum(v is not None for v in f)
            if available == 9:
                score: Optional[int] = int(sum(f))
                label = ("Strong (8-9)" if score >= 8 else "Moderate (5-7)" if score >= 5 else "Weak (0-4)")
            else:
                score = None
                label = ("Not applicable (financial company)" if self.data.is_financial
                         else f"n/a - only {available}/9 signals measurable")
            scores[y], labels[y] = score, label
            col = dict(zip(self.PIOTROSKI_CRITERIA, f))
            col["Total Piotroski F-Score"] = score
            col["Signals Available"] = f"{available}/9"
            col["Interpretation"] = label
            detailed[y] = col
        return {"detailed": pd.DataFrame(detailed, columns=ys), "scores": scores, "interpretations": labels}

    # 10. Common size -----------------------------------------------------
    @staticmethod
    def _monetary_rows(df: pd.DataFrame) -> pd.DataFrame:
        keep = [i for i in df.index if not any(h in str(i).lower() for h in _NON_MONETARY_HINTS)]
        return df.loc[keep]

    def calculate_common_size(self) -> Dict[str, pd.DataFrame]:
        """Income statement as % of revenue, balance sheet as % of total assets (counts/EPS rows excluded)."""
        inc = self._monetary_rows(self.data.income_statement)
        bs = self._monetary_rows(self.data.balance_sheet)
        cs_inc = pd.DataFrame(index=inc.index, columns=self.years, dtype=float)
        cs_bs = pd.DataFrame(index=bs.index, columns=self.years, dtype=float)
        for y in self.years:
            rev = self._v("income", "revenue", y)
            ta = self._v("balance_sheet", "total_assets", y)
            if rev and rev > 0 and y in inc.columns:
                cs_inc[y] = inc[y].astype(float) / rev * 100.0
            if ta and ta > 0 and y in bs.columns:
                cs_bs[y] = bs[y].astype(float) / ta * 100.0
        return {"income_statement": cs_inc, "balance_sheet": cs_bs}

    # 11. Trend -----------------------------------------------------------
    def calculate_horizontal_analysis(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """YoY % change = (t - (t-1)) / |t-1| x 100; index = t / |base year| x 100 (base = oldest year)."""
        def _h(df: pd.DataFrame):
            if df.empty or not self.years:
                return pd.DataFrame(), pd.DataFrame()
            df = df.astype(float)
            base = df[self.years[0]]
            idx = df.div(base.abs().where(base != 0), axis=0) * 100.0
            yoy = pd.DataFrame(index=df.index, columns=self.years, dtype=float)
            for i in range(1, len(self.years)):
                prev = df[self.years[i - 1]]
                yoy[self.years[i]] = (df[self.years[i]] - prev) / prev.abs().where(prev != 0) * 100.0
            return yoy, idx

        inc_yoy, inc_idx = _h(self.data.income_statement)
        bs_yoy, bs_idx = _h(self.data.balance_sheet)
        cf_yoy, cf_idx = _h(self.data.cash_flow)
        return {"income_statement": {"yoy": inc_yoy, "indexed": inc_idx},
                "balance_sheet": {"yoy": bs_yoy, "indexed": bs_idx},
                "cash_flow": {"yoy": cf_yoy, "indexed": cf_idx}}

    # 12. Health report ---------------------------------------------------
    def generate_health_report(self) -> Dict[str, Any]:
        """Deterministic rules -> strengths / weaknesses / red flags for the latest fiscal year."""
        strengths: List[Dict[str, str]] = []
        weaknesses: List[Dict[str, str]] = []
        red_flags: List[Dict[str, str]] = []
        notes: List[str] = []
        if not self.years:
            return {"overall_status": "Insufficient Data", "status_color": "gray",
                    "summary": "No financial statement data available.", "strengths": [], "weaknesses": [],
                    "red_flags": [], "notes": [], "latest_year": None,
                    "stats": {"strengths_count": 0, "weaknesses_count": 0, "red_flags_count": 0}}

        y = self.years[-1]
        cur = self.data.currency
        liq, prof, solv = (self.calculate_liquidity_ratios(), self.calculate_profitability_ratios(),
                           self.calculate_solvency_ratios())
        cfq, growth = self.calculate_cash_flow_quality(), self.calculate_growth_metrics()
        altman, pio = self.calculate_altman_z_score(), self.calculate_piotroski_f_score()

        def val(df, row):
            return _safe_float(df.loc[row, y]) if row in df.index else None

        def add(lst, cat, title, detail):
            lst.append({"category": cat, "title": title, "detail": detail})

        if self.data.is_financial:
            notes.append("This looks like a bank or other financial company. Current ratio, gross margin, "
                         "inventory days, Altman Z and Piotroski F are not meaningful for it and are shown as n/a. "
                         "Banks are analysed with capital ratios (CET1), net interest margin and loan-loss data instead.")

        # Cash flow & earnings quality
        ni = self._v("income", "net_income", y)
        ocf = self._v("cashflow", "operating_cash_flow", y)
        ocf_ni, fcf, fcf_m = val(cfq, "Operating Cash Flow / Net Income"), val(cfq, "Free Cash Flow"), val(cfq, "FCF Margin")
        if self.data.is_financial:
            notes.append("Cash-flow rules are skipped for financial companies: a bank's operating cash flow "
                         "swings with deposits, loans and trading assets.")
        elif ocf is not None and ocf < 0:
            add(red_flags, "Cash Flow", "Negative operating cash flow",
                f"Operating cash flow in FY{y} was negative ({ocf:,.0f} {cur}): the core business used more cash than it brought in.")
        elif ocf_ni is not None:
            if ocf_ni >= 1.10:
                add(strengths, "Earnings Quality", f"Cash flow backs up profits (CFO/NI {ocf_ni:.2f}x)",
                    f"Operating cash flow was {ocf_ni:.2f}x net income, so reported profit is turning into cash.")
            elif ocf_ni < 0.70:
                add(red_flags, "Earnings Quality", f"Profit not turning into cash (CFO/NI {ocf_ni:.2f}x)",
                    f"Operating cash flow was only {ocf_ni*100:.0f}% of net income. Check receivables, inventory and non-cash gains.")
        if self.data.is_financial:
            pass
        elif fcf is not None and fcf > 0 and fcf_m is not None and fcf_m > 0.15:
            add(strengths, "Cash Generation", f"High free-cash-flow margin ({fcf_m*100:.1f}%)",
                f"Free cash flow was {fcf_m*100:.1f}% of revenue, leaving cash for dividends, buybacks or debt repayment.")
        elif fcf is not None and fcf < 0:
            add(weaknesses, "Cash Generation", "Negative free cash flow",
                f"Free cash flow in FY{y} was {fcf:,.0f} {cur}: capital spending was larger than operating cash flow.")

        # Solvency & credit
        z, zone = val(altman, "Altman Z-Score"), str(altman.loc["Zone (Original)", y])
        z2, zone2 = val(altman, "Altman Z''-Score (Non-Mfg)"), str(altman.loc["Zone (Non-Mfg)", y])
        model, zval, zz, safe, dist = ("Altman Z", z, zone, 2.99, 1.81) if z is not None else ("Altman Z''", z2, zone2, 2.60, 1.10)
        if zval is not None:
            if zz == "Safe Zone":
                add(strengths, "Solvency & Credit", f"{model} in the safe zone ({zval:.2f})",
                    f"{model} of {zval:.2f} is above the {safe} safe threshold: low statistical bankruptcy risk.")
            elif zz == "Grey Zone":
                add(weaknesses, "Solvency & Credit", f"{model} in the grey zone ({zval:.2f})",
                    f"{model} of {zval:.2f} is between {dist} and {safe}: watch liquidity and leverage.")
            elif zz == "Distress Zone":
                add(red_flags, "Solvency & Credit", f"{model} in the distress zone ({zval:.2f})",
                    f"{model} of {zval:.2f} is below {dist}, the level linked with higher bankruptcy risk.")
        cov = val(solv, "Interest Coverage")
        if cov is not None:
            if cov < 1.5:
                add(red_flags, "Solvency", f"Weak interest coverage ({cov:.2f}x)",
                    f"Operating income covers interest expense only {cov:.2f}x (below 1.5x); a small fall in profit could make interest hard to pay.")
            elif cov > 8.0:
                add(strengths, "Solvency", f"Strong interest coverage ({cov:.1f}x)",
                    f"Operating income is {cov:.1f}x interest expense, a wide safety margin.")
        dte = val(solv, "Debt-to-Equity")
        eq = self._v("balance_sheet", "stockholders_equity", y)
        if eq is not None and eq < 0:
            add(weaknesses, "Capital Structure", "Negative shareholders' equity",
                "Book equity is negative (often caused by large buybacks), so ROE and debt-to-equity are not meaningful.")
        elif dte is not None:
            if dte > 3.0:
                add(weaknesses, "Capital Structure", f"High debt-to-equity ({dte:.2f}x)",
                    f"Debt is {dte:.2f}x book equity: the company relies heavily on borrowed money.")
            elif dte <= 0.60:
                add(strengths, "Capital Structure", f"Conservative leverage (D/E {dte:.2f}x)",
                    "Debt is modest relative to equity, which gives resilience in downturns.")

        # Liquidity
        crv, qr = val(liq, "Current Ratio"), val(liq, "Quick Ratio")
        if crv is not None:
            if crv < 1.0:
                add(weaknesses, "Liquidity", f"Current ratio below 1 ({crv:.2f}x)",
                    f"Current liabilities are larger than current assets ({crv:.2f}x). Fine for firms with strong cash flow and bargaining power, risky otherwise.")
            elif crv >= 1.8:
                add(strengths, "Liquidity", f"Comfortable current ratio ({crv:.2f}x)",
                    f"Current assets cover current liabilities {crv:.2f}x.")
        if qr is not None and qr < 0.70:
            add(weaknesses, "Liquidity", f"Low quick ratio ({qr:.2f}x)",
                "Cash, short-term investments and receivables cover less than 70% of current liabilities.")

        # Profitability
        roe, roic, om = val(prof, "Return on Equity (ROE)"), val(prof, "Return on Invested Capital (ROIC)"), val(prof, "Operating Margin")
        if roe is not None and (eq is None or eq > 0):
            if roe >= 0.20:
                add(strengths, "Profitability", f"High return on equity ({roe*100:.1f}%)",
                    f"Net income was {roe*100:.1f}% of year-end shareholders' equity.")
            elif roe < 0:
                add(red_flags, "Profitability", f"Negative return on equity ({roe*100:.1f}%)",
                    "The company lost money in the year.")
        if roic is not None and roic > 0.15:
            add(strengths, "Returns on Capital", f"High ROIC ({roic*100:.1f}%)",
                f"After-tax operating profit was {roic*100:.1f}% of debt + equity, well above a typical 8-10% cost of capital.")
        if om is not None:
            if om > 0.20:
                add(strengths, "Operating Efficiency", f"Wide operating margin ({om*100:.1f}%)",
                    f"The company keeps {om*100:.1f} cents of operating profit from each unit of revenue.")
            elif 0 <= om < 0.04:
                add(weaknesses, "Operating Efficiency", f"Thin operating margin ({om*100:.1f}%)",
                    "Little room to absorb cost increases or a drop in sales.")
            elif om < 0:
                add(red_flags, "Operating Efficiency", f"Operating loss ({om*100:.1f}% margin)",
                    "Operating expenses exceeded gross profit.")

        # Piotroski
        fs = pio["scores"].get(y)
        if fs is not None:
            if fs >= 8:
                add(strengths, "Fundamental Trend", f"Piotroski F-score {fs}/9",
                    "Profitability, balance sheet and efficiency nearly all improved versus last year.")
            elif fs <= 3:
                add(red_flags, "Fundamental Trend", f"Piotroski F-score {fs}/9",
                    "Most of the nine fundamental signals worsened versus last year.")

        # Growth
        if len(self.years) > 1:
            rg, ng = val(growth, "Revenue YoY Growth"), val(growth, "Net Income YoY Growth")
            if rg is not None:
                if rg > 0.15:
                    add(strengths, "Growth", f"Strong revenue growth (+{rg*100:.1f}%)", f"Revenue grew {rg*100:.1f}% year over year.")
                elif rg < -0.05:
                    add(weaknesses, "Growth", f"Revenue decline ({rg*100:.1f}%)", f"Revenue fell {abs(rg)*100:.1f}% year over year.")
            if _all(rg, ng) and ng < -0.20 and rg >= 0:
                add(weaknesses, "Operating Leverage", "Profit fell while sales grew",
                    f"Net income fell {abs(ng)*100:.1f}% although revenue grew {rg*100:.1f}%: costs rose faster than sales.")

        n_rf, n_st, n_wk = len(red_flags), len(strengths), len(weaknesses)
        name = self.data.company_name
        if n_rf == 0 and n_st >= 4:
            status, color = "Very Strong", "green"
            summary = f"{name} shows strong fundamentals in FY{y}: no red flags and {n_st} clear strengths."
        elif n_rf <= 1 and n_st >= 2:
            status, color = "Solid", "blue"
            summary = f"{name} looks financially sound in FY{y}, with {n_st} strengths and {n_wk + n_rf} item(s) to monitor."
        elif n_rf >= 2 or (n_rf >= 1 and n_st <= 1):
            status, color = "Elevated Risk", "red"
            summary = f"{name} shows {n_rf} red flag(s) in FY{y}. Review cash flow, debt and liquidity closely."
        else:
            status, color = "Mixed", "orange"
            summary = f"{name} has a mixed profile in FY{y}: {n_st} strengths against {n_wk} weaknesses."
        if self.data.is_financial:
            status, color = "Limited (financial company)", "gray"
            summary = (f"{name} is a bank or other financial company. Most rules here are built for operating "
                       f"companies, so only profitability and leverage were scored for FY{y}.")
        return {"overall_status": status, "status_color": color, "summary": summary, "strengths": strengths,
                "weaknesses": weaknesses, "red_flags": red_flags, "notes": notes, "latest_year": y,
                "stats": {"strengths_count": n_st, "weaknesses_count": n_wk, "red_flags_count": n_rf}}
