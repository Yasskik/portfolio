# Your DCF Project: A Beginner's Guide

*Written for Yamen Agha. Read it slowly, with the app and the Excel file open next to you.*

This guide starts from zero. You don't need to know anything about DCF models yet. By the end you should be able to:

1. Explain what a DCF is and why it works, in simple words.
2. Use the app and the Excel file, and explain every input and output.
3. Rebuild a small DCF in Excel yourself, from a blank sheet.
4. Present the project to an employer and answer interview questions.
5. Honestly say "I understand this model and I improved it myself."

**Contents**

1. What a DCF is, from zero
2. The key ideas in plain words
3. How to use the app
4. How to use the Excel file, and building your own DCF in Excel
5. Presenting the project to an employer
6. Interview questions and sample answers
7. Your study plan for the next 7 days

---

## 1. What a DCF is, from zero

### The core idea: money today is worth more than money later

Would you rather have $100 today or $100 in one year? Today, of course. You could put today's $100 in a bank or an investment and have more than $100 a year from now. Prices also rise over time, and a promise to pay you later might not be kept.

So **money in the future is worth less than money today.** To compare them, we *discount* future money back to today:

```
Present value = Future cash / (1 + r) ^ years
```

`r` is the return you could earn somewhere else with similar risk. If `r` = 10%, then $110 received in one year is worth 110 / 1.10 = **$100 today**.

### A DCF applies that idea to a whole company

A company is worth the cash it will produce for its investors in the future, with each amount discounted back to today. That's the whole idea. **DCF = Discounted Cash Flow.**

**Intuitive example.** A friend offers to sell you a small shop. It produces about $1,000 of free cash every year after all costs and reinvestment, and it should keep doing that for a long time. What is it worth to you? Not "$1,000 × forever", because money later is worth less. A DCF answers: "If I need a 10% return, how much would I pay today for all those future $1,000s?" (For a flat $1,000 a year forever, the answer is 1,000 / 0.10 = **$10,000**.)

### A tiny worked example

A small company is expected to produce free cash flow of **100, 110 and 120** over the next three years. After that, the cash flow grows **2% a year forever**. Investors need a **10%** return. The company has **300 of debt**, **100 of cash** and **100 shares**. The market price is **$10 per share**.

**Step 1. Discount each forecast year.**

| Year | Cash flow | Discount factor = 1/1.10^t | Present value |
|---|---|---|---|
| 1 | 100 | 0.9091 | 90.91 |
| 2 | 110 | 0.8264 | 90.91 |
| 3 | 120 | 0.7513 | 90.16 |
| **Sum** | | | **271.98** |

**Step 2. Terminal value**, which covers every year after Year 3 in one number:

```
TV at end of Year 3 = 120 × 1.02 / (0.10 − 0.02) = 122.4 / 0.08 = 1,530
PV of TV            = 1,530 / 1.10^3 = 1,149.51
```

**Step 3. Enterprise value** (the value of the whole business) = 271.98 + 1,149.51 = **1,421.49**

**Step 4. Equity value** (what belongs to shareholders) = EV − debt + cash = 1,421.49 − 300 + 100 = **1,221.49**

**Step 5. Value per share** = 1,221.49 / 100 = **$12.21**

**Step 6. Compare with the market.** The price is $10, so the model says the share is worth about **22% more** than its price (12.21 / 10 − 1 = 22.1%).

Your project does exactly these six steps. The only differences are 5 forecast years instead of 3, real company data, and more detail in how the cash flow is calculated.

---

## 2. The key ideas in plain words

### Free cash flow (FCFF, "free cash flow to the firm")

This is the cash the business produces from its operations after paying taxes and after reinvesting what it needs to keep growing. It is available to **everyone who funded the company, lenders and shareholders together**. That is why it is also called "unlevered" free cash flow: it is measured *before* interest payments.

```
FCFF = EBIT × (1 − tax rate) + D&A − Capex − Increase in net working capital
```

