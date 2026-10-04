"""Refresh data/prices_snapshot.csv (adjusted daily closes from Yahoo Finance).

    python scripts/update_snapshot.py --end 2026-09-30 --years 10
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import montecarlo as mc  # noqa: E402

TICKERS = ["SPY", "AGG", "BND", "QQQ", "TLT", "GLD", "IEF", "VEA"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default="2026-09-30", help="last date to include (inclusive)")
    ap.add_argument("--years", type=float, default=10)
    a = ap.parse_args()
    end_excl = (pd.Timestamp(a.end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    pdata = mc.fetch_prices(TICKERS, years=a.years, end=end_excl)
    if pdata.missing:
        print("missing:", pdata.missing)
    out = ROOT / "data" / "prices_snapshot.csv"
    pdata.prices.round(6).to_csv(out, index_label="Date")
    print(f"{out.name}: {len(pdata.prices)} rows, {pdata.first_date.date()} to {pdata.last_date.date()}, "
          f"tickers {list(pdata.prices.columns)}")
