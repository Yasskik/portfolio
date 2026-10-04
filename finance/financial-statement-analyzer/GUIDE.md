# Your Financial Statement Analyzer: A Beginner's Guide

*Written for Yamen Agha. Read it slowly, with the app and the Excel file open next to you.*

This guide starts from zero. You already know debits and credits from your accounting courses. Here we use that knowledge to **analyse** a company, not just record its transactions. By the end you should be able to:

1. Explain what financial statement analysis is, and what each of the three statements tells you.
2. Explain every ratio in the app in plain words: its formula, what a good or bad value looks like, and Apple's actual number.
3. Explain DuPont, the Altman Z-score and the Piotroski F-score, and know when *not* to use them.
4. Use the app and the Excel file, and compute the key ratios for a real company yourself.
5. Present the project to an employer, answer interview questions, and honestly say "I understand this and I improved it myself."

All numbers for Apple in this guide come from the app's data snapshot of **Apple's fiscal year 2025** (the year that ended on 27 September 2025). They are in **USD millions** unless stated otherwise, and were taken on 1 October 2026.

**Contents**

1. What financial statement analysis is, from zero
2. The three statements, explained
3. Every ratio in plain words
4. DuPont, Altman Z, Piotroski, common-size and trend analysis
5. How to use the app and the Excel file, plus a hands-on exercise
6. Presenting the project to an employer
7. Interview questions and sample answers
8. Your study plan for the next 7 days

---

## 1. What financial statement analysis is, from zero

### Accounting records the story; analysis reads it

In your accounting courses you learn how to *prepare* financial statements: journal entries, ledgers, trial balance, then the statements. **Financial statement analysis** goes the other way. You take finished statements and ask questions like these:

- Is the company **profitable**? How many cents of profit does it keep from each dollar of sales?
- Is it **liquid**? Can it pay the bills due in the next 12 months?
- Is it **solvent**? Does it carry too much debt for its earnings?
- Is it **efficient**? How quickly does it turn inventory and receivables into cash?
- Is the profit **real**? Is it backed by cash, or only by accounting entries?

Banks ask these questions before they lend. Investors ask them before they buy shares. Auditors use them to spot unusual numbers, and brokers use them to compare companies for clients.

### Why ratios and not raw numbers?

Apple's net income of $112,010 million is just a big number on its own. Is it good? You can't tell until you **compare** it with something:

- **with sales.** $112,010 / $416,161 = 26.9% net margin. Apple keeps about 27 cents of every dollar of sales.
- **with last year.** FY2024 net income was $93,736M, so profit grew 19.5%.
- **with peers.** Microsoft's net margin was 40.3% and Coca-Cola's 27.3%.

A ratio removes the effect of size, so you can compare a small company with a giant, or 2022 with 2025.

### Three ways to compare

| Comparison | Question | In the app |
|---|---|---|
| **Over time** (trend / horizontal) | Is the company improving or getting worse? | Growth tab, horizontal analysis, trend charts |
| **Within one year** (common-size / vertical) | How is each dollar of sales spent? What are the assets made of? | Common-size view |
| **Against peers** | Is it better or worse than its competitors? | Peer Comparison tab |

> **Golden rule.** A ratio is a question, not an answer. A current ratio of 0.89 is a warning sign for a small shop, but normal for Apple, which collects cash from customers long before it pays suppliers. Always ask *why* a number looks the way it does.

---

## 2. The three statements, explained

### The income statement: "Did we make money this year?"

It covers a **period** (one year). It starts with sales and subtracts costs step by step. Apple FY2025:

| Line | USD m | What it means |
|---|---:|---|
| Revenue (sales) | 416,161 | Everything Apple sold: iPhones, Macs, services and so on |
| − Cost of revenue (COGS) | (220,960) | The direct cost of the products and services sold |
| **= Gross profit** | **195,201** | What is left to pay for running the business |
| − Research & development | (34,550) | |
| − Selling, general & administrative | (27,601) | |
| **= Operating income (EBIT)** | **133,050** | Profit from the core business, before interest and tax |
| ± Other income / (expense), net | (321) | Interest, investment gains and other non-operating items |
| **= Pre-tax income (EBT)** | **132,729** | |
| − Income tax | (20,719) | 15.6% effective tax rate |
| **= Net income** | **112,010** | The bottom line, which belongs to shareholders |

Check it yourself: 416,161 − 220,960 = 195,201. Then 195,201 − 34,550 − 27,601 = 133,050. Then 133,050 − 321 = 132,729, and 132,729 − 20,719 = 112,010.

### The balance sheet: "What do we own and owe on one day?"

It is a **snapshot** at the year-end date. It always balances: **Assets = Liabilities + Equity**.