- **EBIT** is operating profit (earnings before interest and taxes).
- **EBIT × (1 − tax)** is called **NOPAT**, the operating profit after tax.
- **D&A (depreciation & amortization)** is an accounting expense that isn't a cash payment, so we add it back.
- **Capex (capital expenditure)** is cash spent on long-term assets like factories, machines and data centres. It is real cash out, so we subtract it.
- **Net working capital (NWC)** is roughly receivables + inventory − payables. When NWC *increases*, cash gets tied up in the business, so we subtract the increase.

*Accounting link:* this is close to "cash flow from operations minus capex" from your cash-flow statement course. The difference is that FCFF ignores interest, because interest belongs to the lenders, who are also part of "the firm".

### Projections

We forecast the next 5 years. In this model, each line is driven by a simple assumption:

- Revenue grows by a **growth rate** each year. In the app, the growth rate fades a little every year, because fast growth usually slows down.
- EBIT = revenue × **EBIT margin**.
- D&A, capex and NWC are each a **percentage of revenue**.

The forecast is only as good as these assumptions. Good analysts spend most of their time justifying them, not typing formulas.

### WACC (weighted average cost of capital)

This is the discount rate: the return that the company's investors require, on average. A company is funded by shareholders (equity) and lenders (debt), who expect different returns. WACC is the weighted average of the two:

```
WACC = (E / (E + D)) × Cost of equity  +  (D / (E + D)) × Cost of debt × (1 − tax rate)
```

- **E** is the *market* value of equity, which is the market capitalisation (share price × shares). We use market values because they reflect what investors could get if they sold today.
- **D** is debt.
- The cost of debt is multiplied by **(1 − tax rate)** because interest is tax-deductible. This saving is called the **tax shield**.

### CAPM (Capital Asset Pricing Model)

Shareholders don't send the company a bill, so we have to estimate their required return. CAPM does this:

```
Cost of equity = Risk-free rate + Beta × Equity risk premium
```

- **Risk-free rate** is what you earn with (almost) no risk. For US companies it is usually the 10-year US Treasury yield.
- **Equity risk premium (ERP)** is the extra return investors demand for owning stocks instead of government bonds. It is commonly taken as around 4-6%.
- **Beta** is explained next.

### Beta

Beta measures how much a stock tends to move when the whole market moves.

- **Beta = 1**: the stock moves about as much as the market.
- **Beta > 1**, e.g. 1.5: it tends to move more. It is riskier for a diversified investor, so it has a higher cost of equity.
- **Beta < 1**, e.g. 0.4 for Coca-Cola: it moves less, so it has a lower cost of equity.

Beta is estimated from past prices, so it is noisy. Professionals often adjust it, or use the average beta of similar companies.

### Terminal value (TV)

A company doesn't stop after Year 5, so we need a single number for all the years after that. **This is usually 60-80% of the total value**, which is why it matters so much. There are two methods.

**1. Gordon Growth (perpetual growth) method.** This assumes cash flow grows at a steady rate **g** forever:

```
TV = FCFF in Year 5 × (1 + g) / (WACC − g)
```

- `g` must be **lower than WACC**, otherwise the formula breaks. When WACC ≤ g, the app shows "n/a".
- `g` should be modest, usually 2-3%. No company can grow faster than the whole economy forever.

**2. Exit multiple method.** This assumes that at the end of Year 5 the business could be sold at a typical market price, expressed as a multiple of its EBITDA:

```
TV = EBITDA in Year 5 × EV/EBITDA multiple      (EBITDA = EBIT + D&A)
```

Both are values **at the end of Year 5**, so both are discounted 5 years: `PV of TV = TV / (1 + WACC)^5`.

A good habit is to **cross-check** the two. The app shows the exit multiple implied by the Gordon value, and the growth rate implied by the exit multiple value. If a 12x multiple implies 4% growth forever, that is aggressive.

### Enterprise value vs. equity value

