"""ui_theme.py - the shared design system of Yamen Agha's finance apps.

One file, vendored (copied unchanged) into every project so each app still runs on its own
after `git clone`. The master copy lives in finance/_shared/ui_theme.py; run
`python finance/_shared/sync_theme.py` after editing it to copy it into the five projects
and regenerate their .streamlit/config.toml from the same tokens.

Contents
  TOKENS / colours ......... ink, paper, hairline, accent, positive/negative/warning, chart palette
  apply() .................. fonts + CSS + the Plotly template ("ledger"); call once per page
  masthead(), section(), footer(), callout(), kpis(), chip(), spacer()
  html_table() ............. publication-style table (zebra rows, sticky header, accounting negatives)
  styler() ................. the same number formatting for st.dataframe (interactive tables)
  chart() .................. st.plotly_chart with the template, crisp config and no Streamlit theme
  money(), acct(), pct(), num() formatting helpers
"""
from __future__ import annotations

import html as _html
import math
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Union

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ----------------------------------------------------------------------------- tokens
INK = "#0F1B2D"          # primary text: deep ink navy
INK_2 = "#3D4A5C"        # secondary text
MUTED = "#6B7585"        # captions, axis labels
PAPER = "#FAF8F4"        # page background: warm off-white
SURFACE = "#FFFFFF"      # cards, charts, tables
SURFACE_2 = "#F3F0E9"    # sidebar, zebra rows, table headers
HAIRLINE = "#E3DED3"     # 1px borders
GRID = "#ECE8DF"         # chart gridlines
ACCENT = "#0B5D6B"       # deep teal: links, active tab, primary buttons
ACCENT_2 = "#1F4E8C"     # oxford blue: secondary accent
POS = "#0E7F4F"          # positive / gains
NEG = "#C0322B"          # negative / losses
WARN = "#B7791F"         # warnings / caution
POS_BG, NEG_BG, WARN_BG, ACCENT_BG = "#E7F3EC", "#FBEAE8", "#FBF1DE", "#E5F0F1"

# categorical chart palette: vivid but harmonious, distinguishable in print
PALETTE = ["#1F4E8C", "#0E8C8C", "#E07B39", "#C0322B", "#6A4C9C", "#2E9E5B", "#C9A227", "#5C6B7A"]
DIVERGING = [[0.0, NEG], [0.5, "#F6F3EC"], [1.0, POS]]
SEQUENTIAL = [[0.0, "#E5F0F1"], [0.5, "#4F9AA3"], [1.0, "#0B3F4A"]]

SERIF = "'Source Serif 4', 'Source Serif Pro', Georgia, 'Times New Roman', serif"
SANS = "Inter, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONT_URL = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&"
            "family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap")
GITHUB = "https://github.com/Yasskik/portfolio"
AUTHOR = "Yamen Agha"

TOKENS = dict(ink=INK, ink_2=INK_2, muted=MUTED, paper=PAPER, surface=SURFACE, surface_2=SURFACE_2,
              hairline=HAIRLINE, grid=GRID, accent=ACCENT, accent_2=ACCENT_2, pos=POS, neg=NEG, warn=WARN,
              palette=PALETTE)