| Apple, 27 Sep 2025 | USD m |
|---|---:|
| Cash and cash equivalents | 35,934 |
| Short-term investments (marketable securities) | 18,763 |
| Accounts receivable (trade) | 39,777 |
| Other (vendor non-trade) receivables | 33,180 |
| Inventory | 5,718 |
| Other current assets | 14,585 |
| **Total current assets** | **147,957** |
| Non-current assets (long-term securities, PP&E, other) | 211,284 |
| **Total assets** | **359,241** |
| Accounts payable | 69,860 |
| Other current liabilities (incl. current debt 20,329) | 95,771 |
| **Total current liabilities** | **165,631** |
| Non-current liabilities (incl. long-term debt 78,328) | 119,877 |
| **Total liabilities** | **285,508** |
| Shareholders' equity (incl. retained earnings of −14,264) | 73,733 |
| **Total liabilities + equity** | **359,241** |

Check it: 285,508 + 73,733 = 359,241. ✔

Two things that surprise beginners:

- **Retained earnings are negative** (−14,264), even though Apple earns about $100 billion a year. This is because Apple has spent more on **share buybacks and dividends** than it has kept as profit ($90.7bn of buybacks and $15.4bn of dividends in FY2025 alone). Negative retained earnings are not always a sign of losses, so always check why.
- **Equity is small** compared with assets (73,733 of 359,241). Buybacks shrink equity. This makes Apple's ROE look huge (151.9%), which is a classic interview topic.

### The cash-flow statement: "Where did the cash actually go?"

Profit is an accounting opinion; cash is a fact. This statement explains the change in cash in three sections:

| Apple FY2025 | USD m | What it means |
|---|---:|---|
| Cash from operating activities (CFO) | 111,482 | Cash generated by the business |
| Cash from investing activities | 15,195 | Capex of −12,715, plus net sales of investment securities |
| Cash from financing activities | (120,686) | Buybacks (−90,711), dividends (−15,421) and debt repayment |
| **Net change in cash** | **5,991** | 29,943 at the start + 5,991 = 35,934 at the end ✔ |

**Free cash flow (FCF)** = CFO − capital expenditure = 111,482 − 12,715 = **98,767**. It is the cash left after the company maintains and grows its assets, and it is what pays for dividends, buybacks and debt repayment.

> **Sign convention.** Yahoo Finance reports capex as a *negative* number (−12,715), because it is cash going out. The app always uses the absolute value, FCF = CFO − |capex|, so the sign can't be wrong. It is a common bug in student projects, and this one had it too.

### How the three statements link

- Net income (income statement) → goes into retained earnings (balance sheet) → is the starting line of CFO (cash-flow statement).
- The cash-flow statement explains the change in the balance-sheet cash line.
- Capex on the cash-flow statement increases PP&E on the balance sheet. Depreciation reduces PP&E and is an expense on the income statement.

---

## 3. Every ratio in plain words

**Conventions in the app.**

- Balance-sheet items are **year-end** values, unless the ratio name says "(avg.)". Avg. means (this year-end + last year-end) / 2.
- Days ratios use **365 days**.
- If any input is missing, the ratio shows **n/a**. The app never puts 0 in place of a missing number.

The "good / bad" ranges are rough rules of thumb for non-financial companies. They depend a lot on the industry.

### 3.1 Liquidity: can it pay its bills in the next 12 months?

| Ratio | Formula | Plain words | Rough guide | Apple FY2025 |
|---|---|---|---|---|
| **Current ratio** | Current assets / current liabilities | Dollars of short-term assets for each dollar of short-term bills | 1.2–2.0 comfortable; < 1.0 needs a reason | 147,957 / 165,631 = **0.89x** |
| **Quick ratio** | (Cash + ST investments + receivables) / current liabilities | Like the current ratio, but without inventory and prepaid items that are slow to turn into cash | > 1.0 comfortable | (54,697 + 72,957) / 165,631 = **0.77x** |
| **Cash ratio** | (Cash + ST investments) / current liabilities | Could it pay today with cash in hand? | 0.2–0.5 is normal | 54,697 / 165,631 = **0.33x** |

Why is Apple below 1 and still fine? It generates over $100 billion of operating cash a year, collects from customers quickly, and pays suppliers slowly (see the CCC below). It also holds $77.7 billion of *long-term* marketable securities, which are not counted in current assets.

### 3.2 Profitability: how much profit does it make?