**House analogy.** A house is worth $200,000 (that is the *enterprise value*). You still owe the bank $150,000 on the mortgage, and you have $10,000 in your drawer. Your share of the house, the *equity value*, is 200,000 − 150,000 + 10,000 = **$60,000**.

- **Enterprise value (EV)** is the value of the whole business, for all investors. It equals PV of forecast cash flows + PV of terminal value.
- **Equity value** is what belongs to shareholders: EV − debt + cash.

### Net debt

```
Net debt = Total debt − Cash
```

Equity value = EV − Net debt. If a company has more cash than debt, net debt is negative, and that *increases* equity value.

### Implied share price

```
Implied value per share = Equity value / Number of shares
```

This is the model's estimate of what one share is worth, given your assumptions.

### Upside and margin of safety

- **Upside (or downside)** = implied value / market price − 1. It answers: "How far is the model's value from the price?"
- **Margin of safety** is an idea from Benjamin Graham: only buy when the price is well below your estimate of value, so you are protected if you are wrong. It is often measured as (value − price) / value. In the tiny example the value is $12.21 and the price is $10, so the margin of safety is about 18% while the upside is 22%. The two formulas measure the same gap from different sides.

### Sensitivity analysis

Because small changes in WACC or g move the answer a lot, we show a **table of values for many combinations**. Rows are different WACCs and columns are different g values (or exit multiples). This shows the *range* of reasonable values instead of pretending one number is exact. In an interview, saying "the value is between X and Y depending on WACC and growth" sounds much more professional than quoting one price.

### Main limitations of a DCF

- **Garbage in, garbage out.** The output is completely driven by your assumptions.
- **The terminal value dominates.** Most of the value depends on what happens after Year 5, which nobody knows.
- **It is very sensitive to WACC and g.** A 1% change can move the value by 20% or more.
- **It doesn't suit every company.** It is hard to use for **banks and insurers**, where debt is their raw material and not just financing (use dividend models or price-to-book instead). It is also hard for start-ups with negative cash flow and for very cyclical businesses.
- **Inputs are estimates.** Beta and the equity risk premium are estimated and debated, not facts.
- **The market may know something you don't.** When your DCF disagrees strongly with the market price, first ask *"What assumptions is the market making?"* before concluding the market is wrong.

---

## 3. How to use the app

### Starting it

```bash
cd dcf-valuation-model
source .venv/bin/activate        # Windows: .venv\Scripts\activate
streamlit run app.py
```

Your browser opens at `http://localhost:8501`.

### Step by step

1. **Choose a company.** Type a Yahoo Finance ticker (e.g. `AAPL`, `MSFT`, `KO`) or click a quick button. If Yahoo is unavailable, choose **Offline snapshot** (AAPL, MSFT, NVDA, GOOGL, AMZN, KO, TSLA). If the ticker doesn't exist, the app shows an error instead of inventing data.
2. **Read any yellow warnings.** They tell you when data was missing and what the app assumed instead.
3. **Check the defaults.** The sliders start from the company's own history, but you should question every one of them.
4. **Change assumptions** in the sidebar and watch the Valuation tab update.
5. **Look at the tabs**: Valuation → Forecast → Cost of capital → Sensitivity → Historicals → Methodology. Every chart is interactive: hover for values, drag to zoom, double-click to reset, click a legend item to hide it.
6. **Download the Excel model** with the button in the Export section at the bottom of the Valuation tab.

### The inputs (sidebar)

