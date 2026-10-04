# Shared design system (`ui_theme.py`)

All five finance apps use one look: a light, editorial "research note" style with serif headings, tabular numbers,
hairline borders and consistent red / green for negative / positive values. There is no dark theme, no gradients and no glow.

`ui_theme.py` in this folder is the **master copy**. Each project keeps a **vendored copy** next to its `app.py`,
so every project still runs on its own when it is cloned or deployed by itself. Nothing imports from `../_shared`.

```bash
python finance/_shared/sync_theme.py          # copy ui_theme.py into every project + regenerate .streamlit/config.toml
python finance/_shared/sync_theme.py --check  # exit 1 if any project copy or config.toml is out of date
```

Edit the master copy, then run the sync. The `.streamlit/config.toml` in each project is generated from the same tokens,
so Streamlit's own widgets (sliders, radios, tabs, inputs) match the custom components.

## Tokens

| Role | Token | Hex |
|---|---|---|
| Text (ink navy) | `INK` / `INK_2` / `MUTED` | `#0F1B2D` / `#3D4A5C` / `#6B7585` |
| Page background (warm paper) | `PAPER` | `#FAF8F4` |
| Cards, charts | `SURFACE` / `SURFACE_2` (sidebar, table headers) | `#FFFFFF` / `#F3F0E9` |
| Hairlines, gridlines | `HAIRLINE` / `GRID` | `#E3DED3` / `#ECE8DF` |
| Accent (deep teal), secondary (oxford blue) | `ACCENT` / `ACCENT_2` | `#0B5D6B` / `#1F4E8C` |
| Positive / negative / warning | `POS` / `NEG` / `WARN` | `#0E7F4F` / `#C0322B` / `#B7791F` |
| Tinted backgrounds | `POS_BG` / `NEG_BG` / `WARN_BG` / `ACCENT_BG` | `#E7F3EC` / `#FBEAE8` / `#FBF1DE` / `#E5F0F1` |

Categorical chart palette (`PALETTE`): `#1F4E8C` `#0E8C8C` `#E07B39` `#C0322B` `#6A4C9C` `#2E9E5B` `#C9A227` `#5C6B7A`.
Diverging scale (`DIVERGING`) for heatmaps: red `#C0322B` → paper `#F6F3EC` → green `#0E7F4F`.

Fonts (Google Fonts): **Source Serif 4** for titles and headings, **Inter** for the UI with tabular figures
(`font-variant-numeric: tabular-nums`), so the decimals in tables and KPI cards line up.

Spacing follows an 8 px scale (8 / 16 / 24 / 32 / 48).

## Components

| Function | What it renders |
|---|---|
| `apply(title, icon)` | `st.set_page_config` plus fonts and CSS (call first) |
| `masthead(title, subtitle, kicker, meta)` | publication-style header: kicker, serif title, one-line description, byline (Yamen Agha, GitHub link) and a meta row |
| `sidebar_brand`, `sidebar_section` | sidebar title and small-caps section labels |
| `section(title, caption, kicker)`, `subhead(title, note)` | section headings with a hairline rule |
| `kpis(cards, cols)` | equal-width, equal-height KPI cards: label, big number, delta chip (green / red / amber) and a note |
| `chip`, `callout`, `callout_html`, `card`, `spacer`, `footer` | small building blocks |
| `html_table(df, fmt, row_fmt, row_styles, max_height, highlight)` | publication table: sticky header, zebra rows, right-aligned tabular numbers, accounting format with red negatives in parentheses, total / subtotal rows |
| `styler(df, fmt)` | the same formats as a pandas Styler for `st.dataframe` |
| `money`, `acct`, `pct`, `num`, `tone`, `color_for`, `bar_colors`, `rgba` | number formatting and sign-based colours |
| `style_fig(fig, title, subtitle, ...)`, `chart(fig)` | apply the Plotly template, titles and margins, then render with a consistent toolbar |

The Plotly template `ledger` is registered and set as the default. It sets the fonts, the palette, light gridlines,
unified hover with spike lines, a horizontal legend centred under the plot, 350 ms transitions, and red / green waterfall colours.