| Ratio | Formula | Plain words | Rough guide | Apple FY2025 |
|---|---|---|---|---|
| **Gross margin** | Gross profit / revenue | Profit left after the direct cost of products | Industry-specific: retail 25–35%, software 70%+ | 195,201 / 416,161 = **46.9%** |
| **Operating margin** | Operating income / revenue | Profit from the core business per $1 of sales | > 15% strong | 133,050 / 416,161 = **32.0%** |
| **Net margin** | Net income / revenue | Bottom-line profit per $1 of sales | > 10% strong | 112,010 / 416,161 = **26.9%** |
| **Effective tax rate** | Tax / pre-tax income | The share of profit paid in tax | US statutory rate is 21% | 20,719 / 132,729 = **15.6%** |
| **ROA** | Net income / total assets | Profit produced by each $1 of assets | > 5% good; banks ~1% | 112,010 / 359,241 = **31.2%** |
| **ROE** | Net income / shareholders' equity | Return earned on the owners' money | 10–20% good. Very high values are often caused by low equity | 112,010 / 73,733 = **151.9%** |
| **ROIC** | Operating income × (1 − tax rate) / (total debt + equity) | Return on all the capital that lenders and owners put in | > the cost of capital (about 8–10%) creates value | 133,050 × (1 − 15.6%) / (98,657 + 73,733) = **65.1%** |

The app also shows **ROA (avg. assets)** = 30.9% and **ROE (avg. equity)** = 171.4%. Average balances are the textbook choice, because profit is earned over the whole year. The ending-balance versions are kept because DuPont multiplies back exactly only with them.

**Why we use "Operating Income" and not Yahoo's "EBIT".** Yahoo calculates its own EBIT line as pre-tax income + interest expense, which includes non-operating items. For margins and coverage we want what the company itself reports as operating income. For Apple FY2025 the two are the same (133,050), but for many companies they differ.

### 3.3 Solvency and leverage: is the debt manageable?

| Ratio | Formula | Plain words | Rough guide | Apple FY2025 |
|---|---|---|---|---|
| **Debt-to-equity** | Total debt / equity | Borrowed money for each $1 of owners' money | < 1.0 conservative; > 2.0 high (depends on industry) | 98,657 / 73,733 = **1.34x** |
| **Debt-to-assets** | Total debt / total assets | Share of assets financed by debt | < 40% comfortable | 98,657 / 359,241 = **27.5%** |
| **Financial leverage (equity multiplier)** | Total assets / equity | Assets supported by each $1 of equity | 2–3 is common; banks 10+ | 359,241 / 73,733 = **4.87x** |
| **Interest coverage** | Operating income / interest expense | How many times operating profit covers the interest bill | > 5x safe; < 1.5x danger | **n/a** (see below) |

*Total debt* means interest-bearing debt only (borrowings, notes, commercial paper and, where reported, leases). It is **not** total liabilities. Accounts payable is not debt.

**Interest coverage for Apple is n/a.** From FY2024 Apple stopped reporting interest expense as a separate line, so Yahoo has no number for it. The app shows n/a instead of guessing or showing "infinite". In FY2023, when Apple still reported it, coverage was 114,301 / 3,933 = **29.1x**. Interest expense is always treated as a positive cost. If operating income is negative, coverage is negative and the health report flags it.

### 3.4 Efficiency and working capital: how fast does cash go round?

| Ratio | Formula | Plain words | Apple FY2025 |
|---|---|---|---|
| **Asset turnover** | Revenue / total assets | Sales produced by each $1 of assets | 416,161 / 359,241 = **1.16x** |
| **Inventory turnover** | COGS / inventory | How many times a year inventory is sold and replaced | 220,960 / 5,718 = **38.6x** |
| **DSO** (days sales outstanding) | Accounts receivable / revenue × 365 | Days it takes to collect from customers | 39,777 / 416,161 × 365 = **34.9 days** |
| **DIO** (days inventory outstanding) | Inventory / COGS × 365 | Days inventory sits before it is sold | 5,718 / 220,960 × 365 = **9.4 days** |
| **DPO** (days payable outstanding) | Accounts payable / COGS × 365 | Days the company takes to pay suppliers | 69,860 / 220,960 × 365 = **115.4 days** |
| **Cash conversion cycle (CCC)** | DSO + DIO − DPO | Days between paying suppliers and collecting from customers | 34.9 + 9.4 − 115.4 = **−71.1 days** |

Notes:

- **Inventory and payables use COGS, not revenue.** Inventory and payables are recorded at cost, so comparing them with sales (which include the profit margin) would mix two different measures.
- **A negative CCC is excellent.** Apple collects from customers about 71 days *before* it pays its suppliers, so suppliers are financing Apple's operations. The same explains its current ratio below 1.
- **No inventory?** A software or service company may report none. Then DIO counts as 0 and inventory turnover is n/a. The app doesn't crash.
- **Rough guide:** compare with peers and with the company's own history. A rising DSO can mean customers are paying later, or that sales are being booked too early.

### 3.5 Cash-flow quality: is the profit backed by cash?

