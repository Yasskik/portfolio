# Historical data templates

Enter **3 fiscal years** (oldest on the left) and upload the file in the app: sidebar → *Data source* → *Upload template*.

| File | What it is |
|---|---|
| `three_statement_template.xlsx` | Blank Excel template (42 line items, yellow input cells, an *Instructions* sheet) |
| `blank_template.csv` | The same layout as CSV |
| `sample_company.xlsx` / `sample_historical.csv` | A small **fictional** company (revenue 1,000 → 1,120 → 1,250) that balances in every year, to try the upload |

Regenerate them with `python scripts/make_templates.py`.

## Rules the loader follows

- **Exact labels.** Rows are matched on the label in column A (case and punctuation are ignored). Unknown rows are listed as a warning and ignored, so a typo never silently moves a number to the wrong line.
- **Required lines:** Revenue, Operating income (EBIT), Pre-tax income, Net income to common shareholders, Cash, Total assets, Total liabilities, Total shareholders' equity.
- **Totals are kept as entered.** Lines you do not split out go to disclosed "other" lines (e.g. other current assets = total current assets − cash − ST investments − AR − inventory). AOCI and other equity = shareholders' equity − common stock − retained earnings + treasury stock.
- **No plugs.** If total assets ≠ total liabilities + total equity, the difference is shown in the balance check of that historical year. It is never forced to zero.
- **Signs.** Cash-flow outflows are negative (capex, dividends, buybacks, debt repaid). Costs on the income statement are positive. Accumulated depreciation and treasury stock are read as positive amounts.
- **Missing lines.** Leave the cell empty. The line is shown as n/a (or 0 inside totals) and listed in the warnings. Nothing is invented.
- **Units.** Use one unit for everything (e.g. millions).
