"""Historical data for the three-statement model: Yahoo Finance (live or offline snapshot) or a
CSV / Excel template.

Rules:
* Nothing is invented. A line that is not reported is shown as n/a (or 0 for a balance-sheet
  line that simply does not exist, e.g. no treasury stock) and listed in the warnings.
* Every reported total is kept. "Other" lines are disclosed differences between a reported
  subtotal and the lines shown, so each statement foots to the company's own totals.
* The historical balance check (Total assets - Total liabilities - Total equity, using the
  reported totals) is shown, never forced to zero.
Units: millions of the reporting currency.
"""
from __future__ import annotations

import io
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from model import NAN, StatementYear, isnum, nz

SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "yahoo_snapshot"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


@dataclass
class HistoricalData:
    years: List[StatementYear]
    company: str
    ticker: str
    currency: str
    source: str
    as_of: str = ""
    warnings: List[str] = field(default_factory=list)
    mapping: Optional[pd.DataFrame] = None       # which source line fed each model line


# ------------------------------------------------------------------ canonical items
# key: (label in template, statement, required)
ITEMS = {
    "revenue": ("Revenue", "IS", True),
    "cogs": ("Cost of goods sold", "IS", False),
    "sga": ("SG&A", "IS", False),
    "rd": ("R&D", "IS", False),
    "da": ("Depreciation & amortization", "IS", False),
    "ebit": ("Operating income (EBIT)", "IS", True),
    "interest_expense": ("Interest expense", "IS", False),
    "interest_income": ("Interest income", "IS", False),
    "ebt": ("Pre-tax income", "IS", True),
    "tax": ("Income tax", "IS", False),
    "ni_consolidated": ("Net income (consolidated)", "IS", False),
    "ni_common": ("Net income to common shareholders", "IS", True),
    "cash": ("Cash & cash equivalents", "BS", True),
    "st_investments": ("Short-term investments", "BS", False),
    "ar": ("Accounts receivable", "BS", False),
    "inventory": ("Inventory", "BS", False),
    "current_assets": ("Total current assets", "BS", False),
    "gross_ppe": ("Gross PP&E", "BS", False),
    "acc_dep": ("Accumulated depreciation", "BS", False),
    "net_ppe": ("Net PP&E", "BS", False),
    "total_assets": ("Total assets", "BS", True),
    "ap": ("Accounts payable", "BS", False),
    "current_liabilities": ("Total current liabilities", "BS", False),
    "current_debt": ("Short-term debt & current portion of long-term debt", "BS", False),
    "lt_debt": ("Long-term debt", "BS", False),
    "total_liabilities": ("Total liabilities", "BS", True),
    "common_stock": ("Common stock & APIC", "BS", False),
    "retained_earnings": ("Retained earnings", "BS", False),
    "treasury_stock": ("Treasury stock", "BS", False),
    "shareholders_equity": ("Total shareholders' equity", "BS", True),
    "nci": ("Non-controlling interests", "BS", False),
    "cfo": ("Cash from operations", "CF", False),
    "change_wc": ("Change in working capital", "CF", False),
    "capex": ("Capital expenditure", "CF", False),
    "cfi": ("Cash from investing", "CF", False),
    "debt_issued": ("Debt issued", "CF", False),
    "debt_repaid": ("Debt repaid", "CF", False),
    "dividends": ("Dividends paid", "CF", False),
    "buybacks": ("Share buybacks", "CF", False),
    "cff": ("Cash from financing", "CF", False),
    "beginning_cash": ("Beginning cash (cash-flow statement)", "CF", False),
    "ending_cash": ("Ending cash (cash-flow statement)", "CF", False),
}