| Ratio | Formula | Plain words | Rough guide | Apple FY2025 |
|---|---|---|---|---|
| **CFO / net income** | Operating cash flow / net income | Cash earned for each $1 of reported profit | ≥ 1.0 healthy; persistently < 0.8 is a warning | 111,482 / 112,010 = **1.00x** |
| **Free cash flow** | CFO − \|capex\| | Cash left after investment | Positive and growing | **$98,767M** |
| **FCF margin** | FCF / revenue | Free cash per $1 of sales | > 10% strong | **23.7%** |
| **Capex / revenue** | \|Capex\| / revenue | How capital-hungry the business is | Software < 5%, utilities 20%+ | **3.1%** |
| **Sloan accrual ratio** | (Net income − CFO) / total assets | The part of profit that is accruals rather than cash | Near 0 good; > +10% is a red flag | (112,010 − 111,482) / 359,241 = **0.1%** |

### 3.6 Growth (year over year)

Growth = (this year − last year) / |last year|. Apple FY2025: revenue **+6.4%**, operating income **+8.0%**, net income **+19.5%** (FY2024 had a one-off tax charge of about $10bn related to the EU state-aid case, so the base year was low), and FCF **−9.2%**.

> **Banks are different.** JPMorgan has no "current assets", no COGS and no inventory. Its "revenue" is mostly interest and fee income. Current ratio, gross margin, CCC, Altman and Piotroski are **not meaningful** for banks, so the app shows n/a and labels the report "Limited (financial company)". For banks, look at ROE (JPM FY2025: **15.7%**), ROA (**1.3%**) and, outside this app, capital ratios such as CET1.

---

## 4. DuPont, Altman Z, Piotroski, common-size and trend analysis

### 4.1 DuPont analysis: *why* is ROE high or low?

DuPont splits ROE into parts, so you can see whether it comes from **margins**, **efficiency** or **debt**.

**3-step:**

ROE = (Net income / Revenue) × (Revenue / Assets) × (Assets / Equity) = **net margin × asset turnover × financial leverage**

Apple FY2025: 26.9% × 1.158 × 4.872 = **151.9%**. That is exactly the ROE, because "revenue" and "assets" cancel out. ✔

**5-step:** this version splits the net margin further:

ROE = (NI / EBT) × (EBT / EBIT) × (EBIT / Revenue) × (Revenue / Assets) × (Assets / Equity)
= **tax burden × interest burden × operating margin × asset turnover × leverage**

| Component | Apple FY2025 | Reading |
|---|---:|---|
| Tax burden (NI / EBT) | 0.844 | Keeps 84.4% of pre-tax profit after tax |
| Interest burden (EBT / EBIT) | 0.998 | Non-operating items barely matter |
| Operating margin (EBIT / revenue) | 0.320 | Very profitable core business |
| Asset turnover | 1.158 | |
| Financial leverage | 4.872 | Big contribution from low equity (buybacks) |
| **Product = ROE** | **151.9%** | The same as the reported ROE ✔ |

Here EBIT = operating income. Both versions use **ending** balances, so the product equals ROE exactly. The DuPont sheet in Excel has a check row that shows the difference (0).

**What it tells you about Apple:** strong margins *and* high leverage. Margin × turnover gives a return on assets of 31.2%. The 4.87x leverage, which comes from buybacks that made equity small, turns that into a 151.9% ROE. Compare KO: ROE 40.7% with a net margin of 27.3%.

### 4.2 Altman Z-score: how close is the company to financial distress?

Edward Altman (1968) built this score from public **manufacturing** companies that did and did not go bankrupt:

**Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 0.999·X5**

| Part | Formula | Apple FY2025 |
|---|---|---:|
| X1 | Working capital / total assets = (147,957 − 165,631) / 359,241 | −0.049 |
| X2 | Retained earnings / total assets = −14,264 / 359,241 | −0.040 |
| X3 | EBIT (operating income) / total assets = 133,050 / 359,241 | 0.370 |
| X4 | **Market value** of equity / total liabilities = 3,761,715 / 285,508 | 13.18 |
| X5 | Revenue / total assets = 416,161 / 359,241 | 1.158 |
| **Z** | 1.2(−0.049) + 1.4(−0.040) + 3.3(0.370) + 0.6(13.18) + 0.999(1.158) | **10.17** |

**Zones:** safe > 2.99 · grey 1.81–2.99 · distress < 1.81. Apple's Z by year is 6.54 (FY2022), 7.65, 8.89 and 10.17 (FY2025). It is in the safe zone in every year.

**Market value of equity** = the share price at the **fiscal year-end** × the shares outstanding at year-end. For Apple: $254.63 × 14,773.3M shares = $3,761.7bn. An early version of the app used *today's* market cap for the latest year and *book* equity for older years, so the score jumped from 2.1 to 12.5 for no real reason. Every year now uses its own year-end price.

