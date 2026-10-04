"""
finance_calc.py - time value of money (TVM) engine
==================================================

Pure-Python functions that follow Microsoft Excel's conventions (and were checked
against LibreOffice Calc, which implements the same functions):

    pmt, ipmt, ppmt, fv, pv, nper, rate, npv, irr, effect (EFFECT), nominal (NOMINAL)

plus three models built on them:

* compute_amortization_schedule - fixed-payment (annuity), equal-principal and
  interest-only + balloon loans, with recurring and lump-sum extra payments.
* compute_investment_growth - initial amount + periodic contributions with
  beginning/end timing, any compounding frequency, step-ups, tax and inflation.
* analyze_cash_flows / compare_two_loans / compare_apr_ear_frequencies - tools.

Conventions (stated on purpose, see README "Conventions")
---------------------------------------------------------
Cash-flow signs follow Excel: money you receive is positive, money you pay is
negative. PMT(0.005, 360, 200000) is therefore about -1,199.10.

Rates: a "nominal annual rate" (APR) compounded m times a year has an effective
annual rate EAR = (1 + APR/m)^m - 1. When payments/contributions happen p times a
year, the model uses the *equivalent periodic rate*
    i_p = (1 + APR/m)^(m/p) - 1          (continuous: i_p = e^(APR/p) - 1)
which earns exactly the same EAR. When m == p this is simply APR/p.

Loans: interest per period = ROUND(balance x i_p, 2); the regular payment is
rounded to cents; the last payment absorbs the rounding so the balance ends at
exactly 0.00. Extra payments go straight to principal, the regular payment is
NOT recalculated, so the loan simply ends earlier.

Rounding uses "round half away from zero" (like Excel's ROUND), not Python's
banker's rounding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dateutil.relativedelta import relativedelta

SUPPORTED_FREQUENCIES = {1: "Annual", 2: "Semi-annual", 4: "Quarterly", 6: "Bi-monthly",
                         12: "Monthly", 26: "Bi-weekly", 52: "Weekly"}
CONTINUOUS = 0  # compounding frequency code for continuous compounding


# ============================================================================
# 0. Helpers
# ============================================================================

def xround(x: float, decimals: int = 2) -> float:
    """Round half away from zero, like Excel's ROUND (works on 15 significant digits)."""
    if x is None or not math.isfinite(x):
        return x
    q = Decimal(1).scaleb(-decimals)
    d = Decimal(f"{x:.15g}").quantize(q, rounding=ROUND_HALF_UP)
    return float(d) + 0.0  # + 0.0 turns -0.0 into 0.0


def periodic_rate(annual_nominal_rate: float, compounding_per_year: int, periods_per_year: int) -> float:
    """Equivalent rate per payment period.

    i_p = (1 + APR/m)^(m/p) - 1, continuous (m == 0 or < 0): e^(APR/p) - 1.
    When m == p it returns APR/p exactly.
    """
    p = periods_per_year
    if p <= 0:
        raise ValueError("Periods per year must be positive.")
    m = compounding_per_year
    if m is None or m == p:
        return annual_nominal_rate / p
    if m <= 0:
        return math.exp(annual_nominal_rate / p) - 1.0
    return (1.0 + annual_nominal_rate / m) ** (m / p) - 1.0


