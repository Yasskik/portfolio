"""Streamlit smoke tests (AppTest, no browser).

The dashboard shows its key figures as HTML KPI cards (ui_theme.kpis) instead of st.metric, so the
tests read label / value / footer text back out of those cards.
"""
import html
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

_CARD = re.compile(r'<div class="ya-kpi-label"[^>]*>(.*?)</div><div class="ya-kpi-value[^"]*"[^>]*>(.*?)</div>'
                   r'<div class="ya-kpi-foot">(.*?)</div>', re.S)


def run(**set_):
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60)
    at.run()
    return at


def cards(at):
    """[(label, value, footer text)] for every KPI card on the page."""
    out = []
    for md in at.markdown:
        for lab, val, foot in _CARD.findall(md.value):
            text = html.unescape(re.sub(r"<[^>]+>", " ", foot))
            out.append((html.unescape(lab), html.unescape(val), " ".join(text.split())))
    return out


def card_values(at, prefix):
    return [v for lab, v, _ in cards(at) if lab.startswith(prefix)]


def test_app_runs_offline_snapshot():
    at = run()
    assert not at.exception
    assert any("balances in every forecast year" in m.value for m in at.markdown)
    labels = [lab for lab, _, _ in cards(at)]
    assert "Revenue 2030E" in labels and "Balance check 2030E" in labels
    assert [v for lab, v, _ in cards(at) if lab == "Balance check 2030E"] == ["0.000000"]


@pytest.mark.parametrize("ticker", ["MSFT", "KO", "T", "F"])
@pytest.mark.parametrize("scenario", ["Bull", "Bear"])
def test_app_each_ticker_and_scenario(ticker, scenario):
    at = run()
    at.sidebar.selectbox[0].select(ticker).run()
    at.sidebar.radio[1].set_value(scenario).run()
    assert not at.exception
    assert card_values(at, "Balance check") == ["0.000000"]


def test_app_sample_company_and_stress_toggle():
    at = run()
    at.sidebar.radio[0].set_value("Sample company").run()
    assert not at.exception
    at = run()
    at.sidebar.toggle[1].set_value(True).run()            # revolver stress test
    assert not at.exception
    rev = [(v, foot) for lab, v, foot in cards(at) if lab.startswith("Revolver")]
    assert rev and any("peak" in foot for _, foot in rev)


def test_driver_edit_takes_effect_in_same_run():
    at = run()
    before = card_values(at, "Revenue")[0]
    at.session_state["editor1"] = {"edited_rows": {0: {"2026E": 20.0}}, "added_rows": [], "deleted_rows": []}
    at.run()
    after = card_values(at, "Revenue")[0]
    assert not at.exception and after != before
