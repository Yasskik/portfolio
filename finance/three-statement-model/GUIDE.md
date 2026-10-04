# Your Three-Statement Financial Model: A Beginner's Guide

*Written for Yamen Agha. Read it slowly, with the app and the Excel files open next to you.*

This guide starts from zero. Your accounting courses taught you how to **record** transactions and **prepare** the three financial statements. Financial modeling turns that around: you **forecast** the statements from a few assumptions ("drivers") and make sure they stay linked, so the balance sheet still balances in five years' time. A three-statement model is the most common test in finance interviews and the base of almost every valuation, credit and budgeting model. By the end you should be able to:

1. Explain the income statement, balance sheet and cash-flow statement, and exactly how they connect.
2. Trace a $10 depreciation increase and a sale on credit through all three statements.
3. Forecast every line from drivers, including working capital days, PP&E and debt.
4. Explain the revolver, the circular reference it creates and how the model solves it.
5. Debug a balance sheet that does not balance.
6. Build a small linked three-statement model in Excel from an empty sheet.
7. Present the project to an employer, answer interview questions, and honestly say "I understand this and I improved it myself."

Every number in this guide was produced by the app's engine (`model.py`) or by the exercise workbook. Company figures use the offline Yahoo Finance snapshot downloaded on 1 October 2026. All amounts are in millions of US dollars unless stated.

**Contents**

1. The three statements from zero
2. How the statements connect
3. Worked example 1: $10 more depreciation
4. Worked example 2: a sale on credit
5. Drivers and assumptions
6. Forecasting each line
7. Working capital days
8. The PP&E schedule
9. The debt schedule and the revolver
10. Circular references in plain words
11. Why the balance sheet must balance, and how to debug it
12. Historical data: mapping Yahoo Finance honestly
13. Scenarios
14. How to use the app and the Excel files
15. Hands-on Excel exercise: build a linked model yourself
16. Presenting the project to an employer
17. Interview questions and sample answers
18. Your study plan for the next 7 days

---

## 1. The three statements from zero

Imagine a small shop over one year.

**The income statement (profit and loss)** answers: *did we make a profit this year?* It lists revenue, then subtracts costs:

| Line | Meaning |
|---|---|
| Revenue | What customers were charged this year (earned, not necessarily received) |
| − Cost of goods sold (COGS) | The cost of the goods that were sold |
| = Gross profit | |
| − Operating expenses (SG&A, R&D) | Salaries, rent, marketing, research |
| − Depreciation & amortization (D&A) | The part of long-lived assets "used up" this year |
| = Operating income (EBIT) | Profit from the business itself |
| − Interest expense + interest income | The cost of borrowing, the return on cash |
| = Pre-tax income (EBT) | |
| − Income tax | |
| = **Net income** | The bottom line, which belongs to the shareholders |

It covers a **period** (e.g. the year to 30 September 2025) and uses **accrual accounting**: a sale counts when it is earned, even if the customer pays later.

**The balance sheet** answers: *what do we own and owe on one day?* It is a **snapshot** at the end of the period:

> **Assets = Liabilities + Equity**

- Assets: cash, short-term investments, accounts receivable (customers who owe us), inventory, property, plant & equipment (PP&E), other assets.
- Liabilities: accounts payable (suppliers we owe), other current liabilities, debt, other long-term liabilities.
- Equity: the owners' claim. That is money they put in (common stock and additional paid-in capital), plus profits kept in the business (**retained earnings**), minus shares bought back (**treasury stock**), plus a few accounting items (AOCI). In a group, part of equity can belong to **non-controlling interests** (minority shareholders of subsidiaries).

**The cash-flow statement** answers: *where did the cash come from and where did it go?* It has three sections:

| Section | Examples |
|---|---|
| Operating (CFO) | Cash from running the business |
| Investing (CFI) | Capex (buying PP&E), buying or selling investments |
| Financing (CFF) | Borrowing and repaying debt, dividends, share buybacks |

Most companies use the **indirect method**: start from net income, add back non-cash expenses (D&A), and adjust for changes in working capital. That is exactly how the model builds CFO.

Why do we need three statements? Because profit is not cash. A company can be profitable and run out of cash (customers pay late, it buys too much inventory, it repays debt). It can also have strong cash flow and an accounting loss (for example, heavy depreciation). Each statement shows something the others hide.

## 2. How the statements connect

These are the links every model must have. Learn them by heart.

1. **Net income** (income statement) is the first line of the cash-flow statement. It also flows into **retained earnings** on the balance sheet: *RE end = RE start + net income − dividends*.
2. **D&A** (income statement) is added back in CFO, because it is not a cash payment. It also reduces **net PP&E**: *PP&E end = PP&E start + capex − D&A*.
3. **Working capital** (balance sheet: receivables, inventory, payables) changes flow into CFO:
   - An *increase* in an asset uses cash (negative in CFO).
   - An *increase* in a liability provides cash (positive).
