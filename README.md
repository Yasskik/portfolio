<h1 align="center">Yamen Agha · Projects Portfolio</h1>

<p align="center">
  <b>Accounting student · DSE-trained broker candidate · Financial modelling · Python &amp; Arduino builder</b><br>
  Aleppo, Syria
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Finance-DCF%20%7C%203--Statement%20%7C%20Ratios%20%7C%20TVM%20%7C%20Risk-0b6e4f" alt="Finance">
  <img src="https://img.shields.io/badge/Excel-financial%20modelling-217346?logo=microsoftexcel&logoColor=white" alt="Excel">
  <img src="https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Power%20BI-data%20analytics-F2C811?logo=powerbi&logoColor=black" alt="Power BI">
  <img src="https://img.shields.io/badge/Arduino-Uno-00979D?logo=arduino&logoColor=white" alt="Arduino">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
</p>

---

## 👋 About me

I'm a third-year **Economics (Accounting)** student at **Aleppo University**, looking for internships and traineeships in **finance, accounting, auditing and brokerage**.

- 🏛️ **Damascus Securities Exchange (DSE)** – Financial Broker Training Program (Sep 2026): market rules, trading mechanics, order execution and surveillance; passed the final practical exam with zero execution errors.
- 🎓 **University of Geneva & UBS** – Investment Management Specialization (2026, scholarship): fundamental analysis, cost of capital, a three-statement model and a DCF model in Excel.
- 📊 **Data Analytics Mini-Diploma** (Syrian Youth Assembly, courses by IBM, Johns Hopkins, Microsoft on Coursera) – in progress: Excel, Power BI, IBM Cognos, data cleaning and storytelling.
- 🧾 Hands-on with regional accounting software (Al-Ameen, Al-Bazar, Al-Muhtaseb …): full accounting cycle, trial balance and financial statements.

This repository collects my **finance projects** and my **Arduino electronics projects**. Every project has its own README with a full explanation.

## 🛠️ Skills

| Area | Skills |
|---|---|
| Finance & accounting | DCF valuation, WACC / CAPM, three-statement modelling, financial-statement analysis, time value of money (loans, amortization, NPV / IRR), risk analysis (Monte Carlo simulation, VaR / CVaR, Black-Scholes), sensitivity analysis, brokerage operations (DSE) |
| Tools | Excel (advanced, live-formula models), Power BI, IBM Cognos, regional accounting ERPs |
| Programming | Python (pandas, NumPy, Streamlit, openpyxl, pytest), SQL, Bash / Linux, Arduino C++ |
| Electronics | Arduino Uno, sensors, stepper motors, RFID, LCD + keypad interfaces, serial communication |
| Languages | Arabic (native), English (C1), Russian (A2) |

## 📁 Projects

### Finance