**Z'' (Altman 1995)** is the version for **non-manufacturers** and emerging markets. It drops X5 and uses **book** equity in X4:

**Z'' = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4''**, where X4'' = book equity / total liabilities = 73,733 / 285,508 = 0.258.

Apple: Z'' = **2.31** (grey zone; Z'' zones are safe > 2.60, grey 1.10–2.60, distress < 1.10). The grey result comes from low book equity and negative retained earnings, both caused by buybacks. It is a good example of why you must understand a model's inputs before you trust it. Apple is not close to bankruptcy.

> **When not to use it:** banks and insurers (their balance sheets are mostly financial assets and debt, so the ratios mean something else), and very young companies. The app returns n/a for financial companies.

### 4.3 Piotroski F-score: is the company getting stronger?

Joseph Piotroski (2000) built a score from 9 yes/no tests. Each "yes" scores 1 point, so the total is 0–9. Every test compares **this year with last year**:

| # | Test (1 point if true) | Apple FY2025 vs FY2024 | Point |
|---|---|---|:-:|
| 1 | ROA > 0 (net income / *beginning* total assets) | 112,010 / 364,980 = 30.7% | 1 |
| 2 | Operating cash flow > 0 | 111,482 | 1 |
| 3 | ROA higher than last year | 30.7% vs 26.6% | 1 |
| 4 | CFO > net income (quality of earnings) | 111,482 < 112,010 | **0** |
| 5 | Long-term debt / average total assets fell | 21.7% vs 23.9% | 1 |
| 6 | Current ratio rose | 0.89 vs 0.87 | 1 |
| 7 | No new shares issued (shares ≤ last year) | 14,773M vs 15,117M | 1 |
| 8 | Gross margin rose | 46.9% vs 46.2% | 1 |
| 9 | Asset turnover rose (revenue / beginning assets) | 1.140 vs 1.109 | 1 |
| | **F-score** | | **8 / 9** |

**Reading:** 8–9 strong · 5–7 moderate · 0–4 weak. Apple scored 7 in FY2024 and 8 in FY2025.

Why are FY2022 and FY2023 n/a? Test 3 needs last year's ROA, and last year's ROA needs the assets from the year *before*. With 4 years of data, only the last 2 years can be scored fully. The app shows a total only when **all 9** tests can be measured, so it never gives free points for missing data.

### 4.4 Common-size (vertical) analysis

Divide every line by a base: **revenue** for the income statement, **total assets** for the balance sheet. For Apple FY2025, COGS = 53.1% of revenue, R&D = 8.3%, SG&A = 6.6%, operating income = 32.0% and net income = 26.9%. On the balance sheet, cash and short-term investments = 15.2% of assets and inventory = 1.6%. Common-size lets you compare Apple with a company ten times smaller, or see that inventory is a tiny part of Apple's assets.

### 4.5 Trend (horizontal) analysis

This compares each line with the previous year (% change), or with a base year set to 100 (indexed). For Apple, revenue went from 394,328 (FY2022) to 416,161 (FY2025): an index of **105.5**, or about **+1.8% a year**. Net income went from 99,803 to 112,010, an index of 112.2. Trends answer the question "is it getting better?", which a single year can't.

---

## 5. How to use the app and the Excel file

### Starting it

```bash
cd portfolio/finance/financial-statement-analyzer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py      # opens http://localhost:8501
```

### Step by step

1. **Sidebar → Data Source.** Choose *Yahoo Finance Ticker(s)* and type one or more tickers separated by commas (for example `AAPL, MSFT`). You can also click a peer button: *Tech: AAPL vs MSFT*, *Payments: V vs MA*, *Beverages: KO vs PEP* or *Industrials: CAT vs DE*. If you are offline, the app uses the saved snapshot. With several tickers, *Company for the in-depth tabs* (also in the sidebar) picks the company shown in every tab except Peer Comparison.
2. Or choose **Upload Custom Financials**. Download the CSV or Excel template, fill in your own company's statements (for example a Syrian company's published accounts), and upload the file. You can enter the market value of equity if you want an Altman Z. Without it, only Z'' is calculated.
3. **Executive Health Dashboard:** KPI cards (Z, F, ROE, FCF margin, current ratio, operating margin), the overall rating, three equal panels of strengths, things to watch and red flags, a revenue / net income / FCF chart and a ratio scorecard against benchmarks.
4. **Financial Statements:** the raw statements, common-size % or trend (YoY % or indexed) views.
5. **Key Financial Ratios:** six sub-tabs, each with formulas, explanations and a chart.
6. **DuPont & Credit Scoring:** 3-step and 5-step DuPont with factor charts, Altman Z / Z'' (zone chart and a build-up of the five factors), and the Piotroski table with a pass/fail grid.
7. **Peer Comparison:** a card per company, a radar chart, grouped bar charts and a side-by-side table (enter 2 or more tickers).
8. **Export Center:** download the Excel workbook, the PDF report or the Markdown report.