# ----------------------------------------------------------------------------- CSS
_CSS = f"""
<style>
@import url('{FONT_URL}');
:root {{ --ink:{INK}; --ink2:{INK_2}; --muted:{MUTED}; --paper:{PAPER}; --surface:{SURFACE}; --surface2:{SURFACE_2};
        --hair:{HAIRLINE}; --accent:{ACCENT}; --pos:{POS}; --neg:{NEG}; --warn:{WARN}; }}
html, body, .stApp, [data-testid="stAppViewContainer"] {{ background:var(--paper); color:var(--ink);
  font-family:{SANS}; font-feature-settings:"tnum" 1, "lnum" 1; -webkit-font-smoothing:antialiased; }}
[data-testid="stHeader"] {{ background:transparent; height:0; }}
[data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display:none; }}
[data-testid="stMainBlockContainer"], .block-container {{ max-width:1320px; padding:40px 48px 24px 48px; }}
h1, h2, h3, h4 {{ font-family:{SERIF}; color:var(--ink); letter-spacing:-0.01em; font-weight:600; }}
p, li, label, .stMarkdown {{ color:var(--ink); }}
a {{ color:var(--accent); }}
[data-testid="stCaptionContainer"], .stCaption {{ color:var(--muted); }}

/* sidebar */
[data-testid="stSidebar"] {{ background:var(--surface2); border-right:1px solid var(--hair); }}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding-top:8px; }}
[data-testid="stSidebar"] label p {{ font-size:13px; color:var(--ink2); font-weight:500; }}
.ya-side-brand {{ font-family:{SERIF}; font-size:20px; font-weight:600; color:var(--ink); line-height:1.2;
  padding:4px 0 12px 0; border-bottom:2px solid var(--ink); margin-bottom:8px; }}
.ya-side-brand span {{ display:block; font-family:{SANS}; font-size:11px; font-weight:500; letter-spacing:.08em;
  text-transform:uppercase; color:var(--muted); margin-top:4px; }}
.ya-side-h {{ font-size:11px; font-weight:600; letter-spacing:.09em; text-transform:uppercase; color:var(--accent);
  margin:24px 0 8px 0; padding-bottom:6px; border-bottom:1px solid var(--hair); }}
[data-testid="stSidebar"] [data-testid="stExpander"] details {{ background:var(--surface); }}
[data-testid="stSidebar"] .stButton > button {{ padding:4px 6px; min-height:34px; border-color:var(--hair); font-weight:600; }}
[data-testid="stSidebar"] .stButton > button p {{ font-size:12.5px; letter-spacing:.02em; }}

/* masthead */
.ya-mast {{ border-top:4px solid var(--ink); padding-top:16px; margin-bottom:24px; }}
.ya-kicker {{ font-size:11px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); }}
.ya-mast-row {{ display:grid; grid-template-columns:1fr auto; gap:32px; align-items:end; margin-top:8px; }}
.ya-title {{ font-family:{SERIF}; font-size:40px; line-height:1.1; font-weight:600; color:var(--ink); margin:0; padding:0; }}
.ya-sub {{ font-size:16px; color:var(--ink2); margin:8px 0 0 0; max-width:760px; line-height:1.5; }}
.ya-byline {{ text-align:right; font-size:12px; color:var(--muted); line-height:1.6; white-space:nowrap; }}
.ya-byline b {{ color:var(--ink); font-weight:600; }}
.ya-rule {{ border:0; border-top:1px solid var(--hair); margin:16px 0 0 0; }}
.ya-meta {{ display:flex; flex-wrap:wrap; gap:8px 24px; margin-top:12px; font-size:13px; color:var(--ink2); }}
.ya-meta b {{ color:var(--ink); font-weight:600; }}

/* section headings */
.ya-section {{ margin:40px 0 16px 0; display:grid; grid-template-columns:1fr auto; align-items:end; gap:16px;
  border-bottom:1px solid var(--hair); padding-bottom:8px; }}
.ya-section h3 {{ font-family:{SERIF}; font-size:24px; margin:0; padding:0; font-weight:600; color:var(--ink); }}
.ya-section .ya-section-k {{ font-size:11px; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
  color:var(--muted); }}
.ya-section p {{ grid-column:1 / -1; margin:4px 0 0 0; color:var(--ink2); font-size:14px; }}

/* KPI cards: one CSS grid, so every card in a row has the same width and height */
.ya-kpis {{ display:grid; gap:16px; margin:8px 0 8px 0; }}
.ya-kpi {{ background:var(--surface); border:1px solid var(--hair); border-radius:8px; padding:16px 20px 16px 20px;
  box-shadow:0 1px 2px rgba(15,27,45,.04); display:flex; flex-direction:column; justify-content:flex-start;
  min-height:128px; border-top:3px solid var(--kpi-accent, var(--ink)); }}
.ya-kpi-label {{ font-size:13px; font-weight:600; letter-spacing:.01em; color:var(--ink2); white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; }}
.ya-kpi-value {{ font-family:{SERIF}; font-size:32px; font-weight:600; color:var(--ink); line-height:40px; height:40px;
  margin:8px 0 8px 0; display:flex; align-items:center;
  font-variant-numeric:tabular-nums lining-nums; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.ya-kpi-value.sm {{ font-size:26px; }} .ya-kpi-value.xs {{ font-size:21px; }}
.ya-kpi-foot {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; font-size:12px; color:var(--muted); min-height:22px; }}
.ya-chip {{ display:inline-flex; align-items:center; gap:4px; font-size:12px; font-weight:600; padding:2px 8px;
  border-radius:999px; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.ya-chip.pos {{ color:var(--pos); background:{POS_BG}; }} .ya-chip.neg {{ color:var(--neg); background:{NEG_BG}; }}
.ya-chip.warn {{ color:var(--warn); background:{WARN_BG}; }} .ya-chip.neutral {{ color:var(--ink2); background:var(--surface2); }}
.ya-chip.accent {{ color:var(--accent); background:{ACCENT_BG}; }}
.pos {{ color:var(--pos); }} .neg {{ color:var(--neg); }} .warn {{ color:var(--warn); }}

/* callouts */
.ya-callout {{ border:1px solid var(--hair); border-left:3px solid var(--c, var(--accent)); background:var(--surface);
  border-radius:6px; padding:12px 16px; margin:8px 0; font-size:14px; color:var(--ink); line-height:1.5; }}
.ya-callout b.t {{ color:var(--c, var(--accent)); font-weight:600; margin-right:6px; }}

.ya-subhead {{ font-family:{SERIF}; font-size:18px; font-weight:600; color:var(--ink); margin:4px 0 4px 0; }}
.ya-subhead-n {{ font-size:13px; color:var(--muted); margin:0 0 12px 0; }}

/* cards and grids */
.ya-card {{ background:var(--surface); border:1px solid var(--hair); border-radius:8px; padding:20px 24px;
  box-shadow:0 1px 2px rgba(15,27,45,.04); height:100%; }}
.ya-card h4 {{ font-family:{SERIF}; font-size:18px; margin:0 0 8px 0; }}

/* publication tables */
.ya-tablewrap {{ background:var(--surface); border:1px solid var(--hair); border-radius:8px; overflow:auto;
  box-shadow:0 1px 2px rgba(15,27,45,.04); }}
table.ya-table {{ border-collapse:separate; border-spacing:0; width:100%; font-size:13.5px;
  font-variant-numeric:tabular-nums lining-nums; }}
table.ya-table thead th {{ position:sticky; top:0; z-index:1; background:var(--surface2); color:var(--ink2);
  font-size:12px; font-weight:600; letter-spacing:.01em; text-align:right;
  padding:10px 16px; border-bottom:1px solid var(--hair); white-space:nowrap; }}
table.ya-table thead th:first-child {{ text-align:left; }}
table.ya-table th, table.ya-table td {{ border:none; }}
table.ya-table td {{ padding:8px 16px; text-align:right; white-space:nowrap; color:var(--ink); border-bottom:1px solid #F0EDE6; }}
table.ya-table td:first-child {{ text-align:left; white-space:normal; color:var(--ink); min-width:180px; }}
table.ya-table tbody tr:nth-child(even) td {{ background:#FBFAF7; }}
table.ya-table tbody tr:hover td {{ background:{ACCENT_BG}; }}
table.ya-table tr.total td {{ font-weight:600; border-top:1px solid var(--ink2); }}
table.ya-table tr.grand td {{ font-weight:700; border-top:1px solid var(--ink); border-bottom:3px double var(--ink); }}
table.ya-table tr.sub td:first-child {{ padding-left:32px; color:var(--ink2); }}
table.ya-table tr.head td {{ font-family:{SERIF}; font-weight:600; font-size:14px; background:var(--surface) !important;
  padding-top:16px; color:var(--accent); }}
table.ya-table td.neg {{ color:var(--neg); }} table.ya-table td.pos {{ color:var(--pos); }}
table.ya-table td.na {{ color:var(--muted); }}
table.ya-table td.hl {{ background:{ACCENT_BG} !important; font-weight:600; }}

/* Streamlit widgets */
[data-baseweb="tab-list"] {{ gap:32px; border-bottom:1px solid var(--hair); }}
button[data-baseweb="tab"] {{ padding:12px 0; background:transparent; }}
button[data-baseweb="tab"] p {{ font-size:14px; font-weight:500; color:var(--ink2); }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color:var(--ink); font-weight:600; }}
[data-baseweb="tab-highlight"] {{ background:var(--accent); height:2px; }}
[data-baseweb="tab-border"] {{ display:none; }}
[data-testid="stPlotlyChart"] {{ background:var(--surface); border:1px solid var(--hair); border-radius:8px;
  padding:12px 12px 4px 12px; box-shadow:0 1px 2px rgba(15,27,45,.04); }}
[data-testid="stDataFrame"] {{ border:1px solid var(--hair); border-radius:8px; overflow:hidden; background:var(--surface); }}
[data-testid="stExpander"] details {{ border:1px solid var(--hair); border-radius:8px; background:var(--surface); }}
[data-testid="stExpander"] summary p {{ font-weight:600; color:var(--ink); }}
.stButton > button, .stDownloadButton > button {{ border-radius:6px; border:1px solid var(--ink); background:var(--surface);
  color:var(--ink); font-weight:600; box-shadow:none; }}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color:var(--accent); color:var(--accent); }}
.stDownloadButton > button[kind="primary"], .stButton > button[kind="primary"] {{ background:var(--ink); color:#fff; border-color:var(--ink); }}
.stDownloadButton > button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
.stDownloadButton > button[kind="primary"] p, .stButton > button[kind="primary"] p,
.stDownloadButton > button[kind="primary"] span, .stButton > button[kind="primary"] span {{ color:#fff !important; }}
button[data-testid="stBaseButton-primary"] {{ background:var(--ink) !important; border-color:var(--ink) !important; color:#fff !important; }}
button[data-testid="stBaseButton-primary"]:hover {{ background:var(--accent) !important; border-color:var(--accent) !important; }}
button[data-testid="stBaseButton-primary"] p, button[data-testid="stBaseButton-primary"] span {{ color:#fff !important; }}
[data-testid="stMetric"] {{ background:var(--surface); border:1px solid var(--hair); border-radius:8px; padding:16px 20px; }}
[data-testid="stAlert"] {{ border-radius:6px; }}
div[data-testid="stRadio"] > label p, div[data-testid="stSelectbox"] > label p {{ font-weight:500; }}

/* footer */
.ya-footer {{ margin-top:56px; padding:16px 0 8px 0; border-top:1px solid var(--hair); display:grid;
  grid-template-columns:1fr auto; gap:24px; align-items:center; font-size:12px; color:var(--muted); }}
.ya-footer .c {{ text-align:center; }} .ya-footer .r {{ text-align:right; }}
.ya-footer a {{ color:var(--ink); font-weight:600; text-decoration:none; border-bottom:1px solid var(--hair); }}
.ya-spacer {{ height:var(--h, 16px); }}
@media (max-width: 900px) {{
  [data-testid="stMainBlockContainer"], .block-container {{ padding:24px 16px; }}
  .ya-kpis {{ grid-template-columns:repeat(2, minmax(0, 1fr)) !important; }}
  .ya-mast-row, .ya-footer {{ grid-template-columns:1fr; }} .ya-byline, .ya-footer .r, .ya-footer .c {{ text-align:left; }}
}}
/* equal-height bordered panels when a column holds only one container */
[data-testid="stHorizontalBlock"] {{ align-items:stretch; }}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"]:only-child) {{ height:100%; }}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child,
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child > [data-testid="stVerticalBlock"] {{ height:100%; }}
</style>
"""


