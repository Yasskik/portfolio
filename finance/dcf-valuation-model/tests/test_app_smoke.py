"""Smoke test: the Streamlit app runs end-to-end without exceptions (no network needed)."""
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def offline_yfinance(monkeypatch):
    fake = types.ModuleType("yfinance")

    class Boom:
        def __init__(self, *_a, **_k):
            raise ConnectionError("offline test")

    fake.Ticker = Boom
    monkeypatch.setitem(sys.modules, "yfinance", fake)


def test_app_runs_with_snapshot_data(offline_yfinance):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    assert any("Apple" in m.value for m in at.markdown)
    # switch ticker
    at.sidebar.text_input[0].set_value("KO").run()
    assert not at.exception, at.exception


def test_app_shows_error_for_unknown_ticker(offline_yfinance):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["ticker"] = "ZZZZNOTREAL"
    at.run()
    assert not at.exception
    assert at.error and "ZZZZNOTREAL" in at.error[0].value
