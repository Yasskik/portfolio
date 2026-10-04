"""Refresh the offline Yahoo Finance snapshot in data/yahoo_snapshot/ (needs internet).

    python scripts/update_snapshot.py AAPL MSFT KO T F
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import yfinance as yf

OUT = Path(__file__).resolve().parents[1] / "data" / "yahoo_snapshot"


def main(tickers) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta_path = OUT / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"tickers": {}}
    for t in tickers:
        tk = yf.Ticker(t)
        tk.financials.to_csv(OUT / f"{t}_income.csv")
        tk.balance_sheet.to_csv(OUT / f"{t}_balance.csv")
        tk.cashflow.to_csv(OUT / f"{t}_cashflow.csv")
        info = tk.info or {}
        meta["tickers"][t] = {"name": info.get("longName") or t, "currency": info.get("financialCurrency") or "USD"}
        print("saved", t)
    meta["downloaded"] = date.today().isoformat()
    meta["source"] = "Yahoo Finance via yfinance (annual statements)"
    meta_path.write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main([a.upper() for a in sys.argv[1:]] or ["AAPL", "MSFT", "KO", "T", "F"])
