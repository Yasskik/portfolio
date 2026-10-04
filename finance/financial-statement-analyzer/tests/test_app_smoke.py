"""Run the Streamlit app headlessly (offline snapshots) and make sure no tab raises."""
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


@pytest.mark.parametrize("tickers", ["AAPL, MSFT", "KO, PEP", "JPM", "GOOGL, V"])
def test_app_runs_without_exceptions(tickers, monkeypatch):
    monkeypatch.setenv("FSA_OFFLINE", "1")
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.text_input[0].set_value(tickers).run()
    assert not at.exception, at.exception
    # Every Altman / Piotroski KPI renders as a number or "n/a", never a Python error
    html = " ".join(m.value for m in at.markdown)
    assert "Altman" in html and "Piotroski" in html


def test_app_upload_mode_has_templates(monkeypatch):
    monkeypatch.setenv("FSA_OFFLINE", "1")
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value("Upload Custom Financials (CSV / Excel)").run()
    assert not at.exception, at.exception