def _period_date(first: date, k: int, freq: int) -> date:
    """Date of payment k (1-based). Monthly-type frequencies use calendar months
    counted from the first date (31 Jan -> 28/29 Feb -> 31 Mar, like Excel EDATE);
    bi-weekly / weekly add 14 / 7 days."""
    if 12 % freq == 0:
        return first + relativedelta(months=(k - 1) * (12 // freq))
    return first + timedelta(days=(k - 1) * round(364 / freq))


# ============================================================================
# 1. Excel-compatible TVM functions
# ============================================================================

def pmt(rate: float, nper: float, pv: float, fv: float = 0.0, when: int = 0) -> float:
    """Excel PMT(rate, nper, pv, [fv], [type]). when: 0 = end, 1 = beginning."""
    if nper <= 0:
        raise ValueError("nper must be > 0 (Excel returns #NUM!).")
    if rate == 0:
        return -(pv + fv) / nper
    temp = (1.0 + rate) ** nper
    return -(fv + pv * temp) * rate / ((1.0 + rate * when) * (temp - 1.0))


def fv(rate: float, nper: float, pmt_val: float, pv: float = 0.0, when: int = 0) -> float:
    """Excel FV(rate, nper, pmt, [pv], [type])."""
    if rate == 0:
        return -(pv + pmt_val * nper)
    temp = (1.0 + rate) ** nper
    return -(pv * temp + pmt_val * (1.0 + rate * when) * (temp - 1.0) / rate)


def pv(rate: float, nper: float, pmt_val: float, fv_val: float = 0.0, when: int = 0) -> float:
    """Excel PV(rate, nper, pmt, [fv], [type])."""
    if rate == 0:
        return -(fv_val + pmt_val * nper)
    temp = (1.0 + rate) ** nper
    return -(fv_val + pmt_val * (1.0 + rate * when) * (temp - 1.0) / rate) / temp


def nper(rate: float, pmt_val: float, pv_val: float, fv_val: float = 0.0, when: int = 0) -> float:
    """Excel NPER(rate, pmt, pv, [fv], [type]). Raises ValueError where Excel shows #NUM!."""
    if rate == 0:
        if pmt_val == 0:
            raise ValueError("pmt cannot be 0 when rate is 0.")
        return -(pv_val + fv_val) / pmt_val
    a = pmt_val * (1.0 + rate * when) / rate
    num, den = a - fv_val, pv_val + a
    if den == 0 or num / den <= 0:
        raise ValueError("No solution: the payment never repays the loan (Excel #NUM!).")
    return math.log(num / den) / math.log(1.0 + rate)


def _tvm_residual(r: float, n: float, p: float, pv_val: float, fv_val: float, when: int) -> float:
    if r == 0:
        return pv_val + p * n + fv_val
    t = (1.0 + r) ** n
    return pv_val * t + p * (1.0 + r * when) * (t - 1.0) / r + fv_val


def rate(nper_val: float, pmt_val: float, pv_val: float, fv_val: float = 0.0, when: int = 0,
         guess: float = 0.1, max_iter: int = 200, tol: float = 1e-12) -> float:
    """Excel RATE(nper, pmt, pv, [fv], [type], [guess]).

    Newton's method from `guess` (numerical derivative), then a bracketing
    bisection on (-0.99, 10]. Raises ValueError if there is no solution."""
    f = lambda r: _tvm_residual(r, nper_val, pmt_val, pv_val, fv_val, when)
    scale = max(1.0, abs(pv_val), abs(fv_val), abs(pmt_val) * nper_val)
    r = guess
    for _ in range(max_iter):
        y = f(r)
        if abs(y) < tol * scale:
            return r
        h = 1e-7 * max(1.0, abs(r))
        dy = (f(r + h) - f(r - h)) / (2 * h)
        if dy == 0 or not math.isfinite(dy):
            break
        r_new = r - y / dy
        if not math.isfinite(r_new) or r_new <= -1.0:
            break
        if abs(r_new - r) < 1e-14:
            return r_new
        r = r_new
    roots = _bracket_roots(f, -0.99, 10.0)
    if not roots:
        raise ValueError("RATE did not converge (Excel #NUM!).")
    return min(roots, key=lambda x: abs(x - guess))


def ipmt(rate_val: float, per: int, nper_val: float, pv_val: float, fv_val: float = 0.0, when: int = 0) -> float:
    """Excel IPMT(rate, per, nper, pv, [fv], [type]): interest part of payment `per`."""
    if per < 1 or per > nper_val:
        raise ValueError(f"per must be between 1 and nper ({nper_val}).")
    p = pmt(rate_val, nper_val, pv_val, fv_val, when)
    if when == 1:
        if per == 1:
            return 0.0
        # Excel convention: the payment at the start of period `per` pays the interest that
        # accrued during period per-1 on the balance left after payment per-1.
        return fv(rate_val, per - 2, p, pv_val + p, 0) * rate_val
    bal = fv(rate_val, per - 1, p, pv_val, 0)
    return bal * rate_val


def ppmt(rate_val: float, per: int, nper_val: float, pv_val: float, fv_val: float = 0.0, when: int = 0) -> float:
    """Excel PPMT = PMT - IPMT."""
    return pmt(rate_val, nper_val, pv_val, fv_val, when) - ipmt(rate_val, per, nper_val, pv_val, fv_val, when)


def npv(rate_val: float, values: List[float]) -> float:
    """Excel NPV(rate, value1, value2, ...).

    IMPORTANT: Excel discounts the FIRST value by one full period (t = 1). For a
    project with an initial outlay at t = 0 use  CF0 + NPV(rate, CF1..CFn)
    (see net_present_value)."""
    return sum(v / (1.0 + rate_val) ** (t + 1) for t, v in enumerate(values))


def net_present_value(discount_rate: float, initial_investment: float, cash_flows: List[float]) -> float:
    """Textbook NPV with CF0 at t = 0 (not discounted): CF0 + NPV(rate, CF1..CFn)."""
    return initial_investment + npv(discount_rate, cash_flows)


def _npv_t0(r: float, values: List[float]) -> float:
    return sum(v / (1.0 + r) ** t for t, v in enumerate(values))


def _bracket_roots(f, lo: float, hi: float, steps: int = 4000) -> List[float]:
    """All sign changes of f on a grid (denser near 0), each refined by bisection."""
    grid = sorted(set([lo + (hi - lo) * (k / steps) ** 2 for k in range(steps + 1)]
                      + [-0.99 + 1.99 * k / steps for k in range(steps + 1)]))
    grid = [g for g in grid if lo <= g <= hi]
    roots: List[float] = []
    prev_x, prev_y = grid[0], f(grid[0])
    for x in grid[1:]:
        y = f(x)
        if prev_y == 0:
            roots.append(prev_x)
        elif prev_y * y < 0:
            a, b, fa = prev_x, x, prev_y
            for _ in range(200):
                mid = (a + b) / 2
                fm = f(mid)
                if fm == 0 or (b - a) < 1e-15:
                    break
                if fa * fm < 0:
                    b = mid
                else:
                    a, fa = mid, fm
            roots.append((a + b) / 2)
        prev_x, prev_y = x, y
    out: List[float] = []
    for r in roots:
        if not out or abs(r - out[-1]) > 1e-9:
            out.append(r)
    return out


def irr_all(values: List[float], lo: float = -0.99, hi: float = 10.0) -> List[float]:
    """Every IRR in (lo, hi]: all rates where NPV(t=0 convention) = 0."""
    return _bracket_roots(lambda r: _npv_t0(r, values), lo, hi)


def sign_changes(values: List[float]) -> int:
    s = [v for v in values if v != 0]
    return sum(1 for a, b in zip(s, s[1:]) if (a < 0) != (b < 0))


def irr(values: List[float], guess: float = 0.1, max_iter: int = 100, tol: float = 1e-12) -> float:
    """Excel IRR(values, [guess]); values[0] is at t = 0.

    Raises ValueError when there is no sign change or no root (Excel #NUM!).
    With several sign changes there can be several IRRs; like Excel this returns
    the one Newton's method reaches from `guess` (use irr_all to see them all)."""
    if len(values) < 2:
        raise ValueError("IRR needs at least two cash flows.")
    if not (any(v > 0 for v in values) and any(v < 0 for v in values)):
        raise ValueError("IRR needs at least one negative and one positive cash flow.")
    r = guess
    scale = max(abs(v) for v in values)
    for _ in range(max_iter):
        f_val = _npv_t0(r, values)
        if abs(f_val) < tol * scale:
            return r
        d = sum(-t * v / (1.0 + r) ** (t + 1) for t, v in enumerate(values))
        if d == 0:
            break
        r_new = r - f_val / d
        if not math.isfinite(r_new) or r_new <= -1.0:
            break
        if abs(r_new - r) < 1e-14:
            return r_new
        r = r_new
    roots = irr_all(values)
    if not roots:
        raise ValueError("IRR did not converge (Excel #NUM!).")
    return min(roots, key=lambda x: abs(x - guess))


def effect(nominal_rate: float, npery: int) -> float:
    """Excel EFFECT(nominal_rate, npery). npery is truncated to an integer >= 1."""
    m = int(npery)
    if nominal_rate <= 0 or m < 1:
        raise ValueError("EFFECT needs nominal_rate > 0 and npery >= 1 (Excel #NUM!).")
    return (1.0 + nominal_rate / m) ** m - 1.0


def nominal(effect_rate: float, npery: int) -> float:
    """Excel NOMINAL(effect_rate, npery)."""
    m = int(npery)
    if effect_rate <= 0 or m < 1:
        raise ValueError("NOMINAL needs effect_rate > 0 and npery >= 1 (Excel #NUM!).")
    return m * ((1.0 + effect_rate) ** (1.0 / m) - 1.0)


def apr_to_ear(nominal_apr: float, compounding_periods_per_year: int) -> float:
    """EAR = (1 + APR/m)^m - 1 ; continuous (m <= 0): e^APR - 1. Allows 0 and negative rates."""
    m = compounding_periods_per_year
    if m <= 0:
        return math.exp(nominal_apr) - 1.0
    return (1.0 + nominal_apr / m) ** m - 1.0


def ear_to_apr(effective_ear: float, compounding_periods_per_year: int) -> float:
    """APR = m((1 + EAR)^(1/m) - 1) ; continuous: ln(1 + EAR)."""
    m = compounding_periods_per_year
    if m <= 0:
        return math.log(1.0 + effective_ear)
    return m * ((1.0 + effective_ear) ** (1.0 / m) - 1.0)


# ============================================================================
# 2. Loan amortization
# ============================================================================

LOAN_TYPES = ("fixed_payment", "equal_principal", "interest_only")


@dataclass
class AmortizationSummary:
    original_principal: float
    annual_interest_rate: float
    term_years: float
    payment_frequency: int
    loan_type: str
    scheduled_payment: float          # regular payment (equal principal: the FIRST payment)
    total_payments_count: int         # contractual number of payments
    actual_payments_count: int        # with extra payments
    payoff_date: date
    original_payoff_date: date
    total_principal_paid: float
    total_interest_paid: float
    total_extra_paid: float
    total_amount_paid: float
    baseline_total_interest: float
    interest_saved: float
    periods_saved: int
    years_saved: float
    periodic_rate: float = 0.0
    compounding_frequency: int = 12
    final_payment: float = 0.0        # last payment (includes any balloon)
    balloon_amount: float = 0.0


@dataclass
class AmortizationResult:
    schedule: pd.DataFrame
    summary: AmortizationSummary
    baseline_schedule: pd.DataFrame


def _build_schedule(principal, i, n, first_date, freq, loan_type, base_pmt, base_principal,
                    recurring_extra, extra_start, lump_sums):
    rows = []
    bal = xround(principal, 2)
    cum_i = cum_p = 0.0
    for k in range(1, n + 1):
        if bal <= 0:
            break
        beg = bal
        interest = xround(beg * i, 2)
        last = k == n
        if loan_type == "fixed_payment":
            sched = beg + interest if last else min(base_pmt, beg + interest)
            prin = max(0.0, xround(sched - interest, 2))
            sched = xround(prin + interest, 2)
        elif loan_type == "equal_principal":
            prin = beg if last else min(base_principal, beg)
            sched = xround(prin + interest, 2)
        else:  # interest_only
            prin = beg if last else 0.0
            sched = xround(prin + interest, 2)
        wanted = (recurring_extra if k >= extra_start else 0.0) + lump_sums.get(k, 0.0)
        extra = xround(min(max(0.0, beg - prin), max(0.0, wanted)), 2)
        end = xround(beg - prin - extra, 2)
        total = xround(sched + extra, 2)
        cum_i = xround(cum_i + interest, 2)
        cum_p = xround(cum_p + prin + extra, 2)
        rows.append({
            "period": k, "date": _period_date(first_date, k, freq), "beginning_balance": beg,
            "scheduled_payment": sched, "principal": prin, "interest": interest,
            "extra_payment": extra, "total_payment": total, "ending_balance": end,
            "cumulative_interest": cum_i, "cumulative_principal": cum_p,
        })
        bal = end
    return pd.DataFrame(rows)


def compute_amortization_schedule(
    principal: float,
    annual_interest_rate: float,
    term_years: float,
    payment_frequency: int = 12,
    start_date: Optional[date] = None,
    loan_type: str = "fixed_payment",
    recurring_extra_payment: float = 0.0,
    recurring_extra_start_period: int = 1,
    lump_sum_extras: Optional[Dict[int, float]] = None,
    balloon_amount: float = 0.0,
    round_decimals: int = 2,
    compounding_frequency: Optional[int] = None,
) -> AmortizationResult:
    """Loan schedule. `start_date` is the date of the FIRST payment.

    loan_type:
      fixed_payment   - level payment PMT(i, n, -P, balloon); optional balloon is
                        paid with the last payment.
      equal_principal - principal P/n each period + interest on the balance.
      interest_only   - interest only, whole principal (the balloon) paid with the last payment.
    compounding_frequency: None = same as payment frequency (US-style APR / p);
      e.g. 2 for Canadian semi-annual compounding (equivalent periodic rate is used).
    """
    if principal <= 0:
        raise ValueError("Principal must be greater than zero.")
    if term_years <= 0:
        raise ValueError("Term must be greater than zero.")
    if payment_frequency not in SUPPORTED_FREQUENCIES:
        raise ValueError(f"Payment frequency must be one of {sorted(SUPPORTED_FREQUENCIES)}.")
    if annual_interest_rate < 0:
        raise ValueError("Interest rate cannot be negative.")
    if loan_type not in LOAN_TYPES:
        raise ValueError(f"Unknown loan_type '{loan_type}'. Expected one of {LOAN_TYPES}.")
    if not (0 <= balloon_amount < principal):
        raise ValueError("Balloon must be at least 0 and smaller than the principal.")
    if recurring_extra_payment < 0 or any(v < 0 for v in (lump_sum_extras or {}).values()):
        raise ValueError("Extra payments cannot be negative.")
    if round_decimals != 2:
        raise ValueError("Schedules are calculated in cents (round_decimals=2).")
    start_date = start_date or date.today()
    lump = {int(k): float(v) for k, v in (lump_sum_extras or {}).items() if v}
    freq = payment_frequency
    n = int(round(term_years * freq))
    if n < 1:
        raise ValueError("Term is shorter than one payment period.")
    comp = freq if compounding_frequency is None else compounding_frequency
    i = periodic_rate(annual_interest_rate, comp, freq)

    base_principal = 0.0
    if loan_type == "fixed_payment":
        base_pmt = xround(-pmt(i, n, principal, -balloon_amount), 2)
    elif loan_type == "equal_principal":
        if balloon_amount:
            raise ValueError("A balloon is only supported for fixed-payment loans.")
        base_principal = xround(principal / n, 2)
        base_pmt = xround(base_principal + xround(principal * i, 2), 2)
    else:
        if balloon_amount:
            raise ValueError("For interest-only loans the balloon is the whole principal; leave balloon at 0.")
        base_pmt = xround(principal * i, 2)

    args = (principal, i, n, start_date, freq, loan_type, base_pmt, base_principal)
    df_base = _build_schedule(*args, 0.0, 1, {})
    df = _build_schedule(*args, recurring_extra_payment, max(1, int(recurring_extra_start_period)), lump)

    base_int = xround(df_base["interest"].sum(), 2)
    tot_int = xround(df["interest"].sum(), 2)
    periods_saved = n - len(df)
    summary = AmortizationSummary(
        original_principal=principal, annual_interest_rate=annual_interest_rate, term_years=term_years,
        payment_frequency=freq, loan_type=loan_type, scheduled_payment=base_pmt,
        total_payments_count=n, actual_payments_count=len(df),
        payoff_date=df["date"].iloc[-1], original_payoff_date=_period_date(start_date, n, freq),
        total_principal_paid=xround(df["principal"].sum() + df["extra_payment"].sum(), 2),
        total_interest_paid=tot_int, total_extra_paid=xround(df["extra_payment"].sum(), 2),
        total_amount_paid=xround(df["total_payment"].sum(), 2), baseline_total_interest=base_int,
        interest_saved=xround(base_int - tot_int, 2), periods_saved=periods_saved,
        years_saved=round(periods_saved / freq, 2), periodic_rate=i, compounding_frequency=comp,
        final_payment=float(df["total_payment"].iloc[-1]), balloon_amount=balloon_amount,
    )
    return AmortizationResult(schedule=df, summary=summary, baseline_schedule=df_base)


# ============================================================================
# 3. Investment growth
# ============================================================================

@dataclass
class InvestmentSummary:
    initial_amount: float
    total_contributions: float        # periodic contributions only (excludes the initial amount)
    total_growth: float               # investment growth after tax
    total_taxes_paid: float
    final_nominal_value: float
    final_real_value: float
    purchasing_power_loss: float
    effective_annual_return: float
    years: float
    periodic_rate: float = 0.0
    total_invested: float = 0.0       # initial + contributions
    gross_growth: float = 0.0


@dataclass
class InvestmentResult:
    period_schedule: pd.DataFrame
    annual_schedule: pd.DataFrame
    summary: InvestmentSummary


def compute_investment_growth(
    initial_amount: float,
    regular_contribution: float,
    contribution_frequency: int = 12,
    contribution_timing: str = "end",
    annual_return: float = 0.07,
    compounding_frequency: int = 12,
    years: float = 10.0,
    annual_contribution_increase_pct: float = 0.0,
    inflation_rate: float = 0.025,
    tax_rate_on_gains: float = 0.0,
    round_decimals: int = 2,
) -> InvestmentResult:
    """Period-by-period growth model (no intermediate rounding, so it matches Excel's FV).

    Per period k (p contributions a year, equivalent periodic rate i):
        contribution C_k = C x (1 + step_up)^(year - 1)
        growth G_k      = (B_{k-1} + C_k x [timing = beginning]) x i
        tax T_k         = G_k x tax_rate if G_k > 0 else 0   (gains taxed as they accrue; no refund for losses)
        B_k             = B_{k-1} + C_k + G_k - T_k
        real value      = B_k / (1 + inflation)^(k / p)
    compounding_frequency: 1, 2, 4, 12, 26, 52, 365, or 0 / -1 for continuous.
    """
    if initial_amount < 0 or regular_contribution < 0:
        raise ValueError("Initial amount and contributions cannot be negative.")
    if years <= 0:
        raise ValueError("Investment years must be greater than zero.")
    if contribution_frequency <= 0:
        raise ValueError("Contribution frequency must be positive.")
    if contribution_timing not in ("end", "beginning"):
        raise ValueError("contribution_timing must be 'end' or 'beginning'.")
    if not (0 <= tax_rate_on_gains < 1):
        raise ValueError("Tax rate must be between 0% and 100%.")
    if annual_return <= -1:
        raise ValueError("Annual return must be greater than -100%.")
    p = contribution_frequency
    n = int(round(years * p))
    i = periodic_rate(annual_return, compounding_frequency, p)
    ear = apr_to_ear(annual_return, compounding_frequency)
    begin = contribution_timing == "beginning"

    bal = float(initial_amount)
    cum_c = cum_g = cum_t = cum_gross = 0.0
    rows = []
    for k in range(1, n + 1):
        yr = (k - 1) // p + 1
        c = regular_contribution * (1.0 + annual_contribution_increase_pct) ** (yr - 1)
        g = (bal + (c if begin else 0.0)) * i
        t = g * tax_rate_on_gains if g > 0 else 0.0
        beg = bal
        bal = bal + c + g - t
        cum_c += c
        cum_g += g - t
        cum_t += t
        cum_gross += g
        rows.append({
            "period": k, "year": yr, "period_in_year": (k - 1) % p + 1, "beginning_balance": beg,
            "contribution": c, "gross_growth": g, "tax": t, "net_growth": g - t, "ending_balance": bal,
            "real_balance": bal / (1.0 + inflation_rate) ** (k / p),
            "cumulative_contributions": initial_amount + cum_c, "cumulative_growth": cum_g,
        })
    dfp = pd.DataFrame(rows)
    annual = []
    for yr, g in dfp.groupby("year"):
        annual.append({
            "year": int(yr), "beginning_balance": g["beginning_balance"].iloc[0],
            "contributions": g["contribution"].sum(), "interest_earned": g["net_growth"].sum(),
            "tax_paid": g["tax"].sum(), "ending_balance": g["ending_balance"].iloc[-1],
            "real_balance": g["real_balance"].iloc[-1],
            "cumulative_contributions": g["cumulative_contributions"].iloc[-1],
            "cumulative_growth": g["cumulative_growth"].iloc[-1],
        })
    dfa = pd.DataFrame(annual)
    final_real = float(dfp["real_balance"].iloc[-1])
    summary = InvestmentSummary(
        initial_amount=initial_amount, total_contributions=cum_c, total_growth=cum_g,
        total_taxes_paid=cum_t, final_nominal_value=bal, final_real_value=final_real,
        purchasing_power_loss=bal - final_real, effective_annual_return=ear, years=years,
        periodic_rate=i, total_invested=initial_amount + cum_c, gross_growth=cum_gross,
    )
    return InvestmentResult(period_schedule=dfp, annual_schedule=dfa, summary=summary)


def _inv_kwargs(**kw):
    return {k: v for k, v in kw.items()}


def goal_seek_contribution(
    target_future_value: float, initial_amount: float, years: float, annual_return: float,
    contribution_frequency: int = 12, contribution_timing: str = "end", compounding_frequency: int = 12,
    annual_contribution_increase_pct: float = 0.0, inflation_rate: float = 0.0,
    tax_rate_on_gains: float = 0.0, adjust_target_for_inflation: bool = False,
) -> float:
    """Contribution per period (first-year amount if there is a step-up) that reaches the target.

    The final value is linear in the contribution (as long as growth stays positive), so
    the answer is found exactly from two model runs, then checked; bisection is the fallback.
    Returns 0.0 if the initial amount alone already reaches the target."""
    target = target_future_value
    if adjust_target_for_inflation:
        target *= (1.0 + inflation_rate) ** years
    common = dict(initial_amount=initial_amount, contribution_frequency=contribution_frequency,
                  contribution_timing=contribution_timing, annual_return=annual_return,
                  compounding_frequency=compounding_frequency, years=years,
                  annual_contribution_increase_pct=annual_contribution_increase_pct,
                  inflation_rate=inflation_rate, tax_rate_on_gains=tax_rate_on_gains)
    f = lambda c: compute_investment_growth(regular_contribution=c, **common).summary.final_nominal_value
    f0 = f(0.0)
    if f0 >= target:
        return 0.0
    f1 = f(1.0)
    c = (target - f0) / (f1 - f0)
    if abs(f(c) - target) <= 1e-6 * max(1.0, target):
        return c
    lo, hi = 0.0, max(1.0, c * 2)
    while f(hi) < target:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def goal_seek_return(
    target_future_value: float, initial_amount: float, regular_contribution: float, years: float,
    contribution_frequency: int = 12, contribution_timing: str = "end", compounding_frequency: int = 12,
    annual_contribution_increase_pct: float = 0.0, inflation_rate: float = 0.0,
    tax_rate_on_gains: float = 0.0, adjust_target_for_inflation: bool = False,
    max_rate: float = 1.0,
) -> Optional[float]:
    """Nominal annual return (same compounding as the model) needed to reach the target.

    The final value rises with the rate, so bisection on [-0.99, max_rate] always converges
    when a solution exists. Returns None if the target needs more than max_rate (100%/yr)
    or if nothing is invested."""
    target = target_future_value
    if adjust_target_for_inflation:
        target *= (1.0 + inflation_rate) ** years
    if initial_amount <= 0 and regular_contribution <= 0:
        return None
    common = dict(initial_amount=initial_amount, regular_contribution=regular_contribution,
                  contribution_frequency=contribution_frequency, contribution_timing=contribution_timing,
                  compounding_frequency=compounding_frequency, years=years,
                  annual_contribution_increase_pct=annual_contribution_increase_pct,
                  inflation_rate=inflation_rate, tax_rate_on_gains=tax_rate_on_gains)
    f = lambda r: compute_investment_growth(annual_return=r, **common).summary.final_nominal_value - target
    lo, hi = -0.99, max_rate
    if f(hi) < 0:
        return None
    if f(lo) > 0:
        return lo
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return (lo + hi) / 2


# ============================================================================
# 4. Tools: NPV / IRR / payback, APR vs EAR, loan comparison
# ============================================================================

@dataclass
class CashFlowAnalysisResult:
    npv: float                                 # CF0 at t = 0 + discounted CF1..CFn
    irr: Optional[float]
    profitability_index: Optional[float]
    payback_period: Optional[float]
    discounted_payback_period: Optional[float]
    cumulative_cash_flows: List[float]
    cumulative_discounted_cash_flows: List[float]
    excel_npv_all_values: float = 0.0          # =NPV(rate, CF0..CFn): the common mistake (CF0 discounted too)
    irr_roots: List[float] = field(default_factory=list)
    irr_note: str = ""


def analyze_cash_flows(initial_investment: float, cash_flows: List[float], discount_rate: float) -> CashFlowAnalysisResult:
    """Project appraisal. initial_investment is the outlay at t = 0 (entered as a positive number);
    cash_flows are CF1..CFn at the END of years 1..n."""
    cf0 = -abs(initial_investment)
    all_cfs = [cf0] + list(cash_flows)
    npv_val = net_present_value(discount_rate, cf0, cash_flows)
    roots, note, irr_val = [], "", None
    if sign_changes(all_cfs) == 0:
        note = "No IRR: the cash flows never change sign."
    else:
        roots = irr_all(all_cfs)
        try:
            irr_val = irr(all_cfs)
        except ValueError:
            irr_val = None
        if not roots and irr_val is None:
            note = "No IRR found between -99% and 1,000%."
        elif len(roots) > 1:
            note = ("Multiple IRRs (" + ", ".join(f"{r:.2%}" for r in roots) +
                    "): the cash flows change sign more than once, so use NPV to decide.")
        elif sign_changes(all_cfs) > 1:
            note = "Cash flows change sign more than once; only one IRR was found, but rely on NPV."
    pv_in = npv(discount_rate, cash_flows)
    pi = pv_in / abs(cf0) if cf0 != 0 else None

    cum, cum_d = cf0, cf0
    cum_list, cum_d_list = [cum], [cum_d]
    payback = disc_payback = None
    for t, cf in enumerate(cash_flows, start=1):
        prev, prev_d = cum, cum_d
        cum += cf
        d = cf / (1.0 + discount_rate) ** t
        cum_d += d
        cum_list.append(cum)
        cum_d_list.append(cum_d)
        if payback is None and prev < 0 <= cum:
            payback = (t - 1) + (-prev / cf)
        if disc_payback is None and prev_d < 0 <= cum_d:
            disc_payback = (t - 1) + (-prev_d / d)
    if cf0 == 0:
        payback = disc_payback = 0.0
    return CashFlowAnalysisResult(
        npv=npv_val, irr=irr_val, profitability_index=pi, payback_period=payback,
        discounted_payback_period=disc_payback, cumulative_cash_flows=cum_list,
        cumulative_discounted_cash_flows=cum_d_list, excel_npv_all_values=npv(discount_rate, all_cfs),
        irr_roots=roots, irr_note=note,
    )


def compare_apr_ear_frequencies(apr: float) -> pd.DataFrame:
    rows = []
    for label, m in [("Annually", 1), ("Semi-Annually", 2), ("Quarterly", 4), ("Monthly", 12),
                     ("Bi-Weekly", 26), ("Weekly", 52), ("Daily", 365), ("Continuous", -1)]:
        e = apr_to_ear(apr, m)
        rows.append({"Compounding Frequency": label, "Periods/Year": str(m) if m > 0 else "Continuous",
                     "Nominal APR": apr, "Effective EAR (APY)": e, "Spread (bps)": round((e - apr) * 10000, 2)})
    return pd.DataFrame(rows)


@dataclass
class LoanComparisonResult:
    loan_a_name: str
    loan_b_name: str
    loan_a_pmt: float
    loan_b_pmt: float
    loan_a_total_interest: float
    loan_b_total_interest: float
    loan_a_total_paid: float
    loan_b_total_paid: float
    payment_difference: float
    interest_difference: float
    total_cost_difference: float
    cheaper_loan: str
    breakeven_months: Optional[float]
    summary_df: pd.DataFrame
    loan_a_apr_with_fees: Optional[float] = None
    loan_b_apr_with_fees: Optional[float] = None


def _apr_with_fees(principal, payment, n, fees, freq):
    """Annual rate that equates the net amount received (principal - fees) with the payments."""
    if fees <= 0:
        return None
    try:
        return rate(n, -payment, principal - fees) * freq
    except ValueError:
        return None


def compare_two_loans(
    principal_a: float, rate_a: float, term_a_years: float, upfront_fees_a: float = 0.0,
    principal_b: float = 0.0, rate_b: float = 0.0, term_b_years: float = 0.0, upfront_fees_b: float = 0.0,
    freq: int = 12, name_a: str = "Loan A", name_b: str = "Loan B",
) -> LoanComparisonResult:
    """Side-by-side comparison of two fixed-payment loans. Totals are undiscounted
    (simple sums of cash paid); 'break-even' = extra fees / payment saving per period."""
    principal_b = principal_b or principal_a
    term_b_years = term_b_years or term_a_years
    ra = compute_amortization_schedule(principal_a, rate_a, term_a_years, freq)
    rb = compute_amortization_schedule(principal_b, rate_b, term_b_years, freq)
    pa, pb = ra.summary.scheduled_payment, rb.summary.scheduled_payment
    ia, ib = ra.summary.total_interest_paid, rb.summary.total_interest_paid
    ca = xround(ra.summary.total_amount_paid + upfront_fees_a, 2)
    cb = xround(rb.summary.total_amount_paid + upfront_fees_b, 2)
    fee_diff, pay_diff = upfront_fees_b - upfront_fees_a, pa - pb
    breakeven = None
    if fee_diff * pay_diff > 0:
        breakeven = round(abs(fee_diff) / abs(pay_diff), 1)
    cheaper = name_a if ca < cb else name_b
    per = SUPPORTED_FREQUENCIES.get(freq, f"{freq}/yr")
    summary_df = pd.DataFrame([
        {"Metric": "Loan Amount", name_a: principal_a, name_b: principal_b, "Difference": principal_b - principal_a},
        {"Metric": "Interest Rate", name_a: f"{rate_a*100:.3f}%", name_b: f"{rate_b*100:.3f}%", "Difference": f"{(rate_b-rate_a)*100:+.3f}%"},
        {"Metric": "Term (Years)", name_a: f"{term_a_years:g} yrs", name_b: f"{term_b_years:g} yrs", "Difference": f"{term_b_years-term_a_years:+g} yrs"},
        {"Metric": "Upfront Points/Fees", name_a: upfront_fees_a, name_b: upfront_fees_b, "Difference": fee_diff},
        {"Metric": f"{per} Payment", name_a: pa, name_b: pb, "Difference": xround(pb - pa, 2)},
        {"Metric": "Total Interest", name_a: ia, name_b: ib, "Difference": xround(ib - ia, 2)},
        {"Metric": "Total Cost (payments + fees, undiscounted)", name_a: ca, name_b: cb, "Difference": xround(cb - ca, 2)},
    ])
    n_a, n_b = ra.summary.total_payments_count, rb.summary.total_payments_count
    return LoanComparisonResult(
        loan_a_name=name_a, loan_b_name=name_b, loan_a_pmt=pa, loan_b_pmt=pb,
        loan_a_total_interest=ia, loan_b_total_interest=ib, loan_a_total_paid=ca, loan_b_total_paid=cb,
        payment_difference=xround(pb - pa, 2), interest_difference=xround(ib - ia, 2),
        total_cost_difference=xround(cb - ca, 2), cheaper_loan=cheaper, breakeven_months=breakeven,
        summary_df=summary_df,
        loan_a_apr_with_fees=_apr_with_fees(principal_a, pa, n_a, upfront_fees_a, freq),
        loan_b_apr_with_fees=_apr_with_fees(principal_b, pb, n_b, upfront_fees_b, freq),
    )