4. **Capex** (cash-flow statement, investing) increases PP&E.
5. **Debt issued and repaid** (financing) change the debt balance. **Interest** on that debt goes to the income statement.
6. **Dividends** (financing) reduce retained earnings. **Buybacks** (financing) increase treasury stock, which reduces equity.
7. **Ending cash** on the cash-flow statement *is* the cash line of the balance sheet. This is the most important link: cash is never typed in, it is calculated.

If all seven links are in place, the balance sheet balances automatically. You never need a "plug".

## 3. Worked example 1: $10 more depreciation

This is the most famous interview question. Assume a 25% tax rate, and that nothing else changes.

**Income statement.** D&A rises by $10, so operating income falls by $10 and pre-tax income falls by $10. Tax falls by 25% × $10 = **$2.50**. Net income falls by $10 − $2.50 = **$7.50**.

**Cash-flow statement.** Net income is down $7.50, but D&A is added back: +$10. CFO rises by **+$2.50**. The reason is that depreciation is not a cash cost, but it does reduce the tax bill (the "tax shield"). Investing and financing are unchanged, so cash is up $2.50.

**Balance sheet.**

| | Change |
|---|---|
| Cash | +$2.50 |
| Net PP&E | −$10.00 (more accumulated depreciation) |
| **Total assets** | **−$7.50** |
| Liabilities | 0 |
| Retained earnings | −$7.50 (lower net income) |
| **Total liabilities + equity** | **−$7.50** ✔ |

I checked this in the engine. With Apple's 2026E forecast, a 25% tax rate, interest on beginning balances, and no payouts linked to net income, I increased 2026E D&A by exactly 10.0. The changes were:
- D&A +10.0, EBIT −10.0, tax −2.5, net income −7.5, CFO +2.5, cash +2.5
- net PP&E −10.0, total assets −7.5, retained earnings −7.5
- balance check 0

A real-model twist: in the default Apple drivers, dividends and buybacks are a percentage of net income (together 102.6%). When net income falls by 7.5, the payouts fall by 7.69, so cash actually rises by **10.19**, not 2.5. In an interview, give the textbook answer first, then mention this. It shows you understand how a model really behaves.

## 4. Worked example 2: a sale on credit

A company sells goods for **$100 on credit** (the customer will pay next year). The goods cost **$60**, and tax is 25%, still unpaid at year end.

**Income statement.** Revenue +100, COGS +60, so gross profit and pre-tax income are +40. Tax is +10 and **net income +30**. Profit is recognised now (accrual accounting), even though no cash has arrived.

**Cash-flow statement (indirect).**

| Line | Change |
|---|---|
| Net income | +30 |
| Increase in accounts receivable | −100 (a cash "use": the sale is not collected yet) |
| Decrease in inventory | +60 (the goods left the warehouse; their cash was spent earlier) |
| Increase in tax payable | +10 (the tax is owed but not paid) |
| **CFO** | **0**, so cash is unchanged |

**Balance sheet.**

| | Change |
|---|---|
| Accounts receivable | +100 |
| Inventory | −60 |
| **Total assets** | **+40** |
| Tax payable | +10 |
| Retained earnings | +30 |
| **Total liabilities + equity** | **+40** ✔ |

Next year the customer pays: cash +100 and receivables −100. CFO shows the +100 then. This is why **DSO** (days sales outstanding) matters: the longer customers take to pay, the more cash is tied up in receivables.

## 5. Drivers and assumptions

A model does not forecast 50 lines one by one. It forecasts a few **drivers**, and every line follows from them. The app's drivers, with Apple's default values (each is calculated from the three historical years; you can edit them on the *Drivers* tab):

| Driver | Apple default | How the default is set |
|---|---|---|
| Revenue growth | 4.22%, 3.80%, 3.38%, 3.17%, 3.17% | average historical growth, faded ×1.0, 0.9, 0.8, 0.75, 0.75 |
| Gross margin | 45.75% | 3-year average |
| SG&A / R&D % of revenue | 6.60% / 8.04% | 3-year average |
| Other operating items % of revenue | −2.91% | see section 12 (D&A reclassification) |
| D&A % of beginning net PP&E | 25.89% | average of D&A ÷ prior-year net PP&E |
| Capex % of revenue | 2.78% | 3-year average |
| Tax rate on EBT | 18.14% | average effective rate (years with positive EBT and tax) |
| DSO / DIO / DPO (days) | 31.4 / 11.0 / 113.9 | 3-year averages (365-day year) |
| Dividend payout / buybacks (% of NI) | 15.2% / 87.4% | 3-year averages |
| Interest on term debt / cash / revolver | 5.0% / 3.0% / 6.0% | Apple does not report interest separately, so these are **disclosed assumptions** |
| Minimum cash | 17,967 | 50% of the latest cash (assumption) |
| Revolver capacity | 41,616.1 | 10% of the latest revenue (assumption) |

Good habits:
- Every assumption should be **visible, editable and explained**. The app lists every fallback under *How the defaults were set*.
- Start from history, then ask whether the future will be different, and why.
- Keep inputs in one place (the *Assumptions* sheet in Excel), shown in blue on yellow. Calculations should never contain typed numbers.