| Input | What it means | Default |
|---|---|---|
| Risk-free rate | Return on a "riskless" 10-year US government bond | Latest 10-year Treasury yield |
| Equity beta | How much the stock moves with the market | From Yahoo Finance |
| Equity risk premium | Extra return investors want for holding stocks | 5.0% |
| Pre-tax cost of debt | Interest rate the company pays on new borrowing | Risk-free rate + 1% |
| Tax rate (debt tax shield) | Used to make the cost of debt after-tax | Latest effective tax rate |
| Capital structure weights | Market values (E and D today) or your own target mix | Market values |
| Year-1 revenue growth | Sales growth next year | Historical revenue growth (CAGR) |
| Growth fade per year | How fast growth slows each year | 10% (e.g. 10% → 9% → 8.1% ...) |
| EBIT margin | Operating profit as % of revenue | Latest year |
| Tax rate on EBIT | Tax on operating profit | Latest effective tax rate |
| D&A % of revenue | Depreciation and amortization | Latest year |
| Capex % of revenue | Investment in long-term assets | Latest year |
| NWC % of revenue | Working capital needed per $ of sales | 5% |
| Perpetual growth (g) | Growth after Year 5, forever | 2.5% |
| Exit EV/EBITDA multiple | Price for the business at the end of Year 5 | 12.0x |
| Mid-year convention | Cash arrives through the year, so discount t − 0.5 years | On |

### The outputs

- **Summary**: implied value per share, upside or downside vs. the market price, enterprise value, WACC, a side-by-side table of the two methods (with cross-checks), a waterfall chart from EV to equity value, and the Excel download.
- **Forecast & FCFF**: the full 5-year table from revenue to present value, plus a chart.
- **WACC**: cost of equity, cost of debt, the weights and the final WACC, each shown with the actual numbers plugged into the formula.
- **Sensitivity**: value per share for 25 combinations of WACC and g, or WACC and exit multiple. The table is green where the value is above the current price and red where it is below.
- **Historicals**: what the company actually reported, plus ratios. Use this to justify your assumptions.
- **Methodology**: the formulas.

### Example output: Apple (AAPL, data as of 1 October 2026, app defaults)

| | Gordon Growth | Exit Multiple (12x) |
|---|---|---|
| Current price | $333.02 | $333.02 |
| WACC | 10.60% | 10.60% |
| Enterprise value | $1,369.2B | $1,585.2B |
| Implied value per share | **$92.31** | **$107.11** |
| vs. price | −72.3% | −67.8% |
| Terminal value % of EV | 66.7% | 71.3% |

**How to read this honestly.** The default assumptions are deliberately simple. Revenue growth starts at Apple's recent average of about **1.8%** a year, and the WACC is **10.6%**. That WACC is fairly high because the 10-year Treasury yield Yahoo reported was 5.29%. With these inputs, today's price looks very expensive. It does **not** mean "Apple is a sell". It means the market is pricing in much better assumptions. For example, keeping everything else the same with g = 3%, you would need a WACC of only about **5.2%** to get $333. Explaining this is a great interview answer (see Section 6).

---

## 4. The Excel file, and building your own DCF

### Using the exported file (`examples/AAPL_DCF.xlsx`)

1. Open the **Summary** sheet. It shows the key results and an "audit" row, which proves the Excel formulas give the same answer as the Python app (difference 0.00).
2. Go to **Assumptions**. **Blue text on a yellow background = inputs.** Everything else is a formula.
3. Change the perpetual growth rate (cell `B24`) from 2.50% to 3.00% and watch **DCF!B43** (value per share) and the **Sensitivity** grids update.
4. Click any black number on the **DCF** sheet and press **F2**, or use *Formulas → Trace Precedents*. You'll see where it comes from. Do this for every row once.
5. Set **mid-year convention** (`B26`) to 0 and see how the discount periods change from 0.5, 1.5, ... to 1, 2, ...

### Guided exercise: build a DCF from a blank sheet

Do this without looking at the project's file. It takes about 60-90 minutes the first time. Then do it again the next day, faster. **This is the skill employers want.**

**Step 1. Inputs.** Type the labels in column A and the numbers in column B. Colour the numbers blue.