### The Excel workbook (`examples/AAPL_analysis.xlsx`)

- **Blue numbers are inputs** (copied from the statements, in USD millions). Black cells are **formulas**. A blank cell means the item was not reported, and every ratio that needs it shows "n/a".
- **Sheets:**
  - *Summary*
  - *Income Statement*, *Balance Sheet* (with a market-data block: FY-end price × shares = market value) and *Cash Flow*
  - *Ratios*, *DuPont* (with check rows), *Altman Z*, *Piotroski*, *Common-Size* and *Notes*
- Try this: on *Income Statement*, change FY2025 revenue (cell E4) from 416161 to 450000. Margins, turnover, DSO, DuPont, Z-score and Summary all update immediately. Undo afterwards.
- Click any ratio cell and read its formula, for example `='Balance Sheet'!E10/'Balance Sheet'!E16` for the current ratio. Being able to trace every number back to its source is what makes a model easy to audit.
- The workbook was recalculated in LibreOffice and compared cell by cell with the Python results: **0 differences**.

### Hands-on exercise: compute Apple's key ratios yourself (45–60 minutes)

Open a **blank** Excel sheet. Don't copy from the app. Type the inputs below (Apple FY2025, USD millions). You can check them against Apple's 10-K for FY2025 (on investor.apple.com or SEC EDGAR).

**Step 1: inputs.** Put labels in column A and values in column B:

| Row | Item | Value |
|---|---|---:|
| 2 | Revenue | 416,161 |
| 3 | Cost of revenue (COGS) | 220,960 |
| 4 | Operating income | 133,050 |
| 5 | Pre-tax income | 132,729 |
| 6 | Income tax | 20,719 |
| 7 | Net income | 112,010 |
| 8 | Total current assets | 147,957 |
| 9 | Total current liabilities | 165,631 |
| 10 | Inventory | 5,718 |
| 11 | Accounts receivable (trade) | 39,777 |
| 12 | Accounts payable | 69,860 |
| 13 | Total assets | 359,241 |
| 14 | Total liabilities | 285,508 |
| 15 | Shareholders' equity | 73,733 |
| 16 | Total debt | 98,657 |
| 17 | Retained earnings | −14,264 |
| 18 | Operating cash flow | 111,482 |
| 19 | Capital expenditure (as reported) | −12,715 |
| 20 | Shares outstanding (millions) | 14,773.3 |
| 21 | Share price at FY end ($) | 254.63 |

**Step 2: check that it balances.** In B23 type `=B14+B15-B13`. It must equal 0. Always do this check first.

**Step 3: ratios.** Type each formula, then compare with the expected answer:

| Cell | Ratio | Formula | Expected |
|---|---|---|---:|
| B25 | Gross margin | `=(B2-B3)/B2` | 46.9% |
| B26 | Operating margin | `=B4/B2` | 32.0% |
| B27 | Net margin | `=B7/B2` | 26.9% |
| B28 | Current ratio | `=B8/B9` | 0.89 |
| B29 | ROA | `=B7/B13` | 31.2% |
| B30 | ROE | `=B7/B15` | 151.9% |
| B31 | Debt-to-equity | `=B16/B15` | 1.34 |
| B32 | Tax rate | `=B6/B5` | 15.6% |
| B33 | ROIC | `=B4*(1-B32)/(B16+B15)` | 65.1% |
| B34 | DSO | `=B11/B2*365` | 34.9 |
| B35 | DIO | `=B10/B3*365` | 9.4 |
| B36 | DPO | `=B12/B3*365` | 115.4 |
| B37 | CCC | `=B34+B35-B36` | −71.1 |
| B38 | Free cash flow | `=B18-ABS(B19)` | 98,767 |
| B39 | FCF margin | `=B38/B2` | 23.7% |

**Step 4: DuPont.** `=B27*(B2/B13)*(B13/B15)` should give 151.9%, the same as B30.

**Step 5: Altman Z.** Market value = `=B20*B21` → about 3,761,700 (USD millions). Then:
`=1.2*(B8-B9)/B13 + 1.4*B17/B13 + 3.3*B4/B13 + 0.6*(B20*B21)/B14 + 0.999*B2/B13` → **10.17**.

**Step 6: compare and write.** Open `examples/AAPL_analysis.xlsx` and check that your numbers match the *Ratios* and *Altman Z* sheets. Then write **5 sentences** explaining Apple's health in your own words. Mention the negative CCC, the current ratio below 1, and why ROE is so high.