# ----------------------------------------------------------------------------- Plotly template
def _template() -> go.layout.Template:
    t = go.layout.Template(pio.templates["plotly_white"])
    axis = dict(gridcolor=GRID, gridwidth=1, linecolor=HAIRLINE, linewidth=1, zerolinecolor="#C9C2B3", zerolinewidth=1,
                ticks="outside", tickcolor=HAIRLINE, ticklen=4, tickfont=dict(size=12, color=MUTED),
                title=dict(font=dict(size=12, color=INK_2), standoff=8), automargin=True,
                showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikedash="dot",
                spikecolor="#9AA3AF")
    t.layout.update(
        font=dict(family=SANS, size=13, color=INK),
        title=dict(font=dict(family=SERIF, size=19, color=INK), x=0, xanchor="left", y=0.97, yanchor="top",
                   pad=dict(l=4, b=8), subtitle=dict(font=dict(family=SANS, size=12.5, color=MUTED))),
        colorway=PALETTE, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        margin=dict(l=56, r=44, t=88, b=80),
        xaxis=dict(axis, showgrid=False), yaxis=dict(axis),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=0.02, yanchor="bottom", yref="container",
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(size=12, color=INK_2), itemclick="toggle", itemdoubleclick="toggleothers",
                    title=dict(text="")),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=HAIRLINE, font=dict(family=SANS, size=12.5, color=INK),
                        align="left", namelength=-1),
        hovermode="x unified", hoverdistance=60, spikedistance=-1,
        transition=dict(duration=350, easing="cubic-in-out"),
        bargap=0.28, bargroupgap=0.08,
        coloraxis=dict(colorbar=dict(outlinewidth=0, thickness=12, tickfont=dict(size=11, color=MUTED))),
        separators=".,",
    )
    t.data.bar = [go.Bar(marker=dict(line=dict(width=0)), cliponaxis=False)]
    t.data.scatter = [go.Scatter(line=dict(width=2.5), marker=dict(size=7, line=dict(width=1.5, color=SURFACE)))]
    t.data.waterfall = [go.Waterfall(connector=dict(line=dict(color="#B8B0A0", width=1, dash="dot")),
                                     increasing=dict(marker=dict(color=POS)), decreasing=dict(marker=dict(color=NEG)),
                                     totals=dict(marker=dict(color=ACCENT_2)), cliponaxis=False)]
    t.data.heatmap = [go.Heatmap(colorscale=DIVERGING, xgap=2, ygap=2)]
    t.data.pie = [go.Pie(marker=dict(colors=PALETTE, line=dict(color=SURFACE, width=2)), sort=False)]
    t.data.histogram = [go.Histogram(marker=dict(line=dict(color=SURFACE, width=0.5)))]
    return t


