"""Run the Streamlit app headlessly and check it renders without exceptions."""
import html
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _run(**changes):
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    for key, val in changes.items():
        widget = next(w for w in list(at.number_input) + list(at.selectbox) if w.key == key)
        widget.set_value(val)
    if changes:
        at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _text(at):
    """All markdown on the page; KPI cards are HTML, so entities (&amp;, &#36;) are decoded first."""
    return html.unescape(" ".join(m.value for m in at.markdown))


def test_default_render():
    at = _run()
    text = _text(at)
    assert "Loan & Investment Calculator" in text


def test_reference_loan_values_shown():
    at = _run(l_principal=200_000.0, l_rate=6.0, l_term=30.0, l_extra_recurring=200.0)
    text = _text(at)
    assert "$1,199.10" in text and "$151,876.18" in text and "9 years, 0 months" in text


def test_other_loan_types_and_frequencies():
    _run(l_type="Interest-Only then Balloon", l_freq="Bi-Weekly (26/yr)")
    _run(l_type="Equal Principal Amortization", l_comp="Semi-annual (Canadian mortgages)", l_rate=0.0)
    _run(l_balloon=50_000.0)


def test_investment_variants():
    _run(inv_comp="Continuous Compounding", inv_freq="Weekly (52/yr)", inv_timing="Beginning of Period (Annuity Due)")
    _run(inv_return=-5.0, inv_tax=20.0)
