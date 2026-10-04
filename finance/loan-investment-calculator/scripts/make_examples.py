"""Write the example workbooks in examples/ and check each one in LibreOffice.

    python scripts/make_examples.py
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import shutil  # noqa: E402

import verify_excel as ve  # noqa: E402
from lo_recalc import recalc  # noqa: E402

MORTGAGE = dict(principal=300_000, annual_interest_rate=0.06, term_years=25, payment_frequency=12,
                start_date=date(2026, 11, 1), recurring_extra=200, recurring_extra_start_period=1,
                lump_sum_extras={60: 10_000})
PLAN = dict(initial_amount=10_000, regular_contribution=500, contribution_frequency=12, contribution_timing="end",
            annual_return=0.07, compounding_frequency=12, years=30, annual_contribution_increase_pct=0.03,
            inflation_rate=0.025, tax_rate_on_gains=0.0)

if __name__ == "__main__":
    out = ROOT / "examples"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        n, bad, err, s = ve.check_loan(MORTGAGE, Path(d), save_as=out / "Mortgage_25yr_300k.xlsx")
        print(f"Mortgage_25yr_300k.xlsx: {n} cells checked, {len(bad)} mismatches, {err} errors | payment "
              f"{s.scheduled_payment:,.2f}, interest {s.total_interest_paid:,.2f}, saved {s.interest_saved:,.2f}, "
              f"{s.actual_payments_count} payments, payoff {s.payoff_date}")
        n, bad2, err2, t = ve.check_investment(PLAN, Path(d), save_as=out / "Investment_Plan_30yr.xlsx")
        print(f"Investment_Plan_30yr.xlsx: {n} cells checked, {len(bad2)} mismatches, {err2} errors | final "
              f"{t.final_nominal_value:,.2f}, real {t.final_real_value:,.2f}, contributed {t.total_invested:,.2f}")
        # store the LibreOffice-recalculated copies so viewers that do not recalculate still show values
        for name in ("Mortgage_25yr_300k.xlsx", "Investment_Plan_30yr.xlsx"):
            shutil.copy(recalc(out / name, Path(d) / "cached"), out / name)
    sys.exit(1 if bad or err or bad2 or err2 else 0)