pio.templates["ledger"] = _template()
pio.templates.default = "ledger"

CHART_CONFIG = {"displaylogo": False, "responsive": True, "scrollZoom": False,
                "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
                "toImageButtonOptions": {"format": "png", "scale": 2}}


# ----------------------------------------------------------------------------- formatting
def _ok(x) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def money(x, cur: str = "$", dp: int = 2, unit: str = "", signed: bool = False) -> str:
    """$1,234.56 / -$12.30 / $2.4B (unit appended)."""
    if not _ok(x):
        return "n/a"
    x = float(x)
    sign = "−" if x < 0 else ("+" if signed and x > 0 else "")
    return f"{sign}{cur}{abs(x):,.{dp}f}{unit}"


def acct(x, dp: int = 0, cur: str = "") -> str:
    """Accounting style: 1,234 / (1,234) / – for zero."""
    if not _ok(x):
        return "n/a"
    x = float(x)
    if abs(x) < 0.5 * 10 ** (-dp):
        return "–"
    s = f"{cur}{abs(x):,.{dp}f}"
    return f"({s})" if x < 0 else s


def pct(x, dp: int = 1, signed: bool = False, ratio: bool = True) -> str:
    """pct(0.0425) -> 4.3%. Use ratio=False when x is already in percent."""
    if not _ok(x):
        return "n/a"
    v = float(x) * (100 if ratio else 1)
    sign = "−" if v < 0 and not signed else ""
    if signed:
        return f"{'+' if v > 0 else ('−' if v < 0 else '')}{abs(v):.{dp}f}%"
    return f"{sign}{abs(v):.{dp}f}%"