## 6. Forecasting each line

Here is how every forecast line is built, using Apple 2026E as the example.

| Line | Formula | Apple 2026E |
|---|---|---|
| Revenue | prior revenue × (1 + growth) | 416,161 × 1.0422 = 433,738.6 |
| COGS | revenue × (1 − gross margin) | 235,313.8 |
| SG&A, R&D, other | revenue × % | |
| D&A | rate × beginning net PP&E | 25.89% × 49,834 = 12,904.4 |
| EBIT | gross profit − opex − D&A | 134,632.6 |
| Interest expense | rate × average debt | 5% × 98,657 = 4,932.9 |
| Interest income | rate × average (cash + ST investments) | 3% × 58,262.8 = 1,747.9 |
| Tax | max(0, EBT × tax rate) | 18.14% × 131,447.6 = 23,844.8 |
| Net income | EBT − tax | 107,602.9 |
| Receivables, inventory, payables | days ÷ 365 × revenue or COGS | section 7 |
| Net PP&E | beginning + capex − D&A | 49,834 + 12,044.1 − 12,904.4 = 48,973.7 |
| Retained earnings | prior + NI − dividends | −14,264 + 107,602.9 − 16,323.4 = 77,015.5 |
| Treasury stock | prior + buybacks | 0 + 94,056.2 |
| Term debt | prior + issuance − repayment | 98,657 |
| Cash | **from the cash-flow statement** | 43,065.6 |

Lines with no good driver are **held flat**: short-term investments, other non-current assets and liabilities, common stock and AOCI. That is a common, transparent simplification.

Two details that matter:
- **Tax is never negative.** If pre-tax income is a loss, tax is 0 (the model does not book a tax credit). Ford's bear case shows this: pre-tax losses of about 8,900–9,600 a year, and tax of 0.
- **Payouts only come from profits.** Dividends and buybacks are a percentage of net income to common, and 0 when net income is negative.

## 7. Working capital days

Working capital is the cash tied up in the operating cycle: you buy inventory, sell it on credit, wait for the customer to pay, and pay suppliers later.

| Ratio | Formula | Base, and why |
|---|---|---|
| DSO (days sales outstanding) | AR ÷ revenue × 365 | **Revenue**, because receivables come from sales |
| DIO (days inventory outstanding) | Inventory ÷ COGS × 365 | **COGS**, because inventory is carried at cost, not at selling price |
| DPO (days payables outstanding) | AP ÷ COGS × 365 | **COGS**, because suppliers are paid for purchases at cost |

To forecast, turn the formulas around: AR = DSO ÷ 365 × revenue, and so on.

Apple 2026E:
- **AR** = 31.39 ÷ 365 × 433,738.6 = **37,302.7**. This is down from 39,777, so cash **+2,474.3**.
- **Inventory** = 10.96 ÷ 365 × 235,313.8 = **7,065.7**. This is up from 5,718, so cash **−1,347.7**.
- **AP** = 113.93 ÷ 365 × 235,313.8 = **73,448.1**. This is up from 69,860, so cash **+3,588.1**.

Apple's payables (114 days) are far longer than its receivables (31 days) and inventory (11 days), so **its suppliers finance its operations**. That is a sign of bargaining power.

**Sign rule:**
- An increase in an asset (AR, inventory) is a cash **outflow**.
- An increase in a liability (AP) is a cash **inflow**.
- In the model: CFO change in AR = prior AR − current AR, and change in AP = current AP − prior AP.

In the Bear scenario, DSO and DIO rise by 5 days and DPO falls by 5 days. All three hurt cash.

## 8. The PP&E schedule

The PP&E roll-forward:

> **Ending net PP&E = beginning net PP&E + capex − D&A**

The model also rolls forward gross PP&E (+ capex) and accumulated depreciation (+ D&A), so gross − accumulated depreciation = net in every year.

D&A is a rate on **beginning** net PP&E, and the history is calibrated the same way: D&A of year t ÷ net PP&E at the end of year t−1. The first version calibrated on same-year PP&E but applied the rate to beginning PP&E, which is inconsistent. D&A is also capped, so PP&E can never go below zero.

Capex vs D&A tells a story:
- **Capex > D&A**: the asset base is growing.
- **Capex < D&A**: the company is investing less than its assets wear out. Apple's capex (2.78% of revenue) is slightly below its D&A, so its net PP&E is roughly flat.

## 9. The debt schedule and the revolver

**Term debt** (bonds and loans) follows: *ending = beginning + issuance − mandatory repayment*. Repayment is capped at the balance, so debt can never go negative.

**The revolver** (a revolving credit facility) works like a company credit card. The bank commits a maximum amount (**capacity**); the company draws when it needs cash and repays when it has spare cash. The model uses it to protect a **minimum cash balance**:

1. Compute **cash before the revolver** = beginning cash + CFO + CFI + financing other than the revolver.
2. If that is **below** minimum cash: **draw** the gap, but only up to the undrawn capacity.
3. If it is **above** minimum cash: **repay** the revolver with the surplus, up to the balance outstanding.
4. If the capacity is used up and cash is still below the minimum, the model **flags a shortfall**. It never invents cash.