**Step 7 (bonus):** repeat Steps 1–5 for **Coca-Cola (KO)** using the app's Financial Statements tab. You should get an operating margin of about 31.1%, ROE of about 40.7% and Z of about 4.67.

---

## 6. Presenting the project to an employer

### 60-second pitch

"I built a financial statement analyzer in Python. You type a ticker and it downloads three or four years of income statements, balance sheets and cash flows. It calculates 34 ratios, DuPont, the Altman Z-score and the Piotroski F-score, and it compares peers and writes a health report. It exports an Excel workbook where every ratio is a live formula linked to the statements, and I checked it against the Python results in LibreOffice: zero differences. As an accounting student, the part I care most about is the definitions. For example, it uses operating income instead of Yahoo's derived EBIT, COGS for inventory days, and the fiscal-year-end market value in Altman Z. Missing data shows as n/a instead of zero. For Apple FY2025 it shows a 32% operating margin, a negative 71-day cash conversion cycle, a Z-score of 10.2 and an F-score of 8 out of 9."

### 5-minute demo script

1. **(30 s) Problem:** "Comparing companies by hand takes hours, and it's easy to make formula mistakes."
2. **(60 s) Dashboard:** click *Tech: AAPL vs MSFT*. Show the KPI cards and the strengths and warnings. Explain why a current ratio of 0.89 is fine for Apple.
3. **(60 s) Ratios → Efficiency:** explain DSO, DIO, DPO and the negative CCC.
4. **(60 s) DuPont & Credit:** show the 3-step DuPont multiplying back to ROE. Explain that buybacks drive Apple's leverage. Show Altman Z vs Z'' and Piotroski 8/9.
5. **(45 s) Excel:** open the workbook, click a ratio to show its formula, and change revenue to show everything updating.
6. **(45 s) Quality:** show the tests, and mention one bug you found and fixed (for example the Altman market-value bug).

### CV bullet points

- Built a **Python/Streamlit financial statement analyzer** that calculates 34 ratios, 3- and 5-step DuPont, Altman Z/Z'' and Piotroski F-score for any listed company, with peer comparison and a PDF health report.
- Designed an **Excel export with live formulas** linked to the income statement, balance sheet and cash flow (about 470 formulas per company). Verified it against Python with a LibreOffice recalculation: **0 mismatches across 10 companies**.
- **Reviewed and corrected the accounting definitions**, for example operating income vs derived EBIT, COGS-based DIO/DPO, fiscal-year-end market value in Altman Z, and the original Piotroski criteria. Covered them with **61 automated tests**.

### LinkedIn post draft

> 📊 New project: a Financial Statement Analyzer (Python + Excel)
>
> As a 3rd-year accounting student, I wanted to go beyond preparing statements and practise *reading* them. This tool takes any ticker and calculates 34 ratios, DuPont, the Altman Z-score and the Piotroski F-score. It compares peers and exports an Excel workbook where every ratio is a live formula.
>
> What I learned:
> 🔹 Apple's current ratio is below 1, and that's fine: its cash conversion cycle is −71 days, so suppliers finance its operations.
> 🔹 Apple's ROE of 152% comes partly from buybacks that shrank its equity. DuPont makes that visible.
> 🔹 Definitions matter: using today's market cap instead of the year-end value moved Apple's Z-score from 2.1 to 12.5.
>
> I reviewed every formula against its accounting definition and added automated tests.
>
> Code and Excel file: github.com/Yasskik/portfolio
> #Accounting #FinancialAnalysis #Excel #Python #Finance

---

## 7. Interview questions and sample answers

**1. Why can a company with a current ratio below 1 be healthy?**
If it turns sales into cash faster than it pays suppliers (a negative CCC) and has strong operating cash flow. Apple's current ratio is 0.89, but its CCC is −71 days and its CFO is $111bn. For a company with slow-moving inventory, the same ratio would be a warning.

**2. Why does Apple's ROE exceed 150%? Is that good?**
Partly because of high margins and turnover, but mostly because years of buybacks have made equity small (equity multiplier 4.9x). DuPont separates these effects. ROIC (65%) is a better measure of operating quality because leverage doesn't distort it.

**3. What is the difference between EBIT and operating income?**
In textbooks they are often the same. In data feeds, EBIT is sometimes calculated as pre-tax income + interest, which includes non-operating gains and losses. I use the company's reported operating income for margins, coverage and Altman X3.

**4. Why do inventory turnover and DPO use COGS and not revenue?**
Inventory and payables are recorded at cost. Revenue includes the profit margin, so dividing by it would mix two different measures and make DIO and DPO look too small.