def num(x, dp: int = 2, suffix: str = "") -> str:
    if not _ok(x):
        return "n/a"
    x = float(x)
    return f"{'−' if x < 0 else ''}{abs(x):,.{dp}f}{suffix}"


def tone(x, good_if_positive: bool = True, tol: float = 0.0) -> str:
    if not _ok(x) or abs(float(x)) <= tol:
        return "neutral"
    return "pos" if (float(x) > 0) == good_if_positive else "neg"


def color_for(x, good_if_positive: bool = True) -> str:
    t = tone(x, good_if_positive)
    return POS if t == "pos" else (NEG if t == "neg" else MUTED)


# ----------------------------------------------------------------------------- page components
def apply(page_title: str, icon: str = ":material/insights:", layout: str = "wide", sidebar: str = "expanded") -> None:
    """Page config + fonts + CSS. Call first."""
    try:
        st.set_page_config(page_title=page_title, page_icon=icon, layout=layout, initial_sidebar_state=sidebar)
    except Exception:  # already configured (e.g. in tests)
        pass
    st.markdown(_CSS, unsafe_allow_html=True)


def _e(s) -> str:
    """Escape text for HTML and keep $ from turning into LaTeX in Streamlit markdown."""
    return _html.escape(str(s)).replace("$", "&#36;")