**Apple stress test** (a one-off 55,000 special buyback in 2026E, recurring buybacks at 80% of NI):

| | 2026E | 2027E | 2028E | 2029E | 2030E |
|---|---|---|---|---|---|
| Cash before revolver | −4,001.5 | 25,828.4 | 25,404.4 | 25,216.3 | 25,811.5 |
| Revolver draw / (repayment) | 21,968.5 | (7,861.4) | (7,437.4) | (6,669.7) | 0 |
| Ending revolver | 21,968.5 | 14,107.2 | 6,669.7 | 0 | 0 |
| Ending cash | 17,967.0 | 17,967.0 | 17,967.0 | 18,546.6 | 25,811.5 |
| Revolver interest (6%, average balance) | 659.1 | 1,082.3 | 623.3 | 200.1 | 0 |

Check 2026E: 17,967 − (−4,001.5) = 21,968.5 drawn, and the interest is 6% × (0 + 21,968.5) ÷ 2 = 659.1.

**Ford bear case.**
- Capacity is 18,726.7 and minimum cash is 11,678.
- The revolver hits its cap in 2028E. Cash then falls to 11,015.9 (662.1 below the minimum), 4,081.9 in 2029E and −3,036.0 in 2030E.
- The app shows *"revolver capacity exhausted"*.
- In real life the company would have to raise new debt or equity, sell assets or cut costs. The model's job is to show the problem, not to hide it.

## 10. Circular references in plain words

Here is the loop:

1. Interest expense depends on the **average** revolver balance (beginning + ending ÷ 2).
2. The ending revolver depends on how much cash the company generates.
3. Cash depends on net income.
4. Net income depends on interest expense, so the chain returns to step 1.

Interest income on average cash creates the same kind of loop. In Excel this is a **circular reference**: a formula that, through a chain of other cells, depends on itself.