| Cell | Label | Value |
|---|---|---|
| B3 | Base-year revenue (Year 0) | 1000 |
| B4 | EBIT margin | 20% |
| B5 | Tax rate | 25% |
| B6 | D&A % of revenue | 4% |
| B7 | Capex % of revenue | 5% |
| B8 | NWC % of revenue | 10% |
| B9 | WACC | 9% |
| B10 | Perpetual growth (g) | 2.5% |
| B11 | Debt | 300 |
| B12 | Cash | 100 |
| B13 | Shares | 100 |

**Step 2. The timeline.** In row 16, type `Year` in A16. Put **0** in B16 and **1, 2, 3, 4, 5** in C16:G16. In row 17 (growth), type **10%, 8%, 6%, 5%, 4%** in C17:G17.

**Step 3. The forecast.** Type these formulas in column C, then drag them right to column G. The `$` signs keep the reference fixed on the input cell.

| Row | Line | Formula in C (then drag to G) | Also |
|---|---|---|---|
| 18 | Revenue | `=B18*(1+C17)` | B18: `=B3` |
| 19 | EBIT | `=C18*$B$4` | |
| 20 | NOPAT | `=C19*(1-$B$5)` | |
| 21 | D&A | `=C18*$B$6` | |
| 22 | Capex | `=C18*$B$7` | |
| 23 | NWC | `=C18*$B$8` | B23: `=B18*$B$8` |
| 24 | Increase in NWC | `=C23-B23` | |
| 25 | **FCFF** | `=C20+C21-C22-C24` | |
| 26 | Discount factor | `=1/(1+$B$9)^C16` | |
| 27 | PV of FCFF | `=C25*C26` | |

**Step 4. Valuation.**

| Cell | Line | Formula |
|---|---|---|
| B29 | Sum of PV of FCFF | `=SUM(C27:G27)` |
| B30 | Terminal value | `=G25*(1+B10)/(B9-B10)` |
| B31 | PV of terminal value | `=B30/(1+B9)^G16` |
| B32 | Enterprise value | `=B29+B31` |
| B33 | Equity value | `=B32-B11+B12` |
| B34 | **Value per share** | `=B33/B13` |
| B35 | TV as % of EV | `=B31/B32` |

**Check your answers** (end-of-year discounting):

| Item | Year 1 | Year 5 |
|---|---|---|
| Revenue | 1,100.00 | 1,375.13 |
| EBIT | 220.00 | 275.03 |
| NOPAT | 165.00 | 206.27 |
| D&A | 44.00 | 55.01 |
| Capex | 55.00 | 68.76 |
| Increase in NWC | 10.00 | 5.29 |
| **FCFF** | **144.00** | **187.23** |
| Discount factor | 0.9174 | 0.6499 |
| PV of FCFF | 132.11 | 121.69 |

Sum of PV = **643.69** · TV = **2,952.47** · PV of TV = **1,918.90** · EV = **2,562.59** · Equity = **2,362.59** · **Value per share = $23.63** · TV = 74.9% of EV.

If your numbers differ, check the `$` signs and whether Year 0 NWC (B23) is filled in.

**Step 5. Extensions (do them one at a time).**

1. **Mid-year convention.** Add a row "discount period" = `C16-0.5` and use it in the discount factor. Keep the terminal value discounted by `G16` (5 years). Answer: sum of PV = 672.03, **value per share = $23.91**. *Why is it higher?* Cash arrives earlier, so it is discounted less.
2. **Exit multiple.** Year-5 EBITDA = `G19+G21` = 330.03. TV = EBITDA × 10 = 3,300.32. PV = 2,144.98. **Value per share = $25.89.**
3. **Sensitivity table.** Use *Data → What-If Analysis → Data Table*. Put WACC values (7%-11%) down a column and g values (1.5%-3.5%) across a row, with `=B34` in the corner. Set the row input cell to B10 and the column input cell to B9.
4. **Break it on purpose.** Set g = 9% (equal to WACC). What happens, and why?

---

## 5. Presenting the project to an employer

### 60-second pitch