def masthead(title: str, subtitle: str, kicker: str = "Finance portfolio", meta: Optional[Dict[str, str]] = None,
             right: Optional[str] = None) -> None:
    """Publication-style header: kicker, serif title, one-line description, byline, optional meta row."""
    meta_html = ""
    if meta:
        meta_html = '<div class="ya-meta">' + "".join(
            f"<span>{_e(k)} <b>{_e(v)}</b></span>" for k, v in meta.items()) + "</div>"
    right_html = right if right is not None else (
        f'By <b>{AUTHOR}</b><br>Finance &amp; accounting portfolio<br>'
        f'<a href="{GITHUB}" target="_blank">github.com/Yasskik/portfolio</a>')
    st.markdown(f"""<div class="ya-mast"><div class="ya-kicker">{_e(kicker)}</div>
<div class="ya-mast-row"><div><h1 class="ya-title">{_e(title)}</h1><p class="ya-sub">{_e(subtitle)}</p></div>
<div class="ya-byline">{right_html}</div></div>{meta_html}<hr class="ya-rule"></div>""", unsafe_allow_html=True)


def sidebar_brand(title: str, tagline: str = "Yamen Agha · Finance portfolio") -> None:
    st.sidebar.markdown(f'<div class="ya-side-brand">{_e(title)}<span>{_e(tagline)}</span></div>', unsafe_allow_html=True)


def sidebar_section(title: str, container=None) -> None:
    (container or st.sidebar).markdown(f'<div class="ya-side-h">{_e(title)}</div>', unsafe_allow_html=True)


def section(title: str, caption: str = "", kicker: str = "", container=None) -> None:
    cap = f"<p>{_e(caption)}</p>" if caption else ""
    k = f'<span class="ya-section-k">{_e(kicker)}</span>' if kicker else "<span></span>"
    (container or st).markdown(f'<div class="ya-section"><h3>{_e(title)}</h3>{k}{cap}</div>', unsafe_allow_html=True)


def chip(text: str, tone_: str = "neutral", arrow: Optional[bool] = None) -> str:
    """Delta chip. The arrow is shown for signed numbers (+4.2%, −3.1%) unless arrow=False."""
    t = str(text).strip()
    if arrow is None:
        arrow = t[:1] in "+−-" and t[1:2].isdigit()
    arrow = {"pos": "▲ ", "neg": "▼ "}.get(tone_, "") if arrow else ""
    return f'<span class="ya-chip {tone_}">{arrow}{_e(text)}</span>'


def kpis(cards: Sequence[dict], cols: Optional[int] = None, container=None) -> None:
    """Equal-width, equal-height KPI cards in one grid.
    card = dict(label, value, delta=None, tone='neutral'|'pos'|'neg'|'warn'|'accent', note=None, accent=None)."""
    n = cols or len(cards)
    out = []
    for c in cards:
        t = c.get("tone", "neutral")
        bar = c.get("accent") or {"pos": POS, "neg": NEG, "warn": WARN}.get(t, INK)
        foot = ""
        if c.get("delta"):
            foot += chip(c["delta"], t, c.get("arrow"))
        if c.get("note"):
            foot += f"<span>{_e(c['note'])}</span>"
        vcls = c.get("value_tone", "")
        n_chars = len(str(c["value"]))
        vcls += " sm" if 10 < n_chars <= 13 else (" xs" if n_chars > 13 else "")
        out.append(f'<div class="ya-kpi" style="--kpi-accent:{bar}"><div class="ya-kpi-label" title="{_e(c["label"])}">{_e(c["label"])}</div>'
                   f'<div class="ya-kpi-value {vcls}" title="{_e(c["value"])}">{_e(c["value"])}</div>'
                   f'<div class="ya-kpi-foot">{foot}</div></div>')
    (container or st).markdown(f'<div class="ya-kpis" style="grid-template-columns:repeat({n}, minmax(0, 1fr))">'
                               + "".join(out) + "</div>", unsafe_allow_html=True)


def callout(text: str, kind: str = "info", title: str = "", container=None) -> None:
    c = {"info": ACCENT, "pos": POS, "neg": NEG, "warn": WARN, "success": POS, "error": NEG}.get(kind, ACCENT)
    t = f'<b class="t">{_e(title)}</b>' if title else ""
    (container or st).markdown(f'<div class="ya-callout" style="--c:{c}">{t}{_e(text)}</div>', unsafe_allow_html=True)