YAHOO_LINES = {
    "revenue": ("IS", ["Total Revenue", "Operating Revenue"]),
    "cogs": ("IS", ["Cost Of Revenue", "Reconciled Cost Of Revenue"]),
    "gross_profit_reported": ("IS", ["Gross Profit"]),
    "sga": ("IS", ["Selling General And Administration"]),
    "rd": ("IS", ["Research And Development"]),
    "da": ("IS", ["Reconciled Depreciation"]),
    "ebit": ("IS", ["Operating Income", "Total Operating Income As Reported"]),
    "interest_expense": ("IS", ["Interest Expense", "Interest Expense Non Operating"]),
    "interest_income": ("IS", ["Interest Income", "Interest Income Non Operating"]),
    "ebt": ("IS", ["Pretax Income"]),
    "tax": ("IS", ["Tax Provision"]),
    "ni_consolidated": ("IS", ["Net Income Including Noncontrolling Interests"]),
    "ni_common": ("IS", ["Net Income Common Stockholders", "Net Income"]),
    "cash": ("BS", ["Cash And Cash Equivalents", "Cash Financial"]),
    "cash_and_sti": ("BS", ["Cash Cash Equivalents And Short Term Investments"]),
    "sti_line": ("BS", ["Other Short Term Investments"]),
    "ar": ("BS", ["Accounts Receivable", "Receivables"]),
    "inventory": ("BS", ["Inventory"]),
    "current_assets": ("BS", ["Current Assets"]),
    "gross_ppe": ("BS", ["Gross PPE"]),
    "acc_dep": ("BS", ["Accumulated Depreciation"]),
    "net_ppe": ("BS", ["Net PPE"]),
    "total_assets": ("BS", ["Total Assets"]),
    "ap": ("BS", ["Accounts Payable", "Payables"]),
    "current_liabilities": ("BS", ["Current Liabilities"]),
    "current_debt": ("BS", ["Current Debt", "Current Debt And Capital Lease Obligation"]),
    "lt_debt": ("BS", ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]),
    "total_liabilities": ("BS", ["Total Liabilities Net Minority Interest"]),
    "common_stock_par": ("BS", ["Common Stock", "Capital Stock"]),
    "apic": ("BS", ["Additional Paid In Capital"]),
    "retained_earnings": ("BS", ["Retained Earnings"]),
    "treasury_stock": ("BS", ["Treasury Stock"]),
    "shareholders_equity": ("BS", ["Stockholders Equity"]),
    "total_equity_gross": ("BS", ["Total Equity Gross Minority Interest"]),
    "nci_line": ("BS", ["Minority Interest"]),
    "cfo": ("CF", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
    "change_wc": ("CF", ["Change In Working Capital"]),
    "da_cf": ("CF", ["Depreciation And Amortization", "Depreciation Amortization Depletion"]),
    "capex": ("CF", ["Capital Expenditure", "Purchase Of PPE"]),
    "cfi": ("CF", ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities"]),
    "debt_issued": ("CF", ["Issuance Of Debt", "Long Term Debt Issuance"]),
    "debt_repaid": ("CF", ["Repayment Of Debt", "Long Term Debt Payments"]),
    "dividends": ("CF", ["Cash Dividends Paid", "Common Stock Dividend Paid"]),
    "buybacks": ("CF", ["Repurchase Of Capital Stock", "Common Stock Payments"]),
    "cff": ("CF", ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"]),
    "beginning_cash": ("CF", ["Beginning Cash Position"]),
    "ending_cash": ("CF", ["End Cash Position"]),
}


def build_year(label: str, period_end: str, v: Dict[str, float], warn: List[str]) -> StatementYear:
    """Turn canonical values (NaN = not reported) into a StatementYear. Residual 'other' lines
    are computed from reported totals and disclosed; nothing is plugged."""
    g = lambda k: v.get(k, NAN)
    y = StatementYear(year=label, period_end=period_end)
    miss = y.missing

    def need(k):
        if not isnum(g(k)):
            raise ValueError(f"{label}: '{ITEMS[k][0]}' is required but not reported.")
        return float(g(k))

    def opt(k, attr=None, zero_ok=True):
        x = g(k)
        if isnum(x):
            return float(x)
        miss.append(attr or k)
        return 0.0 if zero_ok else NAN

    # ---------------- income statement
    y.revenue = need("revenue")
    y.cogs = opt("cogs")
    y.gross_profit = y.revenue - y.cogs
    y.sga, y.rd = opt("sga"), opt("rd")
    y.da = opt("da")
    y.ebit = need("ebit")
    y.other_opex = y.gross_profit - y.sga - y.rd - y.da - y.ebit
    y.ebitda = y.ebit + y.da
    y.interest_expense_term = g("interest_expense") if isnum(g("interest_expense")) else NAN
    y.interest_income = g("interest_income") if isnum(g("interest_income")) else NAN
    for k, attr in (("interest_expense", "interest_expense_term"), ("interest_income", "interest_income")):
        if not isnum(g(k)):
            miss.append(attr)
    y.interest_expense = y.interest_expense_term
    y.ebt = need("ebt")
    y.other_nonop = y.ebt - y.ebit + nz(y.interest_expense_term) - nz(y.interest_income)
    y.tax_expense = g("tax") if isnum(g("tax")) else NAN
    ni_c = g("ni_consolidated")
    y.ni_common = need("ni_common")
    if not isnum(y.tax_expense):
        miss.append("tax_expense")
        if isnum(ni_c):
            y.tax_expense = y.ebt - ni_c
            warn.append(f"{label}: income tax not reported; shown as pre-tax income - net income.")
    y.net_income = ni_c if isnum(ni_c) else y.ebt - nz(y.tax_expense)
    y.disc_ops = y.net_income - (y.ebt - nz(y.tax_expense))
    y.ni_nci = y.net_income - y.ni_common
    # ---------------- balance sheet
    y.cash = need("cash")
    y.st_investments = opt("st_investments")
    y.accounts_receivable = opt("ar", "accounts_receivable")
    y.inventory = opt("inventory")
    ta = need("total_assets")
    ca = g("current_assets")
    if not isnum(ca):
        miss.append("other_current_assets")
        ca = y.cash + y.st_investments + y.accounts_receivable + y.inventory
        warn.append(f"{label}: total current assets not reported; other current assets set to 0.")
    y.other_current_assets = ca - (y.cash + y.st_investments + y.accounts_receivable + y.inventory)
    y.net_ppe = opt("net_ppe")
    y.gross_ppe = g("gross_ppe") if isnum(g("gross_ppe")) else NAN
    y.accumulated_depreciation = abs(g("acc_dep")) if isnum(g("acc_dep")) else NAN
    if not isnum(y.gross_ppe) or not isnum(y.accumulated_depreciation):
        y.gross_ppe = y.accumulated_depreciation = NAN
        miss += ["gross_ppe", "accumulated_depreciation"]
    y.other_non_current_assets = ta - ca - y.net_ppe
    y.accounts_payable = opt("ap", "accounts_payable")
    cur_debt, lt_debt = nz(g("current_debt")), nz(g("lt_debt"))
    y.senior_debt = cur_debt + lt_debt
    cl = g("current_liabilities")
    if not isnum(cl):
        cl = y.accounts_payable + cur_debt
        miss.append("other_current_liabilities")
        warn.append(f"{label}: total current liabilities not reported; other current liabilities set to 0.")
    y.other_current_liabilities = cl - y.accounts_payable - cur_debt
    tl = need("total_liabilities")
    y.other_non_current_liabilities = tl - cl - lt_debt
    y.revolver_debt = 0.0
    se = need("shareholders_equity")
    y.common_stock = opt("common_stock")
    y.retained_earnings = opt("retained_earnings")
    y.treasury_stock = abs(nz(g("treasury_stock")))
    y.aoci_other = se - (y.common_stock + y.retained_earnings - y.treasury_stock)
    y.nci = nz(g("nci"))
    y.recompute_totals()                     # components reproduce the reported totals
    y.total_assets, y.total_liabilities = ta, tl
    y.total_shareholders_equity = se
    y.total_equity = se + y.nci
    y.total_liabilities_and_equity = tl + y.total_equity
    y.balance_check = ta - y.total_liabilities_and_equity
    if abs(y.balance_check) > 0.5:
        warn.append(f"{label}: the reported balance sheet does not balance: assets {ta:,.1f} vs liabilities + equity "
                    f"{y.total_liabilities_and_equity:,.1f} (difference {y.balance_check:,.1f}). Shown, not plugged; "
                    f"the forecast inherits this difference.")
    # ---------------- cash-flow statement (as reported)
    y.cfo_net_income = y.net_income
    y.cfo_da = y.da
    y.cfo = g("cfo") if isnum(g("cfo")) else NAN
    y.cfo_change_nwc = nz(g("change_wc"))
    y.cfi_capex = -abs(nz(g("capex")))
    y.cfi = g("cfi") if isnum(g("cfi")) else NAN
    y.cff_debt_issued = abs(nz(g("debt_issued")))
    y.cff_debt_repaid = -abs(nz(g("debt_repaid")))
    y.cff_dividends_paid = -abs(nz(g("dividends")))
    y.cff_share_buybacks = -abs(nz(g("buybacks")))
    y.cff = g("cff") if isnum(g("cff")) else NAN
    for k, attr in (("cfo", "cfo"), ("cfi", "cfi"), ("cff", "cff"), ("change_wc", "cfo_change_nwc"),
                    ("capex", "cfi_capex"), ("dividends", "cff_dividends_paid"), ("buybacks", "cff_share_buybacks")):
        if not isnum(g(k)):
            miss.append(attr)
    y.cfo_other = nz(y.cfo) - y.net_income - y.da - y.cfo_change_nwc if isnum(y.cfo) else NAN
    y.cfi_other = nz(y.cfi) - y.cfi_capex if isnum(y.cfi) else NAN
    y.cff_other = (nz(y.cff) - y.cff_debt_issued - y.cff_debt_repaid - y.cff_dividends_paid - y.cff_share_buybacks
                   if isnum(y.cff) else NAN)
    y.fcf = nz(y.cfo) + y.cfi_capex if isnum(y.cfo) else NAN
    bc, ec = g("beginning_cash"), g("ending_cash")
    y.beginning_cash = bc if isnum(bc) else NAN
    y.ending_cash = ec if isnum(ec) else NAN
    y.net_change_cash = ec - bc if isnum(bc) and isnum(ec) else NAN
    if isnum(y.net_change_cash) and isnum(y.cfo) and isnum(y.cfi) and isnum(y.cff):
        y.fx_other = y.net_change_cash - y.cfo - y.cfi - y.cff
    else:
        y.fx_other = NAN
    if isnum(ec) and abs(ec - y.cash) > 0.5:
        warn.append(f"{label}: cash-flow statement ending cash {ec:,.1f} differs from balance-sheet cash {y.cash:,.1f} "
                    f"by {ec - y.cash:,.1f} (usually restricted cash or cash held for sale). The forecast starts from "
                    f"balance-sheet cash.")
    if abs(y.disc_ops) > 0.5:
        warn.append(f"{label}: net income differs from pre-tax income - tax by {y.disc_ops:,.1f} "
                    f"(discontinued operations / other); shown on its own line.")
    return y


# ------------------------------------------------------------------ Yahoo Finance

def _pick(df: pd.DataFrame, col, names: List[str]) -> Tuple[float, str]:
    if df is None or df.empty or col not in df.columns:
        return NAN, ""
    for n in names:
        if n in df.index:
            x = df.loc[n, col]
            if isinstance(x, pd.Series):
                x = x.iloc[0]
            if pd.notna(x):
                return float(x), n
    return NAN, ""


def _match_col(df: pd.DataFrame, col) -> Optional[pd.Timestamp]:
    """Same fiscal year-end (within 20 days) in another statement."""
    if df is None or df.empty:
        return None
    for c in df.columns:
        if abs((pd.Timestamp(c) - pd.Timestamp(col)).days) <= 20:
            return c
    return None


def from_yahoo_frames(fin: pd.DataFrame, bs: pd.DataFrame, cf: pd.DataFrame, ticker: str, company: str,
                      currency: str, source: str, as_of: str = "", scale: float = 1e6) -> HistoricalData:
    warn: List[str] = []
    fin, bs, cf = [d.copy() if d is not None else pd.DataFrame() for d in (fin, bs, cf)]
    for d in (fin, bs, cf):
        if not d.empty:
            d.columns = pd.to_datetime(d.columns)
    if fin.empty or bs.empty:
        raise ValueError(f"Yahoo Finance returned no income statement or balance sheet for '{ticker}'.")
    usable = []
    for c in sorted(fin.columns):
        bcol = _match_col(bs, c)
        if bcol is None:
            continue
        rev, _ = _pick(fin, c, YAHOO_LINES["revenue"][1])
        ta, _ = _pick(bs, bcol, YAHOO_LINES["total_assets"][1])
        if isnum(rev) and isnum(ta):
            usable.append((c, bcol, _match_col(cf, c)))
    if len(usable) < 3:
        raise ValueError(f"'{ticker}': only {len(usable)} fiscal year(s) with both an income statement and a balance "
                         f"sheet on Yahoo Finance; the model needs 3.")
    usable = usable[-3:]
    frames = {"IS": fin, "BS": bs, "CF": cf}
    years, map_rows = [], {}
    for c, bcol, ccol in usable:
        cols = {"IS": c, "BS": bcol, "CF": ccol}
        label = f"FY{pd.Timestamp(c).year}"
        v, used = {}, {}
        for key, (st, names) in YAHOO_LINES.items():
            x, n = _pick(frames[st], cols[st], names) if cols[st] is not None else (NAN, "")
            v[key] = x / scale if isnum(x) else NAN
            used[key] = n
        if not isnum(v["da"]) and isnum(v["da_cf"]):
            v["da"], used["da"] = v["da_cf"], "CF: " + used["da_cf"]
        # cash & short-term investments: never count the same money twice
        if isnum(v["cash"]) and isnum(v["cash_and_sti"]):
            v["st_investments"] = v["cash_and_sti"] - v["cash"]
            used["st_investments"] = "Cash Cash Equivalents And Short Term Investments - Cash And Cash Equivalents"
        elif isnum(v["cash"]):
            v["st_investments"] = v["sti_line"] if isnum(v["sti_line"]) else 0.0
            used["st_investments"] = used["sti_line"] or "(none reported)"
        elif isnum(v["cash_and_sti"]):
            v["cash"], v["st_investments"] = v["cash_and_sti"], 0.0
            used["cash"] = used["cash_and_sti"]
            warn.append(f"{label}: only 'cash and short-term investments' reported; all treated as cash.")
        v["common_stock"] = nz(v["common_stock_par"]) + nz(v["apic"]) if isnum(v["common_stock_par"]) or isnum(v["apic"]) else NAN
        used["common_stock"] = " + ".join(x for x in (used["common_stock_par"], used["apic"]) if x)
        if isnum(v["total_equity_gross"]) and isnum(v["shareholders_equity"]):
            v["nci"] = v["total_equity_gross"] - v["shareholders_equity"]
            used["nci"] = "Total Equity Gross Minority Interest - Stockholders Equity"
        else:
            v["nci"] = v["nci_line"] if isnum(v["nci_line"]) else 0.0
            used["nci"] = used["nci_line"]
        if isnum(v["gross_profit_reported"]) and isnum(v["cogs"]) and abs(v["revenue"] - v["cogs"] - v["gross_profit_reported"]) > 0.5:
            warn.append(f"{label}: Yahoo gross profit differs from revenue - cost of revenue; the model uses revenue - cost of revenue.")
        if not isnum(v["cogs"]) and isnum(v["gross_profit_reported"]):
            v["cogs"] = v["revenue"] - v["gross_profit_reported"]
            used["cogs"] = "Total Revenue - Gross Profit"
        y = build_year(label, str(pd.Timestamp(c).date()), v, warn)
        years.append(y)
        map_rows[label] = used
    m = pd.DataFrame(map_rows)
    m.index.name = "model item"
    missing = sorted({k for y in years for k in y.missing})
    if missing:
        warn.append("Not reported by Yahoo (shown as n/a or 0): " + ", ".join(missing) + ".")
    return HistoricalData(years, company or ticker, ticker.upper(), currency or "USD", source, as_of, warn, m)


def snapshot_tickers() -> List[str]:
    meta = json.loads((SNAPSHOT_DIR / "meta.json").read_text())
    return list(meta["tickers"])


def load_snapshot(ticker: str) -> HistoricalData:
    meta = json.loads((SNAPSHOT_DIR / "meta.json").read_text())
    t = ticker.upper()
    if t not in meta["tickers"]:
        raise ValueError(f"'{t}' is not in the offline snapshot ({', '.join(meta['tickers'])}).")
    rd = lambda n: pd.read_csv(SNAPSHOT_DIR / f"{t}_{n}.csv", index_col=0)
    info = meta["tickers"][t]
    return from_yahoo_frames(rd("income"), rd("balance"), rd("cashflow"), t, info["name"], info["currency"],
                             f"Yahoo Finance snapshot downloaded {meta['downloaded']}", meta["downloaded"])


def fetch_yahoo(ticker: str) -> HistoricalData:
    import yfinance as yf
    t = ticker.strip().upper()
    if not t:
        raise ValueError("Enter a ticker.")
    try:
        tk = yf.Ticker(t)
        fin, bs, cf = tk.financials, tk.balance_sheet, tk.cashflow
        try:
            info = tk.info or {}
        except Exception:
            info = {}
    except Exception as exc:
        raise RuntimeError(f"Could not download '{t}' from Yahoo Finance: {exc}") from exc
    return from_yahoo_frames(fin, bs, cf, t, info.get("longName") or info.get("shortName") or t,
                             info.get("financialCurrency") or "USD", "Yahoo Finance (live)",
                             pd.Timestamp.today().strftime("%Y-%m-%d"))


# ------------------------------------------------------------------ templates

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9&]+", " ", str(s).lower()).strip()


LABEL_TO_KEY = {_norm(lbl): k for k, (lbl, _, _) in ITEMS.items()}


def template_frame(sample: bool = False) -> pd.DataFrame:
    """The template layout (rows = canonical labels, columns = 3 fiscal years)."""
    rows = [lbl for lbl, _, _ in ITEMS.values()]
    df = pd.DataFrame(index=rows, columns=["FY2023", "FY2024", "FY2025"], dtype=float)
    if sample:
        df[:] = np.array(SAMPLE_TEMPLATE_VALUES, dtype=float)
    df.index.name = "Line item"
    return df


def load_template(content: bytes, filename: str) -> HistoricalData:
    name = filename.lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), index_col=0)
        elif name.endswith((".xlsx", ".xlsm")):
            df = pd.read_excel(io.BytesIO(content), sheet_name=0, index_col=0)
        else:
            raise ValueError("Upload a .csv or .xlsx file in the template layout.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Could not read '{filename}': {exc}") from exc
    note_cols = {"statement", "required note", "sign convention", "note", "notes", "comment", "comments"}
    cols = [c for c in df.columns if str(c).strip() and not str(c).startswith("Unnamed")
            and _norm(c) not in note_cols]
    if len(cols) < 3:
        raise ValueError(f"The template needs 3 year columns; found {len(cols)}.")
    cols = cols[-3:]
    warn: List[str] = []
    keyed, unknown = {}, []
    for lbl in df.index:
        k = LABEL_TO_KEY.get(_norm(lbl))
        if k is None:
            if str(lbl).strip() and not str(lbl).startswith("---") and str(lbl) != "nan":
                unknown.append(str(lbl))
            continue
        keyed[k] = lbl
    if unknown:
        warn.append("Rows not recognised and ignored: " + "; ".join(unknown) + ".")
    years = []
    for c in cols:
        v = {}
        for k in ITEMS:
            x = df.loc[keyed[k], c] if k in keyed else NAN
            if isinstance(x, pd.Series):
                x = x.iloc[0]
            if isinstance(x, str):
                x = x.replace(",", "").replace("$", "").strip()
                x = float(x) if x not in ("", "n/a", "na", "-") else NAN
            v[k] = float(x) if x is not None and pd.notna(x) else NAN
        years.append(build_year(str(c).strip(), "", v, warn))
    miss = sorted({k for y in years for k in y.missing})
    if miss:
        warn.append("Not provided in the template (shown as n/a or 0): " + ", ".join(miss) + ".")
    return HistoricalData(years, Path(filename).stem, "CUSTOM", "units as entered", f"Uploaded file {filename}", "", warn)


# A small fictional company used as the template example (it balances: assets = liabilities + equity).
SAMPLE_TEMPLATE_VALUES = [
    [1000, 1120, 1250], [550, 610, 675], [120, 130, 145], [50, 55, 60], [40, 45, 50], [240, 280, 320],
    [15, 14, 12], [5, 6, 8], [230, 272, 316], [48.3, 57.1, 66.4], [181.7, 214.9, 249.6], [181.7, 214.9, 249.6],
    [120, 155, 190], [0, 0, 0], [110, 122, 135], [60, 68, 75], [310, 367, 425], [450, 510, 580], [150, 195, 245],
    [300, 315, 335], [700, 777, 860], [80, 88, 96], [140, 152, 164], [20, 20, 20], [180, 160, 140], [380, 377, 374],
    [120, 125, 130], [200, 275, 356], [0, 0, 0], [320, 400, 486], [0, 0, 0],
    [210, 245, 280], [-20, -10, -12], [-50, -60, -70], [-50, -60, -70], [0, 0, 0], [-20, -20, -20],
    [-30, -35, -40], [-40, -95, -115], [-90, -150, -175], [50, 120, 155], [120, 155, 190],
]