> "I'm a third-year accounting student at Aleppo University, and I wanted to go beyond textbook valuation, so I built a DCF valuation tool. You type in a ticker, and it pulls the company's statements from Yahoo Finance. It forecasts five years of free cash flow to the firm, calculates WACC using CAPM, and values the company with both a Gordon growth and an exit-multiple terminal value. It then bridges from enterprise value to equity value and a value per share, and shows sensitivity tables because the result depends so much on WACC and growth. It also exports a fully linked Excel model. You can change any assumption in Excel and everything recalculates. For example, on Apple my base case gives about $92 against a $333 share price. What I find interesting is working out what the market must be assuming to justify $333. That question is what I'd like to do more of in an internship."

### 5-minute demo script

1. **(30 s) The problem.** "Valuing a company means estimating its future cash and discounting it. I built a tool that makes every step visible."
2. **(45 s) Load a company.** Type `KO`. Point out the Historicals tab: "These are the reported numbers. Notice I had to handle sign conventions. Yahoo reports capex and working capital as negative cash flows."
3. **(60 s) Assumptions.** "Growth starts from the historical CAGR and fades. Margins, capex and D&A come from the latest year. Coca-Cola's beta is only about 0.34, which gives a low cost of equity. I'd question that in a real analysis, for example by using peer betas."
4. **(60 s) Cost of capital tab.** Walk through Ke = Rf + β × ERP, the after-tax cost of debt, and the market-value weights.
5. **(60 s) Summary.** Explain EV → net debt → equity → per share, and compare the two methods and their cross-checks.
6. **(45 s) Change one thing live.** Move g from 2.5% to 3.0%, or the WACC inputs, and explain why the value moves.
7. **(30 s) Sensitivity + Excel.** Show the grid, open the Excel file, change a blue cell, and show it recalculating.
8. **(30 s) Limits.** "The terminal value is about two-thirds of EV, so the long-term assumptions matter most. I wouldn't use this model for a bank."

### CV bullet points

- Built a **DCF valuation tool** (Python, Streamlit) that pulls financial statements from Yahoo Finance, projects 5-year unlevered free cash flow, and values companies using a **CAPM-based WACC** with Gordon growth and exit-multiple terminal values.
- Designed a **fully linked Excel model export** (≈250 live formulas: assumptions → FCFF → WACC → EV-to-equity bridge → 5×5 sensitivity grids), verified to match the Python engine exactly.
- Added **data-quality checks and 32 automated tests**, covering capex and working-capital sign conventions, missing data, and the WACC ≤ g edge case. Documented the methodology and its limitations.

*(Only use a bullet if you can explain every word of it in an interview.)*

### LinkedIn post draft

> I built my first valuation project: an interactive **DCF model** 📈
>
> As an accounting student at Aleppo University, I wanted to understand how analysts value companies, so I built a tool that:
> • pulls real financial statements (Yahoo Finance)
> • forecasts 5 years of free cash flow
> • calculates WACC with CAPM
> • values the company with two terminal-value methods
> • exports a fully linked Excel model with sensitivity tables
>
> My biggest lesson: the answer depends much more on the **assumptions** than on the maths. On Apple, simple base-case assumptions give about $92 per share against a market price of about $333. So the real question is: what growth and discount rate is the market pricing in?
>
> I went through the model line by line, tested it, and rebuilt the DCF in Excel from scratch to make sure I understand every step.
>
> Code: [GitHub link] · Feedback from finance professionals very welcome!
>
> #Valuation #DCF #CorporateFinance #Accounting #Excel #Python

---

## 6. Interview questions and sample answers

**1. "Walk me through a DCF."**
"First I forecast the company's free cash flow to the firm for about five years. That's EBIT after tax, plus D&A, minus capex, minus the increase in working capital. Then I estimate WACC, the blended required return of shareholders and lenders, with the cost of equity from CAPM. I discount each year's cash flow at WACC and add a terminal value for the years after the forecast, using either perpetual growth or an exit multiple, also discounted to today. That gives enterprise value. I subtract net debt to get equity value, then divide by shares to get a value per share, which I compare with the market price. Finally I run sensitivities on WACC and growth."