How to solve it: **iterate**.
1. Guess the ending balances (e.g. use last year's).
2. Compute interest, then net income, cash and the revolver.
3. Use the new ending balances to recompute interest.
4. Repeat until interest stops changing.

Because interest is a small part of net income, each round changes much less than the previous one, and it converges quickly. Apple's forecast converges in 4–5 iterations a year to a relative change below 1e-9.

**Three ways to handle it:**

| Method | How | Trade-off |
|---|---|---|
| Average balances + iteration | Excel: *File → Options → Formulas → Enable iterative calculation* (saved on in the exported file) | Most accurate, but a single error can spread through the loop |
| Beginning balances | Interest = rate × beginning balance | No circularity, simpler, slightly less accurate |
| Circuit breaker | A switch (cell = 1) that forces beginning balances | Lets you "reset" a broken circular model, then switch back |

For Apple, average vs beginning balances changes 2030E net income from 124,782.4 to 124,806.5, a difference of about 0.02%. In the Python engine, if iteration ever fails to converge, the circuit breaker trips automatically and the app shows a warning.

## 11. Why the balance sheet must balance, and how to debug it

If every link in section 2 is right, assets − liabilities − equity is zero in every year. It is not a coincidence: every transaction has two sides, and the model records both. A balance sheet that does not balance means **a link is missing or wrong**, so the cash figure (and everything that depends on it) cannot be trusted.

**Never plug.** A plug forces cash, or an "other" line, to make it balance. It hides the error and destroys the model's credibility. The first version forced historical equity to equal assets − liabilities. That hid real differences, and the forecast still did not balance (Apple was off by −5,571 every year, AT&T by +105,103).

**How to debug, step by step:**

1. **Find the first year that breaks.** If the history balances and year 1 does not, the error is in a forecast link.
2. **Is the difference constant every year?** Then something is missing from the opening balance sheet. A whole equity line (AOCI, treasury stock, minority interest) is the classic case, and it was exactly the original bug.
3. **Does the difference grow?** Then a flow is missing from one statement. Look for a balance-sheet line that changes without a matching cash-flow line, or the reverse. For example, buybacks are in the cash-flow statement but treasury stock never moves.
4. **Is it twice a number you recognise?** Then a sign is wrong (an item added instead of subtracted).
5. **Run the ties.** The app's *Checks & data* tab and the Excel *Checks* sheet test each link separately: balance-sheet cash = cash-flow ending cash; RE roll-forward; PP&E roll-forward; debt roll-forward; working-capital change on the balance sheet = the cash-flow figure. The tie that is not zero shows you the broken link.

## 12. Historical data: mapping Yahoo Finance honestly

Data from Yahoo Finance is standardised, and some lines are traps. The model's mapping rules:

- **Operating income, not Yahoo's "EBIT".** Yahoo's EBIT line includes non-operating items. For Coca-Cola FY2025, Yahoo "EBIT" is 17,652, but operating income is 14,911.
- **D&A is already inside COGS and opex.** Subtracting it again would double count. The model shows D&A on its own line and adds it back through *"Other operating items / D&A reclassification"*. That is why Apple's "other" line is −2.91% of revenue. EBIT then equals reported operating income.
- **Cash vs short-term investments.** Yahoo has "Cash And Cash Equivalents" and "Cash, Cash Equivalents And Short Term Investments". Using both would double count, so ST investments = combined − cash.
- **Total liabilities and minority interest.** Use "Total Liabilities Net Minority Interest". Shareholders' equity is "Stockholders Equity", and NCI = "Total Equity Gross Minority Interest" − shareholders' equity. Coca-Cola's NCI is 2,106, AT&T's 17,959.
- **Disclosed "other" lines.** Lines that are not split out are computed as residuals from reported totals and shown as "other". Nothing is hidden. For all five snapshot companies, the historical balance sheets balance on reported totals (difference 0.0).
- **Known differences are shown.** For example, the cash-flow statement's ending cash can include restricted cash (Coca-Cola FY2025: 11,010 vs 10,270 on the balance sheet). The model warns and starts the forecast from balance-sheet cash.
- **Missing data is not invented.** Apple no longer reports interest expense separately, so the 5% rate is a stated assumption. Ford's interest rate from history is only 0.8%, because Ford Credit's interest sits inside cost of sales; the app warns about this.

## 13. Scenarios

A forecast is a guess; scenarios show how wrong it could be. The model applies **additive deltas** to the base drivers in every forecast year:

| Driver | Bull | Bear |
|---|---|---|
| Revenue growth | +3 pp | −5 pp |
| Gross margin | +1 pp | −2 pp |
| SG&A % of revenue | −0.5 pp | +1 pp |
| DSO / DIO | −3 days | +5 days |
| DPO | +3 days | −5 days |
| Term-debt / revolver interest rate | | +1.5 pp / +2 pp |

Apple 2030E:

| | Bear | Base | Bull |
|---|---|---|---|
| Revenue | 386,794.9 | 495,395.4 | 571,440.4 |
| Net income | 84,457.5 | 124,782.4 | 152,621.5 |
| Ending cash | 23,649.8 | 37,882.6 | 49,999.0 |

Scenarios are only as good as the story behind them. Say *why* the bear case is plausible (a smartphone slowdown, a price war), not just "−5%". A useful next step is a **stress test** that asks: how bad can it get before we run out of cash? The revolver stress and Ford's bear case do exactly that.

## 14. How to use the app and the Excel files

### Starting it

```bash
cd portfolio/finance/three-statement-model
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Step by step

1. **Sidebar → Data source.**
   - *Offline snapshot* (AAPL, MSFT, KO, T, F) works without internet.
   - *Live Yahoo Finance* takes any ticker.
   - *Upload template* takes your own 3 years (download the blank template there).
   - *Sample company* is a tiny fictional business.
2. **Scenario, interest method, circuit breaker, minimum cash, revolver capacity.** Change them and watch the dashboard.
3. **Dashboard:** the balance-check badge, year-5 KPIs, charts and the cash bridge (where the cash went).
4. **Drivers:** edit any driver for any year (percentages in %).
5. **Statements:** the full income statement, balance sheet and cash-flow statement, with historical and forecast years side by side.
6. **Schedules:** PP&E, working capital, debt, the revolver and interest (with iteration counts).
7. **Scenarios:** Bear / Base / Bull side by side.
8. **Checks & data:** every tie (all must be 0), the historical balance check, data warnings and the Yahoo mapping.
9. **Excel export:** download the live model.

Try the **revolver stress test** toggle: the revolver draws in year 1 and is repaid later. Then set *Revolver capacity* to 0 and watch the shortfall warning appear.

### The Excel workbooks

Open [examples/AAPL_base_case.xlsx](examples/AAPL_base_case.xlsx):

- **Assumptions:**
  - switches in column C (minimum cash, capacity, average-balance flag, circuit breaker, D&A basis)
  - drivers in columns F:J (yellow cells), with historical ratios in C:E for reference
- **Income Statement, Balance Sheet, Cash Flow:**
  - historical columns C:E hold reported data
  - forecast columns F:J are **formulas only**
  - click any forecast cell and follow the links with *Trace Precedents* (Formulas tab)
- **Schedules:** PP&E, term debt, revolver (cash before revolver, draw, repayment) and interest.
- **Checks:** the balance check, ties, and the "largest absolute check" cell (must be 0), plus a SHORTFALL flag per year.
- **Data Sources:** the source, all warnings and the Yahoo line mapping.

Exercise: change 2026E revenue growth on *Assumptions* from 4.2% to 10%, and check that *Checks* still shows 0. If you ever see `#VALUE!` or `#REF!` spreading, set the circuit breaker cell to 1, let it recalculate, fix the cause, then set it back to 0.

## 15. Hands-on Excel exercise: build a linked model yourself (60–90 minutes)

You will build a tiny company with one opening balance sheet and three forecast years. Use interest on **beginning** debt so there is no circularity. The solution is [examples/exercise_solution.xlsx](examples/exercise_solution.xlsx); try first, then compare.

### Step 1: assumptions (cells B4:B15)

| Assumption | Value |
|---|---|
| Revenue growth | 10% |
| Gross margin | 40% |
| SG&A % of revenue | 20% |
| D&A % of beginning PP&E | 10% |
| Capex % of revenue | 8% |
| Tax rate | 25% |
| Interest rate (on beginning debt) | 6% |
| DSO / DIO / DPO | 30 / 45 / 40 days |
| Debt repayment per year | 20 |
| Dividend payout | 30% of net income |

### Step 2: the opening balance sheet (Year 0)

| Assets | | Liabilities & equity | |
|---|---|---|---|
| Cash | 100 | Accounts payable | 50 |
| Accounts receivable | 80 | Debt | 200 |
| Inventory | 60 | Common stock | 150 |
| Net PP&E | 300 | Retained earnings | 140 |
| **Total** | **540** | **Total** | **540** |

Year 0 revenue was 1,000. Add a check row: `=ROUND(total assets − total L&E, 6)`. It must be 0.

### Step 3: the income statement (Years 1–3)

- Revenue = prior × (1 + growth)
- COGS = revenue × (1 − gross margin)
- SG&A = revenue × 20%
- D&A = **prior-year** PP&E × 10%
- EBIT = gross profit − SG&A − D&A
- Interest = **prior-year** debt × 6%
- Tax = `MAX(0, EBT × 25%)`
- Net income = EBT − tax

### Step 4: the cash-flow statement

- CFO = net income + D&A − (AR − prior AR) − (inventory − prior inventory) + (AP − prior AP)
- Capex = −revenue × 8%
- Debt repayment = `−MIN(20, prior debt)`
- Dividends = `−30% × MAX(0, net income)`
- Net change in cash = CFO + capex + repayment + dividends

### Step 5: the balance sheet

- Cash = prior cash + net change in cash (**never type it**)
- AR = 30/365 × revenue; inventory = 45/365 × COGS; AP = 40/365 × COGS
- PP&E = prior + capex − D&A
- Debt = prior − repayment
- Common stock = prior
- Retained earnings = prior + net income − dividends

### Step 6: check your numbers

| | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Revenue | 1,100.0 | 1,210.0 | 1,331.0 |
| EBIT | 190.0 | 206.2 | 224.3 |
| Net income | 133.5 | 146.55 | 161.03 |
| Cash from operations | 154.05 | 172.40 | 191.99 |
| Ending cash | 106.00 | 117.64 | 134.84 |
| Total assets = total L&E | 635.78 | 725.60 | 826.27 |
| Balance check | 0 | 0 | 0 |

Year 1 in detail:

1. Revenue 1,100, COGS 660, gross profit 440, SG&A 220, D&A 30 (10% × 300), EBIT 190.
2. Interest 12 (6% × 200), EBT 178, tax 44.5, net income 133.5.
3. AR 90.41, inventory 81.37, AP 72.33.
4. CFO = 133.5 + 30 − 10.41 − 21.37 + 22.33 = 154.05.
5. Cash = 100 + 154.05 − 88 − 20 − 40.05 = **106.00**.
6. Retained earnings = 140 + 133.5 − 40.05 = 233.45.

If your check is not 0, use the debugging steps in section 11.

### Stretch goals

1. Add a revolver: minimum cash 120. Draw = `MAX(0, 120 − cash before revolver)`, then repay when cash is above 120.
2. Switch interest to average debt and enable iterative calculation. Then add a circuit-breaker cell.
3. Add a scenario switch (`CHOOSE` or `INDEX`) that picks growth 5% / 10% / 15%.
4. Change DSO from 30 to 60 days and explain why cash falls although profit is unchanged.

## 16. Presenting the project to an employer

### 60-second pitch

"I built an integrated three-statement financial model in Python with a Streamlit interface and a live Excel export. It loads three years of real financials, for example Apple's from Yahoo Finance, and forecasts five years from drivers: growth, margins, working-capital days, capex, payout and a debt schedule. It also has an automatic revolver that protects minimum cash, and interest on average balances solved by iteration. The balance sheet balances with no plug; cash comes only from the cash-flow statement. I reviewed the first version like an auditor and found that the forecast balance sheet didn't balance for any real company, because equity ignored AOCI, treasury stock and minority interest. I also found a hidden plug and an income statement that double counted D&A. I fixed them, added 103 tests, and verified the Excel file in LibreOffice: 24,378 cells match Python and the balance check is zero."

### 5-minute demo script

1. **Dashboard (Apple, base):** the green "balances in every forecast year" badge. 2030E revenue 495,395.4, net income 124,782.4, cash 37,882.6, balance check 0.
2. **Statements → Balance sheet:** point at treasury stock, AOCI and NCI, which the original version dropped, and at the check row.
3. **Schedules:** show the working-capital days formulas, the PP&E roll-forward and the revolver block.
4. **Turn on the revolver stress test:** the revolver draws 21,968.5 in 2026E and is repaid by 2029E. Interest iterations are shown.
5. **Switch to Ford, Bear:** "capacity exhausted" warnings, and the model still balances.
6. **Checks & data:** every tie is 0. Show the Yahoo mapping (Operating Income, not EBIT).
7. **Excel export:** open it, change a driver on *Assumptions*, and show *Checks* = 0 and *Trace Precedents* on cash.

### CV bullet points

- Built an integrated **three-statement financial model** (Python, Streamlit, Excel) with working-capital days, PP&E and debt schedules, an automatic revolver with minimum cash, and average-balance interest solved by iteration with a circuit breaker. The balance sheet balances with no plug for Apple, Microsoft, Coca-Cola, AT&T and Ford in base, bull and bear scenarios.
- **Reviewed and corrected the first version of the model** as an auditor would: fixed equity that omitted AOCI, treasury stock and minority interest (balance-sheet errors up to 105 billion), a hidden historical plug, a D&A double count and Yahoo "EBIT" mis-mapping. Added 103 automated tests, including a regression test for each bug.
- Exported a **live-formula Excel model** (assumptions-driven, iterative calculation, check sheet) and verified it by recalculating 33 workbooks in LibreOffice: **24,378 values match Python, and the balance check is 0** in every year.

### LinkedIn post draft

> I've just finished a project every finance student should try at least once: an integrated three-statement model. 📊
>
> It loads three years of real financials (Apple, Microsoft, Coca-Cola, AT&T, Ford), forecasts five years from drivers, and keeps the income statement, balance sheet and cash-flow statement linked. That includes a working-capital, PP&E and debt schedule, a revolver that protects minimum cash, and the famous circular reference (interest on average balances), solved by iteration.
>
> The most useful part was reviewing the first version as an accountant would. It looked finished, but its balance sheet didn't balance for any real company: equity ignored treasury stock, AOCI and minority interest. It also had a hidden plug, and D&A was counted twice. Fixing it taught me more than building it.
>
> Rule I'll keep: **never plug the balance sheet.** Cash comes from the cash-flow statement, and if it doesn't balance, a link is broken.
>
> Python · Streamlit · Excel (live formulas, verified in LibreOffice) · 103 tests
> Code and a beginner's guide: github.com/Yasskik/portfolio
>
> #FinancialModeling #Accounting #Excel #Python #Finance

## 17. Interview questions and sample answers

**1. Walk me through the three financial statements.**
The income statement shows revenue, expenses and net income over a period. The balance sheet shows assets, liabilities and equity at a point in time, and assets = liabilities + equity. The cash-flow statement explains the change in cash in three parts: operating, investing and financing. They link because net income starts the cash-flow statement and flows into retained earnings. Non-cash items like D&A are added back, and changes in balance-sheet items (working capital, PP&E through capex, debt, equity) appear in the cash-flow statement. Ending cash from the cash-flow statement is the cash on the balance sheet.

**2. Depreciation goes up by $10. Walk me through the statements (25% tax).**
Income statement: operating income −10, tax −2.5, net income −7.5. Cash flow: net income −7.5, D&A added back +10, so cash +2.5. Balance sheet: cash +2.5 and PP&E −10, so assets −7.5. Retained earnings −7.5, so equity −7.5. It balances. (In my model the payouts are linked to net income, so cash actually rises a bit more, because dividends and buybacks fall.)

**3. A company sells $100 of goods on credit, costing $60. What happens?**
Revenue +100, COGS +60, so pre-tax income +40. At 25% tax, net income +30. Cash flow: net income +30, receivables −100, inventory +60, tax payable +10, so CFO 0 and cash is unchanged. Balance sheet: AR +100 and inventory −60, so assets +40; tax payable +10 and retained earnings +30. When the customer pays, cash rises by 100 and AR falls by 100.

**4. Inventory increases by $10, paid in cash. What happens?**
No income-statement effect (inventory is expensed only when sold). CFO −10, because an increase in a working-capital asset uses cash. Balance sheet: inventory +10 and cash −10, so total assets are unchanged.

**5. Why is net income different from cash flow?**
Accrual accounting. Non-cash expenses (D&A, stock compensation), working-capital timing (customers paying late, inventory build-ups, paying suppliers later), capex that is spent now but expensed over years, and financing flows (debt, dividends, buybacks) that do not touch the income statement.

**6. How do you forecast working capital? Why use COGS for inventory and payables?**
With days ratios: AR = DSO ÷ 365 × revenue, inventory = DIO ÷ 365 × COGS, AP = DPO ÷ 365 × COGS. Inventory and payables are carried at cost, so they relate to COGS; receivables are at selling price, so they relate to revenue. An increase in AR or inventory reduces cash; an increase in AP increases it.

**7. What is a revolver and why have a minimum cash balance?**
A committed credit line the company draws and repays as needed. Companies keep minimum cash for operations and safety. In the model, if cash before the revolver falls below the minimum, the revolver draws the gap up to its capacity. When there is surplus cash, it is repaid first. If capacity runs out, the model flags a shortfall instead of inventing cash.

**8. Where is the circular reference in a three-statement model, and how do you handle it?**
Interest on average debt or cash depends on ending balances. Those depend on cash flow, which depends on net income, which depends on interest. You either use iterative calculation (with a circuit-breaker switch to reset it), or calculate interest on beginning balances. My model iterates to a relative tolerance of 1e-9 and falls back to beginning balances automatically if it does not converge.

**9. Your balance sheet doesn't balance. What do you do?**
First, never plug. I find the first year that breaks and look at the pattern. A constant difference usually means an opening-balance or equity item is missing; a growing difference means a flow is missing from one statement; twice a known number means a sign error. Then I run the ties: cash vs the cash-flow statement, the RE, PP&E and debt roll-forwards, and working capital. This is exactly how I found that the original model dropped AOCI, treasury stock and NCI.

**10. How do you forecast capex and D&A?**
Capex as a percentage of revenue (or from management guidance). D&A as a percentage of beginning PP&E, or from a detailed depreciation waterfall by asset vintage. PP&E rolls forward as beginning + capex − D&A. Capex above D&A means a growing asset base.

**11. What is free cash flow, and what does it tell you?**
In my model, FCF = CFO − capex: the cash left after maintaining and growing the asset base. It is available for dividends, buybacks and debt repayment. Apple's 2026E FCF is 117,511.1, and payouts of about 102.6% of net income use nearly all of it.

**12. What data problems did you find with Yahoo Finance, and how did you handle them?**
Yahoo's "EBIT" is not operating income (Coca-Cola: 17,652 vs 14,911). D&A is already embedded in COGS and opex. "Cash" and "cash and short-term investments" overlap. Minority interest sits between total liabilities and total equity, and restricted cash makes cash-flow ending cash differ from balance-sheet cash. I map to operating income, compute ST investments as a difference, add NCI explicitly, show residual "other" lines, and display every difference instead of plugging it.

**13. What are the limitations of your model?**
It is driver-based and annual. There is no NOL tax asset (losses get zero tax, not a credit carried forward), no share count or EPS, no detailed debt maturities or revolver commitment fees, and no leases or deferred taxes. Many lines are held flat. Scenarios are simple deltas, not a probability distribution. Yahoo's standardised data can differ from the 10-K.

### How to show you really know the project

- Explain the seven links in section 2 without notes.
- Do the $10 depreciation and sale-on-credit examples on a whiteboard.
- Rebuild the exercise in section 15 from an empty sheet in under an hour.
- Open the Excel file and trace cash back to net income with *Trace Precedents*.
- Explain one bug in detail, e.g. why the constant −5,571 for Apple pointed to a missing equity line (it equals Apple's AOCI & other equity).

### Improvements you can make yourself (pick 2–3)

1. **NOL carryforward:** store tax losses and use them to reduce future tax (Ford's bear case is a good test).
2. **Share count and EPS:** model buybacks as shares retired at an assumed price, and show EPS growth.
3. **Revolver commitment fee:** for example 0.25% on the undrawn capacity, added to interest expense.
4. **Debt maturities from the 10-K:** replace the zero mandatory repayment with Apple's real maturity table.
5. **A DCF tab:** discount the forecast unlevered free cash flow (link it to the DCF project in this portfolio).
6. **A sensitivity table:** year-5 cash for growth −5%…+5% × gross margin −2…+2 pp.
7. **Minimum cash as % of revenue,** and a sweep that moves surplus cash to ST investments.
8. **Quarterly model:** shows seasonality in working capital.

For each improvement, add a test first (for example: "with a 1,000 NOL and EBT of 600, tax is 0 and the NOL falls to 400"), then make it pass.

## 18. Your study plan for the next 7 days

| Day | Goal | Tasks (about 1.5–2 hours) |
|---|---|---|
| 1 | The statements | Re-read sections 1–2. Write the seven links from memory. Read Apple's FY2025 income statement, balance sheet and cash flow in the app. |
| 2 | Worked examples | Do sections 3–4 on paper, plus 3 variations: inventory +10; a $50 debt raise; a $20 dividend. Check every balance sheet balances. |
| 3 | Drivers and working capital | Sections 5–7. Recompute Apple's 2026E AR, inventory and AP by hand from the drivers. Change DSO in the app and explain the cash effect. |
| 4 | Build in Excel | Section 15, without looking at the solution. Debug until the check is 0, then compare with `exercise_solution.xlsx`. |
| 5 | Debt, revolver, circularity | Sections 9–10. Add the revolver and the circuit breaker (stretch goals 1–2) to your workbook. Run the app's stress test and explain each number. |
| 6 | Debugging and data | Sections 11–13. Break your workbook on purpose three ways (drop a dividend link, a wrong sign, a missing equity line) and find each with the ties. Compare KO's Yahoo "EBIT" with operating income. |
| 7 | Presentation | Practise the 60-second pitch and the demo out loud (record yourself). Answer the 13 interview questions without notes. Pick one improvement from section 17 and start it. |