**5. Ending or average balances?**
Averages match a flow (profit for a year) with the resources used during that year, so they are more accurate. Ending balances are simpler, and with them DuPont multiplies back exactly. My app shows both and labels which is which.

**6. How do you calculate free cash flow, and what is the most common mistake?**
CFO − capital expenditure. The most common mistake is the sign: data feeds report capex as negative, so "CFO − capex" adds it back. I use CFO − |capex|.

**7. Explain the Altman Z-score and its limitations.**
It is a weighted sum of five ratios (liquidity, accumulated profits, operating return, market leverage, turnover), built from 1960s US manufacturers. Above 2.99 is safe and below 1.81 is distress. It doesn't fit banks, and it is less reliable for service or asset-light companies. Z'' (without sales, with book equity) is for those. Buybacks can push X2 and book equity down even when the company is strong.

**8. Walk me through the Piotroski F-score.**
Nine 0/1 tests: four on profitability (ROA > 0, CFO > 0, ROA rising, CFO > NI), three on leverage and liquidity (less long-term debt, higher current ratio, no new shares) and two on efficiency (higher gross margin, higher asset turnover). 8–9 is strong and 0–4 is weak. It needs two prior years, so with 4 years of data only the last 2 years can be scored.

**9. How would you analyse a bank differently?**
There are no current assets or COGS, and debt (deposits) is the raw material of the business. I would focus on ROE, ROA, net interest margin, cost-to-income ratio, loan-loss provisions and capital ratios (CET1). My app marks Altman, Piotroski and CCC as n/a for banks.

**10. What does a negative retained earnings balance mean?**
Normally, accumulated losses. But for Apple it is because buybacks and dividends have exceeded the profits kept in the business. Always read the equity statement before drawing a conclusion.

**11. What is the Sloan accrual ratio telling you?**
(Net income − CFO) / total assets. A high positive value means a large part of profit is non-cash accruals, which tend to reverse. Apple's is about 0.1%, which is clean.

**12. How did you make sure your Excel numbers are right?**
Every ratio is a formula linked to the statement sheets. I recalculated the workbook in LibreOffice and compared every ratio and score cell with the Python engine for 10 companies: 0 mismatches. Missing inputs give "n/a" through `IF(COUNT(...))` checks, not zero.

**Bonus: what would you add next?**
Industry benchmarks (median ratios by sector), a bank-specific module, quarterly data and TTM figures, and an Altman model chosen automatically from the company's sector.

### How to show you really know the project

- Be able to do the **hands-on exercise** (Section 5) from memory for any company, using only a calculator.
- Be able to explain **every row** of the Ratios sheet and point to its formula.
- Know the **bug list** in the README, and explain one bug in detail.

### Improvements you can make yourself (pick 2–3)

1. **Add a ratio:** for example *Net debt / EBITDA* (total debt − cash, divided by operating income + D&A). Add it to `calculate_solvency_ratios` in `analyzer.py`, add a formula row in `excel_export.py`, and write one test.
2. **Industry benchmarks:** a small CSV of typical ranges by sector, shown next to each ratio.
3. **Bank module:** for JPM, show the net interest margin and the cost-to-income ratio.
4. **Analyse a local company:** fill in the upload template with a Damascus Securities Exchange-listed company's published statements (in SYP) and write a one-page analysis.
5. **Make the health-report rules your own:** change the thresholds in `generate_health_report` and explain why.
6. **Quarterly / TTM data:** use `yfinance` quarterly statements.

Each change is small, but it is *your* commit, and something you can talk about in an interview.

---

## 8. Your study plan for the next 7 days

| Day | Goal (about 1–2 hours) | Output |
|---|---|---|
| 1 | Read Sections 1–2. Find Apple's FY2025 10-K and locate the three statements | Check that 5 numbers from Section 2 match the 10-K |
| 2 | Section 3.1–3.3 (liquidity, profitability, solvency) | Flash cards: formula + meaning + Apple value |
| 3 | Section 3.4–3.6 and the Section 5 exercise, Steps 1–4 | Your own Excel sheet with 15 ratios matching the guide |
| 4 | Section 4: DuPont, Altman (exercise Step 5) and Piotroski by hand | Piotroski for Apple FY2025 calculated on paper: 8/9 |
| 5 | Run the app with KO vs PEP and with JPM. Write a 1-page comparison | A short PDF memo in your own words |
| 6 | Make one improvement from Section 7. Commit it to GitHub | Your own commit |
| 7 | Practise the pitch, the demo and the 12 interview answers out loud. Publish the LinkedIn post | A recorded 60-second pitch, and the post |

**Good luck, Yamen. You now know how to read a company, not just how to record its books.**

*Educational material only. Not investment advice. Figures come from Yahoo Finance data as of 1 October 2026; always check against the company's filed reports.*
