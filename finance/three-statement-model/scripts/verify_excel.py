"""Verify the Excel export against the Python engine with LibreOffice (headless).

For every case the workbook is built, recalculated by LibreOffice with iterative calculation
(scripts/lo_recalc.py) and every mapped cell is compared with Python (relative tolerance 1e-6).
Cases: 5 tickers x 3 scenarios x 2 interest modes (average with iteration, circuit breaker),
plus revolver stress cases. Also checks: balance-check row = 0, Checks!max = 0, no error cells.

    python scripts/verify_excel.py            # full matrix (about 1-2 minutes)
    python scripts/verify_excel.py --quick    # AAPL only
"""
from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import openpyxl  # noqa: E402

import data_loader as dl  # noqa: E402
import excel_export as xe  # noqa: E402
import model as M  # noqa: E402
from lo_recalc import recalc  # noqa: E402

TOL = 1e-6
ERRORS = ("#VALUE!", "#REF!", "#DIV/0!", "#NAME?", "#N/A", "#NUM!", "Err:")


def cases(tickers):
    for t in tickers:
        h = dl.load_snapshot(t)
        base = M.ThreeStatementModel(copy.deepcopy(h.years), None, h.company, t).drivers
        for scen in ("Base", "Bull", "Bear"):
            for breaker in (False, True):
                d = M.scenario_drivers(base, scen)
                d.circuit_breaker = breaker
                yield f"{t} {scen} {'breaker' if breaker else 'iterative'}", h, d
        if t == "AAPL":
            for breaker in (False, True):
                d = M.revolver_stress(base)
                d.circuit_breaker = breaker
                yield f"AAPL revolver stress {'breaker' if breaker else 'iterative'}", h, d
            d = base.copy()
            d.interest_calc_method = "beginning"
            yield "AAPL Base beginning-balance method", h, d


def verify_case(name, h, d, tmp: Path) -> dict:
    m = M.ThreeStatementModel(copy.deepcopy(h.years), d, h.company, h.ticker)
    wb, cm = xe.build_workbook(m, h.source, h.warnings, h.mapping)
    src = tmp / "in" / (name.replace(" ", "_") + ".xlsx")
    src.parent.mkdir(exist_ok=True)
    wb.save(src)
    w = openpyxl.load_workbook(recalc(src, tmp / "out"), data_only=True)
    bad, worst = [], 0.0
    for key, (sheet, cell, pv) in cm.items():
        xv = w[sheet][cell].value
        if not isinstance(xv, (int, float)):
            bad.append((key, cell, xv, pv))
            continue
        e = abs(xv - pv) / max(1.0, abs(pv))
        worst = max(worst, e)
        if e > TOL:
            bad.append((key, cell, xv, pv))
    errors = [(ws.title, c.coordinate, c.value) for ws in w for row in ws.iter_rows() for c in row
              if isinstance(c.value, str) and c.value.startswith(ERRORS)]
    bs_checks = [w[s][c].value for k, (s, c, _) in cm.items() if k.startswith("Balance Sheet:balance_check:")]
    return dict(name=name, cells=len(cm), mismatches=len(bad), worst_rel=worst, errors=len(errors),
                max_check=w[cm["check:max"][0]][cm["check:max"][1]].value,
                max_bs=max(abs(v) for v in bs_checks), revolver_max=max(y.revolver_debt for y in m.forecast_years),
                shortfall=any(y.funding_shortfall > 0.005 for y in m.forecast_years), sample=bad[:3])


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    tickers = ["AAPL"] if "--quick" in argv else dl.snapshot_tickers()
    results = []
    with tempfile.TemporaryDirectory() as t:
        for name, h, d in cases(tickers):
            r = verify_case(name, h, d, Path(t))
            results.append(r)
            print(f"{r['name']:<40} cells {r['cells']:>4}  mismatches {r['mismatches']}  worst {r['worst_rel']:.1e}  "
                  f"errors {r['errors']}  BS check max {r['max_bs']:.6f}  Checks!max {r['max_check']:.6f}  "
                  f"revolver max {r['revolver_max']:,.0f}{'  SHORTFALL' if r['shortfall'] else ''}")
            if r["sample"]:
                print("   ", r["sample"])
    total = sum(r["cells"] for r in results)
    mism = sum(r["mismatches"] for r in results)
    errs = sum(r["errors"] for r in results)
    ok = mism == 0 and errs == 0 and all(abs(r["max_check"]) < 1e-6 and r["max_bs"] < 1e-6 for r in results)
    print(f"\n{len(results)} workbooks, {total:,} values compared, {mism} mismatches, {errs} error cells, "
          f"all balance checks 0: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
