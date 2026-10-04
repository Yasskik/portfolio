"""
Run the Streamlit app headlessly (streamlit.testing AppTest) for all three modules.
The portfolio module uses the offline snapshot, so no network is needed.
"""
from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _run(module):
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value(module).run()
    return at


def test_portfolio_module_with_snapshot():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    src = [r for r in at.radio if r.label == "Data source"][0]
    src.set_value("Offline snapshot (to 2026-09-30)").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "VaR" in text and "2026-09-30" in text


def test_retirement_module():
    at = _run("Retirement plan")
    assert not at.exception
    assert "34.3%" in " ".join(m.value for m in at.markdown)


def test_option_module():
    at = _run("Option pricing")
    assert not at.exception
    assert "10.4506" in " ".join(m.value for m in at.markdown)
