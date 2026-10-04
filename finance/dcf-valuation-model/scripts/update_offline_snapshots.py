"""
Refresh data/offline_snapshots.json from Yahoo Finance.

The snapshot lets the app work offline (or when Yahoo rate-limits) for a few
well-known tickers. Run from the project root:

    python scripts/update_offline_snapshots.py AAPL MSFT KO
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dcf import SNAPSHOT_PATH, company_to_dict, fetch_company_data, load_offline_snapshots  # noqa: E402

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "KO", "TSLA"]


def main(tickers):
    snaps = load_offline_snapshots()
    for sym in tickers:
        company, meta = fetch_company_data(sym)
        if meta["source"] != "yfinance":
            print(f"{sym}: live data unavailable, skipped")
            continue
        d = company_to_dict(company)
        d["as_of"] = date.today().isoformat()
        d["description"] = d["description"][:400]
        snaps[sym] = d
        print(f"{sym}: saved ({company.years[0]}-{company.years[-1]}, price {company.current_price:.2f})")
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snaps, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main([s.upper() for s in sys.argv[1:]] or DEFAULT_TICKERS)
