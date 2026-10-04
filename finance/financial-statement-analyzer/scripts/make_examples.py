"""
Create the example outputs in examples/ for one ticker (default AAPL):
  <T>_analysis.xlsx, <T>_health_report.pdf, <T>_health_report.md

    python scripts/make_examples.py            # AAPL from data/snapshots.json
    python scripts/make_examples.py KO --live  # download fresh data from Yahoo Finance
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analyzer import FinancialAnalyzer, FinancialData  # noqa: E402
from excel_export import export_analysis_to_excel  # noqa: E402
from report_export import generate_markdown_report, generate_pdf_report  # noqa: E402


def main(args):
    live = "--live" in args
    tickers = [a.upper() for a in args if not a.startswith("--")] or ["AAPL"]
    out = ROOT / "examples"
    out.mkdir(exist_ok=True)
    snaps = json.loads((ROOT / "data" / "snapshots.json").read_text())
    for t in tickers:
        data = FinancialData.from_yfinance(t) if live else FinancialData.from_snapshot(snaps[t])
        an = FinancialAnalyzer(data)
        (out / f"{t}_analysis.xlsx").write_bytes(export_analysis_to_excel(an))
        (out / f"{t}_health_report.pdf").write_bytes(generate_pdf_report(an))
        (out / f"{t}_health_report.md").write_text(generate_markdown_report(an), encoding="utf-8")
        print(f"{t}: wrote {t}_analysis.xlsx, {t}_health_report.pdf, {t}_health_report.md")


if __name__ == "__main__":
    main(sys.argv[1:])
