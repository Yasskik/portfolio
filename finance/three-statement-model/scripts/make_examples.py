"""Build the example workbooks in examples/ (recalculated by LibreOffice so the values are cached).

* AAPL_base_case.xlsx         - Apple, base scenario, average-balance interest (iterative calculation)
* AAPL_revolver_stress.xlsx   - Apple with a one-off 55,000 special buyback: the revolver draws and is repaid
* F_bear_capacity_exceeded.xlsx - Ford, bear scenario: the revolver hits its cap and cash falls below the minimum
"""
from __future__ import annotations

import copy
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import data_loader as dl  # noqa: E402
import excel_export as xe  # noqa: E402
import model as M  # noqa: E402
from lo_recalc import SOFFICE, recalc  # noqa: E402

OUT = ROOT / "examples"


def build(ticker: str, make_drivers) -> M.ThreeStatementModel:
    h = dl.load_snapshot(ticker)
    base = M.ThreeStatementModel(copy.deepcopy(h.years), None, h.company, ticker)
    m = M.ThreeStatementModel(copy.deepcopy(h.years), make_drivers(base.drivers), h.company, ticker)
    m.driver_notes = base.driver_notes
    return m, h


def main() -> None:
    OUT.mkdir(exist_ok=True)
    cases = {
        "AAPL_base_case.xlsx": ("AAPL", lambda d: d),
        "AAPL_revolver_stress.xlsx": ("AAPL", M.revolver_stress),
        "F_bear_capacity_exceeded.xlsx": ("F", lambda d: M.scenario_drivers(d, "Bear")),
    }
    with tempfile.TemporaryDirectory() as t:
        for name, (ticker, fn) in cases.items():
            m, h = build(ticker, fn)
            wb, _ = xe.build_workbook(m, h.source, h.warnings, h.mapping)
            src = Path(t) / name
            wb.save(src)
            if SOFFICE:
                shutil.copy(recalc(src, Path(t) / "out"), OUT / name)
            else:
                shutil.copy(src, OUT / name)
            y5 = m.forecast_years[-1]
            print(f"{name}: {y5.year} revenue {y5.revenue:,.1f}  NI to common {y5.ni_common:,.1f}  cash {y5.cash:,.1f}  "
                  f"revolver {y5.revolver_debt:,.1f}  balance check {y5.balance_check:.6f}")


if __name__ == "__main__":
    main()