**2. "Why use free cash flow and not net income?"**
"Net income includes non-cash items like depreciation and ignores cash spent on capex and working capital. Investors can only be paid from actual cash. FCFF is also measured before interest, so it belongs to all capital providers, which matches discounting at WACC."

**3. "How do you calculate WACC? Why market values?"**
"WACC = E/(E+D) × cost of equity + D/(E+D) × cost of debt × (1 − tax). I use market values because they show what investors' capital is worth today, which is their opportunity cost. Book equity is a historical accounting number. For debt, book value is often used as an approximation."

**4. "Why is the cost of debt after tax?"**
"Interest is tax-deductible, so each dollar of interest saves tax. The effective cost to the company is Kd × (1 − t). We don't subtract interest in FCFF, so the tax benefit is captured in WACC instead."

**5. "Gordon growth or exit multiple, which do you prefer?"**
"I use both and cross-check them. Gordon growth is based on fundamentals but is very sensitive to g and WACC. The exit multiple reflects the market but assumes today's multiples are right. My model shows the multiple implied by the Gordon value and the growth implied by the multiple. If a 12x multiple implies 4% growth forever, that tells me the multiple is too high."

**6. "What growth rate would you use for the terminal value, and why must it be below WACC?"**
"Usually 2-3%, around long-term inflation plus real growth, because no company can outgrow the economy forever. It must be below WACC because the formula divides by WACC − g. At or above WACC the value would be infinite or negative, which makes no economic sense."

**7. "What happens to the value if WACC goes up by 1%?"**
"It falls, and a lot. Future cash flows are discounted more and the terminal value shrinks from both sides, a bigger denominator and more discounting. In my Apple base case, WACC going from 10.6% to 11.6% moves the Gordon value from about $92 to about $82, roughly −11%."

**8. "What's the difference between enterprise value and equity value?"**
"Enterprise value is the value of the whole operating business for all investors. Equity value is what's left for shareholders after paying lenders. Equity = EV − debt + cash. It's like a house's value minus the mortgage."

**9. "What is the mid-year convention, and how do you treat the terminal value?"**
"Cash comes in throughout the year, not all on 31 December, so we discount Year 1 by half a year, Year 2 by 1.5 years, and so on. It slightly increases the value. In my model the terminal value is a value at the end of Year 5, so it's discounted five full years. Some practitioners discount a Gordon-growth TV by 4.5 years for consistency, and I'd mention that as an alternative."

**10. "Your model says Apple is worth $92 but it trades at $333. Is Apple overvalued?"**
"Not necessarily. It means my base-case assumptions are much more pessimistic than the market's. My defaults use Apple's recent revenue growth of about 1.8% and a 10.6% WACC. To justify $333 with those cash flows and 3% terminal growth, you'd need a WACC of about 5%. More realistically, the market expects higher growth, for example from services, and a lower required return. So I'd use the model as a reverse DCF: what do you have to believe to justify today's price?"

**11. "What were the hardest data problems?"**
"Sign conventions and missing data. Yahoo reports capex as a negative cash flow and 'Change in Working Capital' as a cash-flow number, where negative means working capital increased. You have to flip that before subtracting it in FCFF, otherwise the cash flow is wrong. I also made the app show a clear error for unknown tickers instead of quietly using made-up numbers, and I added tests for each of these cases."

**12. "How would you value a bank, for example on the Damascus Securities Exchange?"**
"I wouldn't use an FCFF DCF. For a bank, debt and deposits are the raw material of the business, not just financing, so 'free cash flow before debt' doesn't make sense. I'd use a dividend discount model or price-to-book compared with return on equity. In a high-inflation currency I'd also make sure the cash flows and the discount rate are in the same currency and both nominal, or both real."

