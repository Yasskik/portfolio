"""
Recalculate small exported workbooks in LibreOffice (headless) and check that every live
formula reproduces the Python engine. Skipped when LibreOffice is not installed.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")),
                                reason="LibreOffice not installed")


def test_portfolio_workbook_recalculates_to_python(tmp_path):
    import verify_excel as v
    n, bad, err = v.check_portfolio(v.portfolio_case(["SPY", "AGG"], [0.6, 0.4], 3, 21, 500, 42), tmp_path)
    assert n > 500 and bad == [] and err == 0


def test_retirement_workbook_recalculates_to_python(tmp_path):
    import verify_excel as v
    n, bad, err = v.check_retirement(v.retirement_case(50_000, 1_000, 5, 5, 20_000, 0.025, 0.07, 0.15, 300, 1), tmp_path)
    assert n > 5 and bad == [] and err == 0


def test_options_workbook_recalculates_to_python(tmp_path):
    import verify_excel as v
    n, bad, err = v.check_options(v.options_case(100, 100, 1, 0.05, 0.20, 0.0, "put", 1000, 42), tmp_path)
    assert n > 500 and bad == [] and err == 0
