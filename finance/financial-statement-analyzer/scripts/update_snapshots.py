"""
Download Yahoo Finance statements for a few benchmark tickers and save them to
data/snapshots.json. The tests run on this file (no internet needed) and the app
falls back to it if Yahoo Finance is unreachable.

    python scripts/update_snapshots.py            # default tickers
    python scripts/update_snapshots.py AAPL KO    # specific tickers
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analyzer import FinancialData  # noqa: E402

DEFAULT = ["AAPL", "MSFT", "KO", "PEP", "JPM", "GOOGL", "V", "MA", "CAT", "DE"]


def main(tickers):
    path = ROOT / "data" / "snapshots.json"
    snaps = json.loads(path.read_text()) if path.exists() else {}
    for t in tickers:
        fd = FinancialData.from_yfinance(t)
        snap = fd.to_snapshot()
        snap["fetched"] = date.today().isoformat()
        snaps[t] = snap
        print(f"{t}: {fd.company_name}, FY{fd.years[0]}-FY{fd.years[-1]}")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(snaps, indent=1, sort_keys=True))
    print(f"saved {len(snaps)} snapshots -> {path}")


if __name__ == "__main__":
    main([t.upper() for t in sys.argv[1:]] or DEFAULT)
