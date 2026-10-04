"""
dcf.py - Core Discounted Cash Flow (DCF) valuation engine.

What this module does
---------------------
1. Downloads and cleans historical financials from Yahoo Finance (yfinance),
   with an offline snapshot for a few benchmark tickers.
2. Calculates the discount rate (WACC) using CAPM for the cost of equity.
3. Projects 5 years of Free Cash Flow to the Firm (FCFF, "unlevered FCF").
4. Calculates the terminal value two ways (Gordon Growth and Exit Multiple).
5. Bridges Enterprise Value -> Equity Value -> implied value per share.
6. Builds 2-D sensitivity tables (WACC vs. g, WACC vs. exit multiple).

Units: every monetary amount inside this module is in the company's reporting
currency, in full units (not millions). The Excel export converts to millions.

Sign conventions (important!)
-----------------------------
* Capex is stored as a POSITIVE number (cash spent). yfinance reports it as a
  negative cash-flow line, so we take the absolute value.
* Change in NWC (delta NWC) is stored as "increase in NWC = positive number".
  yfinance's cash-flow line "Change In Working Capital" uses the opposite sign
  (a negative value means cash was USED because working capital went up), so
  we flip its sign:  delta_NWC = -(cash-flow statement value).
* FCFF = EBIT x (1 - tax) + D&A - Capex - delta NWC

Discounting
-----------
* Mid-year convention (default): cash flow of year t is discounted t - 0.5 years.
* End-of-year convention: cash flow of year t is discounted t years.
* The terminal value (both methods) is a value AS OF THE END OF YEAR N (N = 5),
  so it is always discounted N full years: PV(TV) = TV / (1 + WACC)^N.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "offline_snapshots.json"
DEFAULT_TAX_RATE = 0.21
DEFAULT_BETA = 1.0


class DataUnavailableError(Exception):
    """Raised when we cannot get trustworthy data for a ticker."""


# ==============================================================================
# Data structures
# ==============================================================================

@dataclass
class HistoricalFinancials:
    """Historical financial metrics (oldest year first)."""
    ticker: str
    company_name: str
    currency: str
    years: List[str]
    revenue: List[float]
    ebit: List[float]
    da: List[float]                  # Depreciation & Amortization (positive)
    capex: List[float]               # Capital expenditure (positive = cash spent)
    nwc_change: List[float]          # Increase in NWC (positive = cash used)
    effective_tax_rate: List[float]
    historical_fcff: List[float]
    current_price: float
    shares_outstanding: float
    total_cash: float
    total_debt: float
    beta: float
    market_cap: float
    sector: str = "N/A"
    industry: str = "N/A"
    description: str = ""
    financial_currency: str = ""     # currency of the financial statements
    as_of: str = ""                  # date of data snapshot (offline data only)


@dataclass
class WACCInputs:
    """Inputs for WACC. All rates are decimals (0.042 = 4.2%)."""
    risk_free_rate: float
    beta: float
    equity_risk_premium: float
    cost_of_debt: float              # pre-tax
    tax_rate: float
    market_cap: float                # market value of equity (E)
    total_debt: float                # debt (D), book value used as a proxy for market value
    weight_equity_override: Optional[float] = None
    weight_debt_override: Optional[float] = None


@dataclass
class WACCResult:
    cost_of_equity: float            # Ke = Rf + beta x ERP
    pre_tax_cost_of_debt: float      # Kd
    after_tax_cost_of_debt: float    # Kd x (1 - t)
    weight_equity: float             # E / (E + D)
    weight_debt: float               # D / (E + D)
    wacc: float                      # We x Ke + Wd x Kd x (1 - t)


def _five(value: float) -> List[float]:
    return [value] * 5


@dataclass
class DCFAssumptions:
    """Projection assumptions (one value per forecast year) and terminal settings."""
    projection_years: int = 5
    revenue_growth_rates: List[float] = field(default_factory=lambda: [0.08, 0.07, 0.06, 0.05, 0.04])
    ebit_margins: List[float] = field(default_factory=lambda: _five(0.25))
    tax_rates: List[float] = field(default_factory=lambda: _five(0.21))
    capex_pcts: List[float] = field(default_factory=lambda: _five(0.05))
    da_pcts: List[float] = field(default_factory=lambda: _five(0.04))
    nwc_pcts: List[float] = field(default_factory=lambda: _five(0.08))
    perpetual_growth_rate: float = 0.025
    exit_multiple: float = 12.0
    mid_year_convention: bool = True

    def validate(self) -> None:
        n = self.projection_years
        if n < 1:
            raise ValueError("projection_years must be at least 1")
        for name in ("revenue_growth_rates", "ebit_margins", "tax_rates",
                     "capex_pcts", "da_pcts", "nwc_pcts"):
            values = getattr(self, name)
            if len(values) < n:
                raise ValueError(f"{name} needs {n} values, got {len(values)}")
            if any(not math.isfinite(v) for v in values[:n]):
                raise ValueError(f"{name} contains a non-numeric value")


@dataclass
class CashFlowProjection:
    """Index 0 = base year (actuals), indices 1..N = forecast years."""
    years: List[str]
    revenue: List[float]
    revenue_growth: List[float]
    ebit: List[float]
    ebit_margin: List[float]
    tax_rate: List[float]
    nopat: List[float]
    da: List[float]
    capex: List[float]
    nwc: List[float]
    nwc_change: List[float]
    fcff: List[float]
    discount_period: List[float]
    discount_factor: List[float]
    pv_fcff: List[float]
    cumulative_pv_fcff: float


@dataclass
class ValuationSummary:
    method: str
    pv_fcf_sum: float
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float
    total_debt: float
    total_cash: float
    net_debt: float
    equity_value: float
    shares_outstanding: float
    implied_share_price: float
    current_share_price: float
    upside_downside_pct: float            # in percent, e.g. 12.5 = +12.5%
    terminal_value_pct_of_ev: float       # in percent
    implied_exit_multiple: float = float("nan")      # TV / EBITDA_N (cross-check)
    implied_perpetual_growth: float = float("nan")   # g implied by TV (cross-check)


@dataclass
class SensitivityMatrix:
    method: str
    wacc_values: List[float]
    param_values: List[float]
    param_label: str
    table: List[List[float]]              # implied share prices (NaN if undefined)
    upside_table: List[List[float]]
    base_wacc: float
    base_param: float
    current_price: float


@dataclass
class DCFResult:
    company: HistoricalFinancials
    assumptions: DCFAssumptions
    wacc_inputs: WACCInputs
    wacc_result: WACCResult
    projections: CashFlowProjection
    ggm_valuation: ValuationSummary
    exit_valuation: ValuationSummary
    ggm_sensitivity: SensitivityMatrix
    exit_sensitivity: SensitivityMatrix
    warnings: List[str] = field(default_factory=list)


# ==============================================================================
# Data loading: yfinance parsing
# ==============================================================================

def _find_row(df: Optional[pd.DataFrame], candidates: List[str]) -> Optional[str]:
    """Return the first row label that exactly matches a candidate (case-insensitive)."""
    if df is None or df.empty:
        return None
    lookup = {str(idx).strip().lower(): idx for idx in df.index}
    for c in candidates:
        if c.lower() in lookup:
            return lookup[c.lower()]
    return None


def _cell(df: Optional[pd.DataFrame], key: Optional[str], col: Any) -> float:
    """Return a float from df[key, col] or NaN if missing."""
    if df is None or key is None or col not in df.columns:
        return float("nan")
    try:
        val = df.loc[key, col]
        if isinstance(val, pd.Series):
            val = val.iloc[0]
        val = float(val)
    except (TypeError, ValueError, KeyError):
        return float("nan")
    return val if math.isfinite(val) else float("nan")


def _info_float(info: Dict[str, Any], *keys: str) -> float:
    for k in keys:
        v = info.get(k)
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            return v
    return float("nan")


def compute_historical_fcff(ebit: List[float], tax: List[float], da: List[float],
                            capex: List[float], nwc_change: List[float]) -> List[float]:
    """FCFF = EBIT(1 - t) + D&A - Capex - increase in NWC."""
    return [e * (1.0 - t) + d - c - n for e, t, d, c, n in zip(ebit, tax, da, capex, nwc_change)]


def parse_yfinance_data(
    symbol: str,
    info: Dict[str, Any],
    fin: Optional[pd.DataFrame],
    cf: Optional[pd.DataFrame],
    bs: Optional[pd.DataFrame],
    last_close: float = float("nan"),
) -> Tuple[HistoricalFinancials, List[str]]:
    """
    Turn raw yfinance tables into clean HistoricalFinancials.

    Pure function (no network) so it can be unit tested with fake data.
    Raises DataUnavailableError when critical data (revenue, EBIT, price,
    shares) is missing, instead of silently inventing numbers.
    """
    warnings: List[str] = []
    info = info or {}
    if fin is None or fin.empty:
        raise DataUnavailableError(f"No income statement data for {symbol}.")

    rev_key = _find_row(fin, ["Total Revenue", "Operating Revenue", "Revenue"])
    # Prefer Operating Income: yfinance's "EBIT" row often includes non-operating items.
    ebit_key = _find_row(fin, ["Operating Income", "EBIT", "Total Operating Income As Reported"])
    if rev_key is None or ebit_key is None:
        raise DataUnavailableError(f"Revenue or operating income not reported for {symbol}.")

    # Keep annual periods where revenue is actually reported, oldest first.
    cols = sorted(c for c in fin.columns
                  if math.isfinite(_cell(fin, rev_key, c)) and _cell(fin, rev_key, c) > 0)
    if cf is not None and not cf.empty:
        with_cf = [c for c in cols if c in cf.columns]
        if with_cf:
            cols = with_cf
    cols = cols[-4:]
    if not cols:
        raise DataUnavailableError(f"No annual periods with revenue for {symbol}.")

    da_key = _find_row(cf, ["Depreciation And Amortization", "Depreciation Amortization Depletion",
                            "Reconciled Depreciation"])
    da_key_fin = _find_row(fin, ["Reconciled Depreciation"])
    capex_key = _find_row(cf, ["Capital Expenditure", "Purchase Of PPE"])
    nwc_key = _find_row(cf, ["Change In Working Capital"])
    tax_key = _find_row(fin, ["Tax Provision", "Income Tax Expense"])
    pretax_key = _find_row(fin, ["Pretax Income"])

    years, rev, ebit, da, capex, dnwc, tax = [], [], [], [], [], [], []
    for col in cols:
        year = pd.to_datetime(col).strftime("%Y")
        years.append(year)
        r = _cell(fin, rev_key, col)
        e = _cell(fin, ebit_key, col)
        if not math.isfinite(e):
            raise DataUnavailableError(f"Operating income missing for {symbol} FY{year}.")
        rev.append(r)
        ebit.append(e)

        d = _cell(cf, da_key, col)
        if not math.isfinite(d):
            d = _cell(fin, da_key_fin, col)
        if not math.isfinite(d):
            d = 0.035 * r
            warnings.append(f"FY{year}: D&A not reported, estimated at 3.5% of revenue.")
        da.append(abs(d))

        c = _cell(cf, capex_key, col)
        if not math.isfinite(c):
            c = 0.04 * r
            warnings.append(f"FY{year}: Capex not reported, estimated at 4% of revenue.")
        capex.append(abs(c))  # yfinance reports capex as a negative cash flow

        w = _cell(cf, nwc_key, col)
        if not math.isfinite(w):
            w = 0.0
            warnings.append(f"FY{year}: change in working capital not reported, assumed 0.")
        dnwc.append(-w)       # cash-flow sign -> "increase in NWC" sign

        t_prov, p_tax = _cell(fin, tax_key, col), _cell(fin, pretax_key, col)
        rate = t_prov / p_tax if (math.isfinite(t_prov) and math.isfinite(p_tax) and p_tax > 0) else float("nan")
        if not (math.isfinite(rate) and 0.0 <= rate <= 0.50):
            rate = DEFAULT_TAX_RATE
            warnings.append(f"FY{year}: effective tax rate unavailable/unusual, using {DEFAULT_TAX_RATE:.0%}.")
        tax.append(rate)

    # ---- Market data -------------------------------------------------------
    price = _info_float(info, "currentPrice", "regularMarketPrice", "previousClose")
    if not math.isfinite(price):
        price = last_close if (math.isfinite(last_close) and last_close > 0) else float("nan")
    if not math.isfinite(price):
        raise DataUnavailableError(f"No current share price for {symbol}.")

    latest = cols[-1]
    shares = _info_float(info, "sharesOutstanding", "impliedSharesOutstanding")
    if not math.isfinite(shares):
        shares = abs(_cell(bs, _find_row(bs, ["Ordinary Shares Number", "Share Issued"]), latest))
    mcap = _info_float(info, "marketCap")
    if not (math.isfinite(shares) and shares > 0) and math.isfinite(mcap):
        shares = mcap / price
    if not (math.isfinite(shares) and shares > 0):
        raise DataUnavailableError(f"No shares outstanding for {symbol}.")
    if not math.isfinite(mcap):
        mcap = shares * price

    cash = _info_float(info, "totalCash")
    if not math.isfinite(cash):
        cash = _cell(bs, _find_row(bs, ["Cash Cash Equivalents And Short Term Investments",
                                        "Cash And Cash Equivalents"]), latest)
    if not math.isfinite(cash):
        cash = 0.0
        warnings.append("Cash balance not reported, assumed 0.")

    debt = _info_float(info, "totalDebt")
    if not math.isfinite(debt):
        debt = _cell(bs, _find_row(bs, ["Total Debt"]), latest)
    if not math.isfinite(debt):
        debt = 0.0
        warnings.append("Total debt not reported, assumed 0.")

    beta = info.get("beta")
    try:
        beta = float(beta)
    except (TypeError, ValueError):
        beta = float("nan")
    if not (math.isfinite(beta) and 0.0 < beta <= 5.0):
        beta = DEFAULT_BETA
        warnings.append(f"Beta unavailable, using {DEFAULT_BETA:.2f}.")

    currency = str(info.get("currency") or "USD")
    fin_currency = str(info.get("financialCurrency") or currency)
    if fin_currency != currency:
        warnings.append(
            f"Financial statements are in {fin_currency} but the share price is in {currency}. "
            "This model does not convert currencies, so the per-share value is NOT reliable."
        )

    company = HistoricalFinancials(
        ticker=symbol,
        company_name=str(info.get("longName") or info.get("shortName") or symbol),
        currency=currency,
        years=years,
        revenue=rev,
        ebit=ebit,
        da=da,
        capex=capex,
        nwc_change=dnwc,
        effective_tax_rate=tax,
        historical_fcff=compute_historical_fcff(ebit, tax, da, capex, dnwc),
        current_price=price,
        shares_outstanding=shares,
        total_cash=cash,
        total_debt=debt,
        beta=beta,
        market_cap=mcap,
        sector=str(info.get("sector") or "N/A"),
        industry=str(info.get("industry") or "N/A"),
        description=str(info.get("longBusinessSummary") or ""),
        financial_currency=fin_currency,
    )
    return company, warnings


def load_offline_snapshots(path: Path = SNAPSHOT_PATH) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_fallback_company_data(ticker_symbol: str) -> HistoricalFinancials:
    """
    Load a company from the offline snapshot (data/offline_snapshots.json).
    Raises DataUnavailableError for tickers that are not in the snapshot,
    so the app never values a company on made-up numbers.
    """
    sym = ticker_symbol.upper().strip()
    snaps = load_offline_snapshots()
    if sym not in snaps:
        available = ", ".join(sorted(snaps)) or "none"
        raise DataUnavailableError(f"No offline data for {sym}. Offline tickers: {available}.")
    return HistoricalFinancials(**snaps[sym])


def fetch_company_data(ticker_symbol: str) -> Tuple[HistoricalFinancials, Dict[str, Any]]:
    """
    Fetch live data from Yahoo Finance. If that fails, fall back to the offline
    snapshot (with a visible warning). If neither works, raise DataUnavailableError.
    """
    sym = ticker_symbol.upper().strip()
    if not sym:
        raise DataUnavailableError("Please enter a ticker symbol.")
    meta: Dict[str, Any] = {"source": "yfinance", "warnings": []}
    try:
        import yfinance as yf  # imported lazily so tests don't need the network

        t = yf.Ticker(sym)
        info = t.info or {}
        last_close = float("nan")
        if not (info.get("currentPrice") or info.get("regularMarketPrice")):
            hist = t.history(period="5d")
            if hist is not None and not hist.empty:
                last_close = float(hist["Close"].iloc[-1])
        company, warns = parse_yfinance_data(sym, info, t.financials, t.cashflow, t.balance_sheet, last_close)
        meta["warnings"].extend(warns)
        return company, meta
    except Exception as exc:  # network error, rate limit, bad ticker, missing data...
        try:
            company = get_fallback_company_data(sym)
        except DataUnavailableError:
            raise DataUnavailableError(
                f"Could not load data for '{sym}' from Yahoo Finance ({exc}). "
                "Check the ticker symbol or try again later."
            ) from exc
        meta["source"] = "offline_snapshot"
        meta["warnings"].append(
            f"Live data unavailable ({exc}). Using the offline snapshot from {company.as_of}."
        )
        return company, meta


def fetch_risk_free_rate(default_rate: float = 0.0425) -> float:
    """Latest 10-year US Treasury yield (^TNX, quoted in percent). Falls back to default."""
    try:
        import yfinance as yf

        hist = yf.Ticker("^TNX").history(period="5d")
        if hist is not None and not hist.empty:
            rate = float(hist["Close"].iloc[-1]) / 100.0
            if 0.005 <= rate <= 0.15:
                return rate
    except Exception:
        pass
    return default_rate


# ==============================================================================
# WACC
# ==============================================================================

def calculate_wacc(inputs: WACCInputs) -> WACCResult:
    """
    Ke   = Rf + beta x ERP                     (CAPM)
    Kd'  = Kd x (1 - t)                        (after-tax cost of debt)
    WACC = E/(E+D) x Ke + D/(E+D) x Kd'        (market-value weights)
    Optional target weights override the market-value weights.
    """
    ke = inputs.risk_free_rate + inputs.beta * inputs.equity_risk_premium
    kd_after_tax = inputs.cost_of_debt * (1.0 - inputs.tax_rate)

    we_o, wd_o = inputs.weight_equity_override, inputs.weight_debt_override
    if we_o is not None or wd_o is not None:
        if we_o is None:
            we_o = 1.0 - wd_o
        if wd_o is None:
            wd_o = 1.0 - we_o
        total = we_o + wd_o
        we, wd = (we_o / total, wd_o / total) if total > 0 else (1.0, 0.0)
    else:
        e, d = max(inputs.market_cap, 0.0), max(inputs.total_debt, 0.0)
        we, wd = (e / (e + d), d / (e + d)) if (e + d) > 0 else (1.0, 0.0)

    return WACCResult(
        cost_of_equity=ke,
        pre_tax_cost_of_debt=inputs.cost_of_debt,
        after_tax_cost_of_debt=kd_after_tax,
        weight_equity=we,
        weight_debt=wd,
        wacc=we * ke + wd * kd_after_tax,
    )


# ==============================================================================
# Projections
# ==============================================================================

def discount_period(year: int, mid_year: bool) -> float:
    return year - 0.5 if mid_year else float(year)


def project_cash_flows(base_revenue: float, base_nwc: float,
                       assumptions: DCFAssumptions, wacc: float) -> CashFlowProjection:
    """
    Revenue_t = Revenue_{t-1} x (1 + g_t)
    EBIT_t    = Revenue_t x margin_t
    NOPAT_t   = EBIT_t x (1 - tax_t)
    D&A_t     = Revenue_t x da%_t ;  Capex_t = Revenue_t x capex%_t
    NWC_t     = Revenue_t x nwc%_t ;  delta NWC_t = NWC_t - NWC_{t-1}
    FCFF_t    = NOPAT_t + D&A_t - Capex_t - delta NWC_t
    PV_t      = FCFF_t / (1 + WACC)^period_t
    """
    assumptions.validate()
    n = assumptions.projection_years
    out: Dict[str, List[float]] = {k: [0.0] for k in (
        "growth", "ebit", "margin", "tax", "nopat", "da", "capex", "dnwc", "fcff", "pv")}
    rev, nwc, periods, dfs = [base_revenue], [base_nwc], [0.0], [1.0]

    for i in range(n):
        t = i + 1
        r = rev[-1] * (1.0 + assumptions.revenue_growth_rates[i])
        ebit = r * assumptions.ebit_margins[i]
        nopat = ebit * (1.0 - assumptions.tax_rates[i])
        da = r * assumptions.da_pcts[i]
        capex = r * assumptions.capex_pcts[i]
        nwc_t = r * assumptions.nwc_pcts[i]
        dnwc = nwc_t - nwc[-1]
        fcff = nopat + da - capex - dnwc
        p = discount_period(t, assumptions.mid_year_convention)
        df = 1.0 / (1.0 + wacc) ** p

        rev.append(r); nwc.append(nwc_t); periods.append(p); dfs.append(df)
        for k, v in (("growth", assumptions.revenue_growth_rates[i]), ("ebit", ebit),
                     ("margin", assumptions.ebit_margins[i]), ("tax", assumptions.tax_rates[i]),
                     ("nopat", nopat), ("da", da), ("capex", capex), ("dnwc", dnwc),
                     ("fcff", fcff), ("pv", fcff * df)):
            out[k].append(v)

    return CashFlowProjection(
        years=["Base (Y0)"] + [f"Year {i}" for i in range(1, n + 1)],
        revenue=rev, revenue_growth=out["growth"], ebit=out["ebit"], ebit_margin=out["margin"],
        tax_rate=out["tax"], nopat=out["nopat"], da=out["da"], capex=out["capex"], nwc=nwc,
        nwc_change=out["dnwc"], fcff=out["fcff"], discount_period=periods, discount_factor=dfs,
        pv_fcff=out["pv"], cumulative_pv_fcff=sum(out["pv"][1:]),
    )


# ==============================================================================
# Terminal value and valuation bridge
# ==============================================================================

def calculate_terminal_value_ggm(final_fcf: float, wacc: float, perpetual_growth: float,
                                 projection_years: int = 5, mid_year: bool = True) -> Tuple[float, float]:
    """
    Gordon Growth:  TV_N = FCFF_N x (1 + g) / (WACC - g);  PV = TV_N / (1 + WACC)^N
    The formula only makes sense when WACC > g; otherwise (NaN, NaN) is returned.
    `mid_year` is accepted for API compatibility: TV is a value at the END of
    year N, so it is discounted N full years under both conventions.
    """
    if wacc <= perpetual_growth:
        return float("nan"), float("nan")
    tv = final_fcf * (1.0 + perpetual_growth) / (wacc - perpetual_growth)
    return tv, tv / (1.0 + wacc) ** projection_years


def calculate_terminal_value_exit_multiple(final_ebitda: float, exit_multiple: float, wacc: float,
                                           projection_years: int = 5) -> Tuple[float, float]:
    """Exit multiple:  TV_N = EBITDA_N x multiple;  PV = TV_N / (1 + WACC)^N"""
    tv = final_ebitda * exit_multiple
    return tv, tv / (1.0 + wacc) ** projection_years


def build_valuation_bridge(method_name: str, pv_fcf_sum: float, terminal_val: float,
                           pv_terminal_val: float, total_cash: float, total_debt: float,
                           shares_outstanding: float, current_price: float) -> ValuationSummary:
    """
    EV            = sum PV(FCFF) + PV(TV)
    Net debt      = Debt - Cash
    Equity value  = EV - Net debt
    Value / share = Equity value / Shares outstanding  (can be negative if debt > EV)
    Upside        = Value per share / Current price - 1
    """
    ev = pv_fcf_sum + pv_terminal_val
    net_debt = total_debt - total_cash
    equity = ev - net_debt
    price = equity / shares_outstanding if shares_outstanding > 0 else float("nan")
    upside = (price / current_price - 1.0) * 100.0 if current_price > 0 else float("nan")
    tv_pct = pv_terminal_val / ev * 100.0 if (math.isfinite(ev) and ev > 0) else float("nan")
    return ValuationSummary(
        method=method_name, pv_fcf_sum=pv_fcf_sum, terminal_value=terminal_val,
        pv_terminal_value=pv_terminal_val, enterprise_value=ev, total_debt=total_debt,
        total_cash=total_cash, net_debt=net_debt, equity_value=equity,
        shares_outstanding=shares_outstanding, implied_share_price=price,
        current_share_price=current_price, upside_downside_pct=upside,
        terminal_value_pct_of_ev=tv_pct,
    )


def implied_perpetual_growth(tv: float, final_fcf: float, wacc: float) -> float:
    """Growth rate g that makes the Gordon formula give this TV:  g = (TV x WACC - FCF) / (TV + FCF)."""
    denom = tv + final_fcf
    return (tv * wacc - final_fcf) / denom if denom != 0 else float("nan")


# ==============================================================================
# Sensitivity tables
# ==============================================================================

def _price_for(proj: CashFlowProjection, assumptions: DCFAssumptions, company: HistoricalFinancials,
               wacc: float, param: float, method: str) -> float:
    n = assumptions.projection_years
    if method == "ggm":
        _, pv_tv = calculate_terminal_value_ggm(proj.fcff[-1], wacc, param, n)
    else:
        _, pv_tv = calculate_terminal_value_exit_multiple(proj.ebit[-1] + proj.da[-1], param, wacc, n)
    bridge = build_valuation_bridge(method, proj.cumulative_pv_fcff, float("nan"), pv_tv,
                                    company.total_cash, company.total_debt,
                                    company.shares_outstanding, company.current_price)
    return bridge.implied_share_price


def generate_sensitivity_table(base_revenue: float, base_nwc: float, assumptions: DCFAssumptions,
                               company: HistoricalFinancials, wacc_inputs: WACCInputs,
                               method: str = "ggm", wacc_steps: Optional[List[float]] = None,
                               param_steps: Optional[List[float]] = None,
                               wacc_step: float = 0.01, growth_step: float = 0.005,
                               multiple_step: float = 2.0) -> SensitivityMatrix:
    """Implied share price for a grid of WACC (rows) x g or exit multiple (columns)."""
    base_wacc = calculate_wacc(wacc_inputs).wacc
    if wacc_steps is None:
        wacc_steps = [base_wacc + k * wacc_step for k in (-2, -1, 0, 1, 2)]
    if method == "ggm":
        base_param = assumptions.perpetual_growth_rate
        label = "Perpetual Growth Rate (g)"
        if param_steps is None:
            param_steps = [base_param + k * growth_step for k in (-2, -1, 0, 1, 2)]
    else:
        base_param = assumptions.exit_multiple
        label = "Exit EV/EBITDA Multiple"
        if param_steps is None:
            param_steps = [max(0.0, base_param + k * multiple_step) for k in (-2, -1, 0, 1, 2)]

    prices, upsides = [], []
    for w in wacc_steps:
        proj = project_cash_flows(base_revenue, base_nwc, assumptions, w)
        row = [_price_for(proj, assumptions, company, w, p, method) for p in param_steps]
        prices.append(row)
        upsides.append([(p / company.current_price - 1.0) * 100.0 if company.current_price > 0
                        else float("nan") for p in row])

    return SensitivityMatrix(
        method="Gordon Growth" if method == "ggm" else "Exit Multiple",
        wacc_values=list(wacc_steps), param_values=list(param_steps), param_label=label,
        table=prices, upside_table=upsides, base_wacc=base_wacc, base_param=base_param,
        current_price=company.current_price,
    )


# ==============================================================================
# Full pipeline
# ==============================================================================

def base_year_nwc(company: HistoricalFinancials, assumptions: DCFAssumptions) -> float:
    """
    Base-year NWC is set to base revenue x Year-1 NWC %. This means the forecast
    delta NWC only reflects growth (NWC% x revenue increase), not a jump to a
    new NWC level in year 1. A simplification that is stated in the README.
    """
    return company.revenue[-1] * assumptions.nwc_pcts[0]


def run_dcf(company: HistoricalFinancials, assumptions: DCFAssumptions,
            wacc_inputs: WACCInputs) -> DCFResult:
    if not company.revenue:
        raise DataUnavailableError("Company has no historical revenue.")
    assumptions.validate()
    warnings: List[str] = []
    wacc_res = calculate_wacc(wacc_inputs)
    wacc = wacc_res.wacc
    n = assumptions.projection_years

    base_rev = company.revenue[-1]
    base_nwc = base_year_nwc(company, assumptions)
    proj = project_cash_flows(base_rev, base_nwc, assumptions, wacc)
    final_fcf = proj.fcff[-1]
    final_ebitda = proj.ebit[-1] + proj.da[-1]

    g = assumptions.perpetual_growth_rate
    ggm_tv, ggm_pv = calculate_terminal_value_ggm(final_fcf, wacc, g, n)
    ggm = build_valuation_bridge("Gordon Growth Model", proj.cumulative_pv_fcff, ggm_tv, ggm_pv,
                                 company.total_cash, company.total_debt,
                                 company.shares_outstanding, company.current_price)
    ggm.implied_exit_multiple = ggm_tv / final_ebitda if final_ebitda > 0 else float("nan")

    ex_tv, ex_pv = calculate_terminal_value_exit_multiple(final_ebitda, assumptions.exit_multiple, wacc, n)
    ext = build_valuation_bridge("Exit Multiple Method", proj.cumulative_pv_fcff, ex_tv, ex_pv,
                                 company.total_cash, company.total_debt,
                                 company.shares_outstanding, company.current_price)
    ext.implied_perpetual_growth = implied_perpetual_growth(ex_tv, final_fcf, wacc)

    if wacc <= g:
        warnings.append(f"WACC ({wacc:.2%}) is not above the perpetual growth rate ({g:.2%}); "
                        "the Gordon Growth value is undefined.")
    if final_fcf <= 0:
        warnings.append("Year-5 free cash flow is negative; the Gordon Growth terminal value is not meaningful.")
    if math.isfinite(ggm.terminal_value_pct_of_ev) and ggm.terminal_value_pct_of_ev > 85:
        warnings.append(f"Terminal value is {ggm.terminal_value_pct_of_ev:.0f}% of EV (Gordon Growth): "
                        "the result depends heavily on long-term assumptions.")
    if company.financial_currency and company.financial_currency != company.currency:
        warnings.append(f"Statements in {company.financial_currency}, price in {company.currency}: "
                        "per-share value is not comparable.")

    return DCFResult(
        company=company, assumptions=assumptions, wacc_inputs=wacc_inputs, wacc_result=wacc_res,
        projections=proj, ggm_valuation=ggm, exit_valuation=ext,
        ggm_sensitivity=generate_sensitivity_table(base_rev, base_nwc, assumptions, company, wacc_inputs, "ggm"),
        exit_sensitivity=generate_sensitivity_table(base_rev, base_nwc, assumptions, company, wacc_inputs, "exit"),
        warnings=warnings,
    )


def default_assumptions_from_history(company: HistoricalFinancials) -> DCFAssumptions:
    """
    Simple starting assumptions derived from history (the user should still
    review them): revenue CAGR, latest EBIT margin, tax rate, D&A% and capex%.
    """
    def clamp(x: float, lo: float, hi: float) -> float:
        return min(hi, max(lo, x))

    rev = company.revenue
    cagr = 0.05
    if len(rev) >= 2 and rev[0] > 0 and rev[-1] > 0:
        cagr = (rev[-1] / rev[0]) ** (1.0 / (len(rev) - 1)) - 1.0
    cagr = clamp(cagr, -0.10, 0.30)
    last_rev = rev[-1]
    margin = clamp(company.ebit[-1] / last_rev, 0.0, 0.60) if last_rev > 0 else 0.15
    tax = clamp(company.effective_tax_rate[-1], 0.0, 0.40) if company.effective_tax_rate else DEFAULT_TAX_RATE
    da = clamp(company.da[-1] / last_rev, 0.0, 0.30) if last_rev > 0 else 0.03
    capex = clamp(company.capex[-1] / last_rev, 0.0, 0.40) if last_rev > 0 else 0.04
    return DCFAssumptions(
        revenue_growth_rates=[cagr * (0.9 ** i) for i in range(5)],  # growth fades 10% per year
        ebit_margins=_five(margin), tax_rates=_five(tax), capex_pcts=_five(capex),
        da_pcts=_five(da), nwc_pcts=_five(0.05),
    )


def company_to_dict(company: HistoricalFinancials) -> Dict[str, Any]:
    return asdict(company)