def callout_html(html: str, kind: str = "info", title: str = "", container=None) -> None:
    """Like callout() but the body is trusted HTML (bold terms, formulas)."""
    c = {"info": ACCENT, "pos": POS, "neg": NEG, "warn": WARN, "success": POS, "error": NEG}.get(kind, ACCENT)
    t = f'<b class="t">{_e(title)}</b>' if title else ""
    (container or st).markdown(f'<div class="ya-callout" style="--c:{c}">{t}{html}</div>', unsafe_allow_html=True)


def card(title: str, body_html: str, container=None) -> None:
    (container or st).markdown(f'<div class="ya-card"><h4>{_e(title)}</h4>{body_html}</div>', unsafe_allow_html=True)


def subhead(title: str, note: str = "", container=None) -> None:
    n = f'<div class="ya-subhead-n">{_e(note)}</div>' if note else '<div class="ya-subhead-n"></div>'
    (container or st).markdown(f'<div class="ya-subhead">{_e(title)}</div>{n}', unsafe_allow_html=True)


def spacer(px: int = 16, container=None) -> None:
    (container or st).markdown(f'<div class="ya-spacer" style="--h:{int(px)}px"></div>', unsafe_allow_html=True)


def footer(note: str = "Educational project, not investment advice.") -> None:
    st.markdown(f"""<div class="ya-footer"><div>© 2026 <b style="color:{INK}">{AUTHOR}</b> · {_e(note)}</div>
<div class="r"><a href="{GITHUB}" target="_blank">github.com/Yasskik/portfolio</a></div></div>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- tables
Fmt = Union[str, Callable[[float], str], None]


def _fmt_cell(v, f: Fmt):
    if isinstance(v, str):
        return v, ""
    if not _ok(v):
        return "n/a" if v is not None else "", "na"
    v = float(v)
    if callable(f):
        s = f(v)
    elif f == "pct":
        s = pct(v)
    elif f == "pct_signed":
        s = pct(v, signed=True)
    elif f == "money":
        s = money(v)
    elif f and f.startswith("acct"):
        s = acct(v, int(f[4:] or 0))
    elif f and f.startswith("num"):
        s = num(v, int(f[3:] or 2))
    else:
        s = acct(v, 1)
    cls = "neg" if v < 0 and any(ch in s for ch in "(−-") else ""
    return s, cls


def html_table(df, fmt: Union[Fmt, Dict[str, Fmt]] = "acct1", row_fmt: Optional[Dict[str, Fmt]] = None,
               row_styles: Optional[Dict[str, str]] = None, max_height: Optional[int] = None,
               index_label: str = "", highlight: Optional[Iterable[tuple]] = None, color_positive: bool = False,
               container=None) -> None:
    """Render a DataFrame as a publication table.
    fmt: one format for all cells, or {column: format}; row_fmt: {row label: format} (wins over column formats).
    Formats: 'acct0'/'acct1'/'acct2' (accounting, negatives in red parentheses), 'pct', 'pct_signed', 'money',
    'num2', or a callable. row_styles: {row label: 'total'|'grand'|'sub'|'head'}."""
    row_fmt, row_styles = row_fmt or {}, row_styles or {}
    hl = set(highlight or [])
    head = f"<th>{_e(index_label)}</th>" + "".join(f"<th>{_e(c)}</th>" for c in df.columns)
    body = []
    for idx, row in df.iterrows():
        cls = row_styles.get(str(idx), "")
        tds = [f"<td>{_e(idx)}</td>"]
        for col, v in row.items():
            f = row_fmt.get(str(idx)) or (fmt.get(str(col)) if isinstance(fmt, dict) else fmt)
            s, c = _fmt_cell(v, f)
            if color_positive and not c and _ok(v) and float(v) > 0:
                c = "pos"
            if (str(idx), str(col)) in hl:
                c += " hl"
            tds.append(f'<td class="{c}">{_e(s)}</td>')
        body.append(f'<tr class="{cls}">' + "".join(tds) + "</tr>")
    style = f' style="max-height:{int(max_height)}px"' if max_height else ""
    (container or st).markdown(f'<div class="ya-tablewrap"{style}><table class="ya-table"><thead><tr>{head}</tr></thead>'
                               f'<tbody>{"".join(body)}</tbody></table></div>', unsafe_allow_html=True)


def styler(df, fmt: Union[Fmt, Dict[str, Fmt]] = "acct1"):
    """pandas Styler for st.dataframe: accounting formats, red negatives, right-aligned tabular numbers."""
    def f_for(col):
        return fmt.get(str(col)) if isinstance(fmt, dict) else fmt

    fmts = {c: (lambda v, _f=f_for(c): _fmt_cell(v, _f)[0]) for c in df.columns}
    sty = df.style.format(fmts)

    def neg(v):
        return f"color:{NEG};" if _ok(v) and not isinstance(v, str) and float(v) < 0 else ""

    try:
        sty = sty.map(neg)
    except AttributeError:  # pandas < 2.1
        sty = sty.applymap(neg)
    return sty.set_properties(**{"text-align": "right", "font-variant-numeric": "tabular-nums"})


# ----------------------------------------------------------------------------- charts
def style_fig(fig: go.Figure, title: str = "", subtitle: str = "", height: int = 400, yfmt: Optional[str] = None,
              xfmt: Optional[str] = None, ytitle: Optional[str] = None, xtitle: Optional[str] = None,
              legend: bool = True, hovermode: Optional[str] = None) -> go.Figure:
    upd = dict(template="ledger", height=height, showlegend=legend)
    margin = dict(t=88 if title else 24, b=88 if legend else 48)
    if title:
        upd["title"] = dict(text=title, subtitle=dict(text=subtitle) if subtitle else None)
    if "yaxis2" in fig.layout and fig.layout.yaxis2.overlaying:
        margin["r"] = 84
    if any(getattr(tr, "type", "") == "heatmap" for tr in fig.data):
        margin["r"] = 120
    upd["margin"] = margin
    if hovermode:
        upd["hovermode"] = hovermode
    fig.update_layout(**upd)
    if yfmt:
        fig.update_yaxes(tickformat=yfmt)
    if xfmt:
        fig.update_xaxes(tickformat=xfmt)
    if ytitle is not None:
        fig.update_yaxes(title_text=ytitle)
    if xtitle is not None:
        fig.update_xaxes(title_text=xtitle)
    return fig


def chart(fig: go.Figure, key: Optional[str] = None, container=None) -> None:
    """Render with the ledger template (Streamlit's own chart theme is switched off so ours is used)."""
    if fig.layout.paper_bgcolor is None:
        fig.update_layout(paper_bgcolor=SURFACE)
    if fig.layout.plot_bgcolor is None:
        fig.update_layout(plot_bgcolor=SURFACE)
    (container or st).plotly_chart(fig, theme=None, width="stretch", config=CHART_CONFIG, key=key)


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def bar_colors(values: Sequence[float], good_if_positive: bool = True) -> List[str]:
    return [color_for(v, good_if_positive) if _ok(v) and float(v) != 0 else MUTED for v in values]


def config_toml() -> str:
    """The matching .streamlit/config.toml (written into each project by sync_theme.py)."""
    pal = ", ".join(f'"{c}"' for c in PALETTE)
    inter = "Inter:https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    serif = ("Source Serif 4:https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;"
             "8..60,600;8..60,700&display=swap")
    return f"""# Generated from ui_theme.py tokens by finance/_shared/sync_theme.py - edit the tokens, not this file.
[theme]
base = "light"
primaryColor = "{ACCENT}"
backgroundColor = "{PAPER}"
secondaryBackgroundColor = "{SURFACE_2}"
textColor = "{INK}"
linkColor = "{ACCENT}"
redColor = "{NEG}"
greenColor = "{POS}"
orangeColor = "{WARN}"
blueColor = "{ACCENT_2}"
borderColor = "{HAIRLINE}"
dataframeBorderColor = "{HAIRLINE}"
dataframeHeaderBackgroundColor = "{SURFACE_2}"
showWidgetBorder = true
showSidebarBorder = true
baseRadius = "6px"
buttonRadius = "6px"
font = "{inter}"
headingFont = "{serif}"
chartCategoricalColors = [{pal}]

[theme.sidebar]
backgroundColor = "{SURFACE_2}"
secondaryBackgroundColor = "{SURFACE}"

[server]
headless = true

[browser]
gatherUsageStats = false

[client]
toolbarMode = "viewer"
"""
