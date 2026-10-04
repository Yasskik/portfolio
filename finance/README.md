# 📊 Finance Projects

[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Excel](https://img.shields.io/badge/Excel-financial%20modelling-217346?logo=microsoftexcel&logoColor=white)](dcf-valuation-model/examples/AAPL_DCF.xlsx)
[![Streamlit](https://img.shields.io/badge/Streamlit-apps-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

> Part of [Yamen Agha's portfolio](../README.md)

Valuation and financial-analysis work that puts corporate-finance theory (UniGe / UBS Investment Management specialization) into practice with Python and Excel.

## Shared design system

All five apps share one design system, so they look like a family: a light, editorial style with Source Serif 4 headings and Inter with tabular figures, hairline cards, consistent red / green for negative / positive values, accounting-style tables and a common Plotly template (interactive hover, zoom and toggleable legends). The master copy is [`_shared/ui_theme.py`](_shared/README.md). Each project vendors a copy next to its `app.py`, so it still runs on its own when cloned.

## Projects

| Project | Live demo | Description | Tools | Highlights |
|---|---|---|---|---|
| [DCF Valuation Model](dcf-valuation-model/README.md) | [Open app](https://yamen-dcf-valuation.streamlit.app/) | Interactive discounted-cash-flow valuation of any listed company: pulls statements from Yahoo Finance, builds a 5-year FCFF forecast, WACC via CAPM, Gordon-growth and exit-multiple terminal values, EV-to-equity bridge and sensitivity tables | Python, Streamlit, pandas, Plotly, openpyxl, pytest | Excel export where **every calculated cell is a live formula** (246 formulas, cross-checked against Python); 32 automated tests; beginner's [guide](dcf-valuation-model/GUIDE.md) |
| [Financial Statement Analyzer](financial-statement-analyzer/README.md) | [Open app](https://yamen-statement-analyzer.streamlit.app/) | Ratio analysis of any listed company (or your own uploaded statements): 34 liquidity, profitability, solvency, efficiency, cash-flow and growth ratios, 3- and 5-step DuPont, Altman Z / Z'', Piotroski F-score, common-size and trend analysis, peer comparison and a PDF health report | Python, Streamlit, pandas, Plotly, openpyxl, reportlab, pytest | Excel export where **every ratio and score is a live formula** on the statement sheets (0 mismatches vs Python across 10 companies, LibreOffice-recalculated); 61 automated tests; beginner's [guide](financial-statement-analyzer/GUIDE.md) |
| [Loan & Investment Calculator](loan-investment-calculator/README.md) | [Open app](https://yamen-loan-calculator.streamlit.app/) | Time-value-of-money toolkit: amortization schedules (annuity, equal principal, interest-only/balloon) with any payment frequency and extra payments, investment growth with contributions, inflation, tax and goal seek, plus NPV, IRR, APR→EAR and a two-loan comparison | Python, Streamlit, pandas, Plotly, openpyxl, pytest | Excel export where **every schedule cell is a live formula** (0 mismatches vs Python across 42,000+ cells in 15 scenarios, LibreOffice-recalculated); TVM functions checked against Excel's PMT/IPMT/PPMT/FV/RATE/NPER/NPV/IRR; 107 automated tests; beginner's [guide](loan-investment-calculator/GUIDE.md) |
| [Monte Carlo Simulation Toolkit](monte-carlo-simulator/README.md) | [Open app](https://yamen-monte-carlo.streamlit.app/) | Monte Carlo risk toolkit: portfolio VaR/CVaR and max drawdown from correlated GBM (Cholesky) or historical bootstrap on real prices, retirement probability of success with a safe-withdrawal-rate sweep, and European option pricing with antithetic variates vs Black-Scholes and the Greeks | Python, Streamlit, NumPy, SciPy, yfinance, Plotly, openpyxl, pytest | Excel export with **live-formula statistics** (`PERCENTILE.INC`, `AVERAGEIF`, `STDEV.S`) over every simulation and a live Black-Scholes sheet (0 mismatches vs Python across 47,000+ values, LibreOffice-recalculated); 64 automated tests; beginner's [guide](monte-carlo-simulator/GUIDE.md) |
| [Three-Statement Financial Model](three-statement-model/README.md) | [Open app](https://yamen-three-statement.streamlit.app/) | Integrated income statement, balance sheet and cash-flow statement: 3 historical years from Yahoo Finance (offline snapshot or live) or an upload template, 5-year driver-based forecast with DSO/DIO/DPO working capital, PP&E and debt schedules, an automatic revolver with minimum cash and a cap, interest on average balances solved by iteration with a circuit breaker, and base/bull/bear scenarios | Python, Streamlit, pandas, Plotly, openpyxl, yfinance, pytest | **Balances with no plug** for AAPL, MSFT, KO, T and F in every scenario; Excel export where every forecast cell is a **live formula** with iterative calculation (0 mismatches vs Python across 24,378 values in 33 workbooks, LibreOffice-recalculated, balance check 0); 103 automated tests; beginner's [guide](three-statement-model/GUIDE.md) |
| [Desktop Financial Ticker](../arduino/desktop-ticker/README.md) *(hardware)* | — | Arduino gadget showing live gold, silver, EUR/USD, Bitcoin, NVIDIA and Apple prices, fetched on demand by a Python bridge | Arduino C++, Python, yfinance, pyserial | Finance meets electronics: caching, back-off and a serial protocol; listed under Arduino |

| DCF Valuation Model | Financial Statement Analyzer |
|---|---|
| <a href="dcf-valuation-model/README.md"><img src="dcf-valuation-model/docs/screenshots/01_summary.png" width="300" alt="DCF Valuation Model – summary screen"></a> | <a href="financial-statement-analyzer/README.md"><img src="financial-statement-analyzer/docs/screenshots/01_dashboard.png" width="300" alt="Financial Statement Analyzer – dashboard"></a> |

| Loan & Investment Calculator | Monte Carlo Simulation Toolkit |
|---|---|
| <a href="loan-investment-calculator/README.md"><img src="loan-investment-calculator/docs/screenshots/01_loan_summary.png" width="300" alt="Loan & Investment Calculator – loan summary"></a> | <a href="monte-carlo-simulator/README.md"><img src="monte-carlo-simulator/docs/screenshots/01_portfolio_fan.png" width="300" alt="Monte Carlo Simulation Toolkit – portfolio fan chart"></a> |

| Three-Statement Financial Model | |
|---|---|
| <a href="three-statement-model/README.md"><img src="three-statement-model/docs/screenshots/01_dashboard.png" width="300" alt="Three-Statement Financial Model – dashboard"></a> | |

## Quick start (DCF model)

```bash
git clone https://github.com/Yasskik/portfolio.git
cd portfolio/finance/dcf-valuation-model
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py        # http://localhost:8501
pytest -q                   # 32 tests, no internet needed
```

No time to install? Open the ready-made model [`examples/AAPL_DCF.xlsx`](dcf-valuation-model/examples/AAPL_DCF.xlsx) in Excel and change the blue inputs on the *Assumptions* sheet.

## Quick start (Financial Statement Analyzer)

```bash
git clone https://github.com/Yasskik/portfolio.git
cd portfolio/finance/financial-statement-analyzer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py        # http://localhost:8501
pytest -q                   # 61 tests, no internet needed
```

No time to install? Open [`examples/AAPL_analysis.xlsx`](financial-statement-analyzer/examples/AAPL_analysis.xlsx) (every ratio is a formula you can trace) or read the sample [health report](financial-statement-analyzer/examples/AAPL_health_report.pdf).

## Quick start (Loan & Investment Calculator)

```bash
git clone https://github.com/Yasskik/portfolio.git
cd portfolio/finance/loan-investment-calculator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py        # http://localhost:8501
pytest -q                   # 107 tests (LibreOffice checks are skipped if it isn't installed)
```

No time to install? Open [`examples/Mortgage_25yr_300k.xlsx`](loan-investment-calculator/examples/Mortgage_25yr_300k.xlsx) or [`examples/Investment_Plan_30yr.xlsx`](loan-investment-calculator/examples/Investment_Plan_30yr.xlsx) and change the blue inputs; every schedule row recalculates.

## Quick start (Monte Carlo Simulation Toolkit)

```bash
git clone https://github.com/Yasskik/portfolio.git
cd portfolio/finance/monte-carlo-simulator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py        # http://localhost:8501
pytest -q                   # 64 tests (LibreOffice checks are skipped if it isn't installed)
```

No time to install? Open [`examples/Option_BS_vs_MC.xlsx`](monte-carlo-simulator/examples/Option_BS_vs_MC.xlsx) (Black-Scholes and the Greeks as live formulas) or [`examples/Portfolio_60_40_SPY_AGG.xlsx`](monte-carlo-simulator/examples/Portfolio_60_40_SPY_AGG.xlsx) (VaR and CVaR as formulas over 10,000 simulations).

## Quick start (Three-Statement Financial Model)

```bash
git clone https://github.com/Yasskik/portfolio.git
cd portfolio/finance/three-statement-model
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py        # http://localhost:8501
pytest -q                   # 103 tests (LibreOffice checks are skipped if it isn't installed)
```

No time to install? Open [`examples/AAPL_base_case.xlsx`](three-statement-model/examples/AAPL_base_case.xlsx) (change a driver on *Assumptions*; the *Checks* sheet stays at 0) or [`examples/AAPL_revolver_stress.xlsx`](three-statement-model/examples/AAPL_revolver_stress.xlsx) (the revolver draws and is repaid).

## Skills demonstrated

- Corporate valuation: FCFF, WACC / CAPM, terminal value (Gordon growth, exit multiple), EV → equity bridge, sensitivity analysis
- Financial-statement analysis from reported data (income statement, balance sheet, cash-flow statement), including sign conventions
- Ratio analysis with stated conventions (ending vs average balances, COGS-based DIO/DPO, 365-day year), DuPont decomposition, Altman Z / Z'' and Piotroski F-score screens
- Time value of money: PMT/IPMT/PPMT/FV/PV/RATE/NPER, APR vs EAR and equivalent periodic rates, amortization (annuity, equal principal, balloon), extra payments, annuity due vs ordinary annuity, real returns, NPV (t = 0 convention) and IRR edge cases
- Risk and simulation: Monte Carlo methods, log returns and GBM (Itô drift correction), Cholesky-correlated simulation, historical and block bootstrap, VaR / CVaR (Monte Carlo, parametric, historical), max drawdown, retirement success probability and the 4% rule, Black-Scholes, the Greeks and variance reduction
- Three-statement modelling: linked IS / BS / CFS (indirect method), working-capital days, PP&E and debt roll-forwards, revolver with minimum cash, interest circularity (iteration, circuit breaker), balance-sheet debugging without plugs, honest mapping of standardised data (operating income vs EBIT, NCI, cash vs short-term investments)
- Excel financial modelling with an auditable assumptions → calculations → outputs layout
- Python for finance: pandas, data APIs, testing and documentation

*Educational projects; nothing here is investment advice.*
