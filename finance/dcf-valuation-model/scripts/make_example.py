"""
Create examples/<TICKER>_DCF.xlsx with the same default inputs the app uses.

    python scripts/make_example.py AAPL
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dcf import WACCInputs, default_assumptions_from_history, fetch_company_data, fetch_risk_free_rate, run_dcf  # noqa: E402
from excel_export import export_to_excel  # noqa: E402


def main(sym: str = "AAPL") -> None:
    company, meta = fetch_company_data(sym)
    a = default_assumptions_from_history(company)
    # round like the app sliders (0.01% steps) so the file matches the app's default screen
    g1 = round(a.revenue_growth_rates[0], 4)
    a.revenue_growth_rates = [g1 * 0.9 ** i for i in range(5)]
    for name in ("ebit_margins", "tax_rates", "capex_pcts", "da_pcts", "nwc_pcts"):
        setattr(a, name, [round(v, 4) for v in getattr(a, name)])
    rf = round(fetch_risk_free_rate(), 4)          # app default (slider rounds to 0.01%)
    w = WACCInputs(risk_free_rate=rf, beta=round(company.beta, 2), equity_risk_premium=0.05,
                   cost_of_debt=rf + 0.01, tax_rate=round(a.tax_rates[0], 4),
                   market_cap=company.market_cap, total_debt=company.total_debt)
    result = run_dcf(company, a, w)
    out = ROOT / "examples" / f"{sym}_DCF.xlsx"
    out.parent.mkdir(exist_ok=True)
    export_to_excel(result, str(out))
    g, e = result.ggm_valuation, result.exit_valuation
    print(f"{sym} ({meta['source']}): price {company.current_price:.2f} | WACC {result.wacc_result.wacc:.2%} | "
          f"Gordon {g.implied_share_price:.2f} ({g.upside_downside_pct:+.1f}%) | "
          f"Exit {e.implied_share_price:.2f} ({e.upside_downside_pct:+.1f}%) -> {out}")


if __name__ == "__main__":
    main(sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL")