| Project | Live demo | Description | Tech |
|---|---|---|---|
| [**DCF Valuation Model**](finance/dcf-valuation-model/README.md) | [Open app](https://yamen-dcf-valuation.streamlit.app/) | Interactive DCF valuation of any listed company: Yahoo Finance data, 5-year FCFF forecast, WACC, two terminal-value methods, sensitivity tables, and an **Excel export with live formulas** | Python · Streamlit · Excel · pytest |
| [**Financial Statement Analyzer**](finance/financial-statement-analyzer/README.md) | [Open app](https://yamen-statement-analyzer.streamlit.app/) | Ratio analysis of any listed company: 34 ratios, 3- and 5-step DuPont, Altman Z / Z'', Piotroski F-score, common-size and trend analysis, peer comparison, PDF health report, and an **Excel export where every ratio is a live formula** | Python · Streamlit · Excel · pytest |
| [**Loan & Investment Calculator**](finance/loan-investment-calculator/README.md) | [Open app](https://yamen-loan-calculator.streamlit.app/) | Amortization schedules for three loan types with extra payments, investment growth with contributions, inflation, tax and goal seek, plus NPV / IRR and APR → EAR tools, and an **Excel export where every schedule cell is a live formula** (verified to the cent in LibreOffice) | Python · Streamlit · Excel · pytest |
| [**Monte Carlo Simulation Toolkit**](finance/monte-carlo-simulator/README.md) | [Open app](https://yamen-monte-carlo.streamlit.app/) | Monte Carlo risk toolkit: portfolio VaR / CVaR and drawdowns from correlated GBM or historical bootstrap on real prices, retirement probability of success and safe withdrawal rate, and option pricing vs Black-Scholes with the Greeks, plus an **Excel export with live-formula statistics and a live Black-Scholes sheet** (verified in LibreOffice) | Python · Streamlit · NumPy · Excel · pytest |
| [**Three-Statement Financial Model**](finance/three-statement-model/README.md) | [Open app](https://yamen-three-statement.streamlit.app/) | Integrated three-statement model: 3 historical years from Yahoo Finance or a template, 5-year driver-based forecast, working-capital, PP&E and debt schedules, an automatic revolver, interest circularity solved by iteration, scenarios, a balance sheet that balances with no plug, and an **Excel export where every forecast cell is a live formula** (verified in LibreOffice, balance check 0) | Python · Streamlit · Excel · pytest |

→ [All finance projects](finance/README.md)

### Arduino

| Project | Description | Key parts |
|---|---|---|
| [**Desktop Financial Ticker**](arduino/desktop-ticker/README.md) | LCD + keypad gadget showing live gold, silver, EUR/USD, BTC, NVDA and AAPL prices via a Python bridge | 1602A LCD, 4x4 keypad, Python |
| [**RFID Access Indicator**](arduino/rfid-access-rgb/README.md) | Learns an authorised RFID tag (saved in EEPROM): green + beep for it, red for any other tag | RC522, RGB LED, buzzer |
| [**Joystick Stepper Turntable**](arduino/joystick-stepper-turntable/README.md) | Joystick-controlled stepper with proportional, ramped speed and a lock button | 28BYJ-48, ULN2003, joystick |
| [**Stepper Motor Test**](arduino/stepper-motor-test/README.md) | Minimal sketch that checks a stepper motor and driver: one turn forward, one back | 28BYJ-48, ULN2003 |
| [**Clap Light**](arduino/clap-light/README.md) | Clap to switch an RGB light on/off, double-clap to change colour | sound sensor, RGB LED |
| [**Fire Alarm**](arduino/fire-alarm/README.md) | Self-calibrating IR flame detector with flashing LED and siren | IR flame diode, buzzer, RGB LED |
| [**Water Level Indicator**](arduino/water-level-indicator/README.md) | Traffic-light display of water level, with corrosion-reducing sensor power switching | water sensor, RGB LED |

→ [All Arduino projects, wiring diagrams and build status](arduino/README.md)

## 🗂️ Repository structure

```text
portfolio/
├── finance/
│   ├── README.md
│   ├── dcf-valuation-model/      # Python + Streamlit + Excel DCF model
│   ├── financial-statement-analyzer/  # Ratios, DuPont, Altman Z, Piotroski + Excel export
│   ├── loan-investment-calculator/    # Amortization, investment growth, NPV/IRR + Excel export
│   ├── monte-carlo-simulator/         # Portfolio VaR/CVaR, retirement success, option pricing + Excel export
│   └── three-statement-model/         # Linked IS/BS/CFS forecast, revolver, circularity + Excel export
├── arduino/
│   ├── README.md
│   ├── docs/photos/              # component photos
│   ├── desktop-ticker/
│   ├── rfid-access-rgb/
│   ├── joystick-stepper-turntable/
│   ├── stepper-motor-test/
│   ├── clap-light/
│   ├── fire-alarm/
│   └── water-level-indicator/
├── tools/wiring_diagrams.py      # generates the Arduino wiring diagrams
├── LICENSE
└── README.md
```

## 📬 Contact

- LinkedIn: **TODO – add LinkedIn profile URL**
- Email: **TODO – add professional email**
- GitHub: [@Yasskik](https://github.com/Yasskik)

---

<sub>All projects are educational. Nothing in this repository is investment advice. Code is released under the [MIT License](LICENSE).</sub>