**13. "Coca-Cola's beta is about 0.34. Would you use it?"**
"I'd be careful. A beta that low gives a cost of equity only a little above the risk-free rate. I'd look at an adjusted beta (for example 0.67 × raw beta + 0.33), or the average beta of peer companies, and see how the value changes."

### How to show you really know the project

1. **Understand every line of `dcf.py`.** Read it in this order: `calculate_wacc` → `project_cash_flows` → `calculate_terminal_value_ggm` / `calculate_terminal_value_exit_multiple` → `build_valuation_bridge` → `run_dcf` → `parse_yfinance_data`. For each function, write one sentence in your own words about what it does and why.
2. **Rebuild the DCF in Excel from scratch** (Section 4) until you can do it without notes.
3. **Be able to change an assumption live and explain the result.** For example: "If I raise Year-1 growth from 1.8% to 5%, Apple's value rises from about $92 to about $103. It's a smaller change than you might expect, because most of the value is in the terminal value, and g didn't change."
4. **Make your own improvements**, and commit them to Git yourself with clear messages. Your commit history then shows your own work.
5. **Know the limitations** (Section 2) and say them before the interviewer does.

### Small improvements you can make yourself (pick 2-3)

Each is roughly 5-40 lines of code. Try them in order of difficulty.

1. **Blume-adjusted beta toggle.** Add a checkbox. When it is on, use `0.67 × beta + 0.33`. *(Easy, in `app.py`.)*
2. **Country risk premium input.** Add an extra % to the cost of equity (Ke = Rf + β × ERP + CRP), which is useful for emerging markets. *(Easy: add a field to `WACCInputs` and use it in `calculate_wacc`, then add a test.)*
3. **Upside table.** Show the sensitivity grid as % upside instead of prices. The data already exists in `upside_table`. *(Easy.)*
4. **Bear / base / bull scenarios.** Add a selectbox that changes growth and margin by ± a few points. *(Medium.)*
5. **Reverse DCF.** Find the Year-1 growth (or WACC) that makes the value equal the market price, using a simple bisection loop. *(Medium, and a great interview story.)*
6. **Terminal-year normalisation.** In Year 5, set capex closer to D&A so the business isn't investing heavily forever. This matters a lot for companies like Microsoft that are spending heavily now. *(Medium.)*
7. **Excel: add an "Upside %" sensitivity grid** in `excel_export.py`. *(Medium.)*

After each change, run `pytest -q`. Add at least one test of your own, e.g. "with CRP = 2%, cost of equity rises by exactly 2%".

---

## 7. Your study plan for the next 7 days

About 1.5-2 hours a day.

| Day | Learn | Do |
|---|---|---|
| **1** | Time value of money and present value | Redo the tiny example (Section 1) on paper, then in Excel. Explain it out loud in 2 minutes. |
| **2** | FCFF, NOPAT, D&A, capex, NWC | Take Apple's or KO's numbers from the Historicals tab and calculate one year of FCFF by hand. Compare with the app. |
| **3** | WACC, CAPM, beta | Calculate the WACC for AAPL and KO by hand from the Cost of capital tab inputs. Why is KO's so much lower? |
| **4** | Terminal value (both methods), EV vs. equity | Build the full Excel exercise (Section 4, Steps 1-4) without looking. Check your answers. |
| **5** | Mid-year, exit multiple, sensitivity | Do the Section 4 extensions, including a Data Table. Read `dcf.py` from `calculate_wacc` to `run_dcf`. |
| **6** | Limitations, reverse DCF, banks | Make one improvement from Section 6 and commit it. Practise interview questions 1-8 aloud. |
| **7** | Presentation | Record yourself giving the 60-second pitch and the 5-minute demo. Practise questions 9-13. Post on LinkedIn. |

**Good free resources:** Aswath Damodaran's website and YouTube lectures (NYU Stern), especially his valuation classes and his data on equity risk premiums and industry betas. Also the free corporate-finance guides from CFI (Corporate Finance Institute) and Wall Street Prep.

---

*This project and guide are for education only. They are not investment advice.*
