"""Write the example workbooks in examples/, recalculated by LibreOffice and checked against Python.

    python scripts/make_examples.py

The saved files are the LibreOffice-recalculated copies, so the cached values that a viewer
without a calculation engine shows are the real formula results.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_excel as v  # noqa: E402

OUT = ROOT / "examples"

if __name__ == "__main__":
    problems = 0
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        jobs = [
            ("Portfolio_60_40_SPY_AGG.xlsx", v.check_portfolio,
             v.portfolio_case(["SPY", "AGG"], [0.6, 0.4], 5, 252, 10_000, 42)),
            ("Retirement_Plan.xlsx", v.check_retirement,
             v.retirement_case(50_000, 1_000, 25, 30, 60_000, 0.025, 0.07, 0.15, 10_000, 42)),
            ("Option_BS_vs_MC.xlsx", v.check_options,
             v.options_case(100, 100, 1, 0.05, 0.20, 0.0, "call", 10_000, 42)),
        ]
        for name, check, case in jobs:
            n, bad, err = check(case, tmp, save_as=OUT / name)
            problems += len(bad) + err
            print(f"{name:32s} {n:7,d} values compared, {len(bad)} mismatches, {err} error cells")
    sys.exit(1 if problems else 0)
