"""
Report Export Module (report_export.py)
--------------------------------------
Generates publication-quality PDF and Markdown financial health reports.
The PDF uses ReportLab to create an institutional-grade executive summary
suitable for inclusion in an accounting/finance portfolio.
"""

from __future__ import annotations
import io
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)

from analyzer import FinancialAnalyzer, _safe_float

PCT_ROWS = {"Gross Margin", "Operating Margin", "Net Profit Margin", "Effective Tax Rate", "Return on Assets (ROA)",
            "ROA (avg. assets)", "Return on Equity (ROE)", "ROE (avg. equity)", "Return on Invested Capital (ROIC)",
            "FCF Margin", "Capex / Revenue", "3-Step DuPont ROE", "5-Step DuPont ROE", "Actual Reported ROE",
            "Operating Margin (EBIT / Rev)", "Revenue YoY Growth", "Operating Income YoY Growth",
            "Net Income YoY Growth", "Diluted EPS YoY Growth", "Free Cash Flow YoY Growth"}
DAY_ROWS = {"Days Sales Outstanding (DSO)", "Days Inventory Outstanding (DIO)", "Days Payable Outstanding (DPO)",
            "Cash Conversion Cycle (CCC)"}
MONEY_ROWS = {"Free Cash Flow", "Market Value of Equity"}
PLAIN_ROWS = {"Sloan Accrual Ratio", "Tax Burden (NI / EBT)", "Interest Burden (EBT / EBIT)"}


def fmt_value(row: str, val, currency: str = "USD") -> str:
    """Format one ratio value for display; missing -> 'n/a'."""
    if isinstance(val, str):
        return val
    v = _safe_float(val)
    if v is None:
        return "n/a"
    if row in PCT_ROWS:
        return f"{v * 100:.1f}%"
    if row in DAY_ROWS:
        return f"{v:.1f} days"
    if row in MONEY_ROWS:
        return f"{v / 1e9:,.2f}B {currency}"
    if row in PLAIN_ROWS or row.startswith("X") or "Z-Score" in row or "Z''" in row:
        return f"{v:.3f}" if (row in PLAIN_ROWS or row.startswith("X")) else f"{v:.2f}"
    if row[:2] in {f"{i}." for i in range(1, 10)} or row == "Total Piotroski F-Score":
        return f"{int(v)}"
    return f"{v:.2f}x"


def generate_markdown_report(analyzer: FinancialAnalyzer) -> str:
    """Generates an extensive, beautifully formatted Markdown financial health report."""
    data = analyzer.data
    years = data.years
    latest_y = years[-1] if years else "N/A"
    health_rep = analyzer.generate_health_report()

    liq = analyzer.calculate_liquidity_ratios()
    prof = analyzer.calculate_profitability_ratios()
    solv = analyzer.calculate_solvency_ratios()
    eff = analyzer.calculate_efficiency_ratios()
    cfq = analyzer.calculate_cash_flow_quality()
    growth = analyzer.calculate_growth_metrics()
    dupont = analyzer.calculate_dupont_analysis()
    altman = analyzer.calculate_altman_z_score()
    piotroski = analyzer.calculate_piotroski_f_score()

    lines = []
    lines.append(f"# Financial Health & Statement Analysis Report")
    lines.append(f"**Entity:** {data.company_name} ({data.symbol})  ")
    lines.append(f"**Sector / Industry:** {data.sector} | {data.industry}  ")
    lines.append(f"**Currency:** {data.currency}  ")
    lines.append(f"**Evaluation Period:** FY {years[0] if years else '-'} – FY {latest_y}  ")
    lines.append(f"**Report Generated:** {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M (UTC%z)')}  ")
    lines.append("**Data:** annual statements as reported by the source; ending balances unless a row says 'avg.'; "
                 "missing data is shown as n/a.  \n")
    lines.append("---")

    lines.append(f"## 1. Executive Diagnostic Summary")
    lines.append(f"**Overall Fundamental Rating:** `{health_rep['overall_status']}`\n")
    lines.append(f"> {health_rep['summary']}\n")

    lines.append("### Key Observations Summary:")
    lines.append(f"- **Identified Strengths:** {len(health_rep['strengths'])}")
    lines.append(f"- **Areas for Monitoring:** {len(health_rep['weaknesses'])}")
    lines.append(f"- **Critical Red Flags:** {len(health_rep['red_flags'])}\n")

    if health_rep["strengths"]:
        lines.append("#### Identified Strengths:")
        for s in health_rep["strengths"]:
            lines.append(f"- **[{s['category']}] {s['title']}**: {s['detail']}")
        lines.append("")

    if health_rep["weaknesses"]:
        lines.append("#### Areas for Monitoring & Weaknesses:")
        for w in health_rep["weaknesses"]:
            lines.append(f"- **[{w['category']}] {w['title']}**: {w['detail']}")
        lines.append("")

    if health_rep["red_flags"]:
        lines.append("#### Critical Red Flags & Solvency Alerts:")
        for r in health_rep["red_flags"]:
            lines.append(f"- 🚩 **[{r['category']}] {r['title']}**: {r['detail']}")
        lines.append("")
    else:
        lines.append("#### Solvency & Integrity Alerts:\n- None detected. The company passed all negative-accrual and severe credit risk screens.\n")

    lines.append("---")
    lines.append("## 2. Key Financial Ratios Dashboard\n")

    def _df_to_md(df, fmt_type=None):
        headers = ["Metric"] + [f"FY {y}" for y in df.columns]
        md_table = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
        for row_label, s in df.iterrows():
            cells = [str(row_label)] + [fmt_value(str(row_label), s.get(y), data.currency) for y in df.columns]
            md_table.append("| " + " | ".join(cells) + " |")
        return "\n".join(md_table) + "\n"

    lines.append("### Profitability Ratios")
    lines.append(_df_to_md(prof, "pct"))

    lines.append("### Liquidity Ratios")
    lines.append(_df_to_md(liq, "multiple"))

    lines.append("### Solvency & Capital Structure Ratios")
    lines.append(_df_to_md(solv, "multiple"))

    lines.append("### Working Capital & Operating Efficiency")
    lines.append(_df_to_md(eff, "multiple"))

    lines.append("### Cash Flow Quality & Accruals")
    lines.append(_df_to_md(cfq, "multiple"))

    lines.append("### Growth (Year over Year)")
    lines.append(_df_to_md(growth))

    lines.append("---")
    lines.append("## 3. DuPont Decomposition & Credit Scoring Models\n")

    lines.append("### 3-Step DuPont Analysis (ROE Decomposition)")
    lines.append(_df_to_md(dupont["three_step"], "multiple"))

    lines.append("### 5-Step DuPont Analysis (Operational, Tax & Interest Burden)")
    lines.append(_df_to_md(dupont["five_step"], "multiple"))

    lines.append("### Altman Z-Score Bankruptcy Assessment")
    lines.append(f"*{analyzer.ALTMAN_NOTE}*\n")
    lines.append(_df_to_md(altman, "ratio"))

    lines.append("### Piotroski F-Score 9-Point Breakdown")
    f_df = piotroski["detailed"]
    headers = ["Criterion"] + [f"FY {y}" for y in f_df.columns]
    f_table = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row_label, s in f_df.iterrows():
        row_cells = [str(row_label)]
        for y in f_df.columns:
            row_cells.append(fmt_value(str(row_label), s.get(y)))
        f_table.append("| " + " | ".join(row_cells) + " |")
    lines.append("\n".join(f_table) + "\n")

    if health_rep.get("notes"):
        lines.append("### Notes")
        for n in health_rep["notes"]:
            lines.append(f"- {n}")
        lines.append("")
    lines.append("---")
    lines.append("*Generated by the Financial Statement Analyzer (educational project, not investment advice).*")

    return "\n".join(lines)


def generate_pdf_report(analyzer: FinancialAnalyzer) -> bytes:
    """
    Generates an institutional PDF report using ReportLab.
    Returns bytes buffer.
    """
    data = analyzer.data
    years = data.years
    latest_y = years[-1] if years else ""
    health_rep = analyzer.generate_health_report()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom ReportLab Styles
    primary_color = colors.HexColor("#1F4E79")
    accent_color = colors.HexColor("#2F5597")
    light_bg = colors.HexColor("#F2F5F9")
    dark_gray = colors.HexColor("#333333")
    red_alert = colors.HexColor("#C00000")
    green_safe = colors.HexColor("#385723")

    style_title = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "DocSubTitle",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#595959"),
        spaceAfter=12,
    )
    style_h2 = ParagraphStyle(
        "SectionH2",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=6,
    )
    style_body = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark_gray,
        spaceAfter=6,
    )
    style_bullet = ParagraphStyle(
        "BulletItem",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=dark_gray,
        leftIndent=12,
        spaceAfter=4,
    )
    style_th = ParagraphStyle(
        "TableHead",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,  # Center
    )
    style_td = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=dark_gray,
        alignment=0,  # Left
    )
    style_td_r = ParagraphStyle(
        "TableCellR",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=dark_gray,
        alignment=2,  # Right
    )

    elements = []

    # Title & Header
    elements.append(Paragraph(f"{data.company_name} ({data.symbol})", style_title))
    header_meta = (
        f"<b>Sector:</b> {data.sector} | <b>Industry:</b> {data.industry} | <b>Currency:</b> {data.currency} | "
        f"<b>Periods:</b> FY {years[0] if years else '-'} – FY {latest_y} | <b>Date:</b> {datetime.now().strftime('%b %d, %Y')}"
    )
    elements.append(Paragraph(header_meta, style_subtitle))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=0, spaceAfter=10))

    # Overall Status Banner
    status_text = f"<b>DIAGNOSTIC STATUS:</b> {health_rep['overall_status'].upper()}"
    status_bg = {"green": colors.HexColor("#E2EFDA"), "blue": colors.HexColor("#DDEBF7"),
                 "red": colors.HexColor("#FCE4D6")}.get(health_rep.get("status_color"), colors.HexColor("#FFF2CC"))
    banner_table = Table([[Paragraph(f"<font size='10' color='#1F4E79'>{status_text}</font>", style_body)]], colWidths=[540])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), status_bg),
        ("BOX", (0, 0), (-1, -1), 1, primary_color),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, 10))

    # Executive Summary
    elements.append(Paragraph("Executive Financial Diagnostic", style_h2))
    elements.append(Paragraph(health_rep["summary"], style_body))
    elements.append(Spacer(1, 6))

    # Strengths, Weaknesses, Red Flags
    if health_rep["strengths"]:
        elements.append(Paragraph("<b>Identified Financial Strengths:</b>", style_body))
        for s in health_rep["strengths"][:4]:
            elements.append(Paragraph(f"• <b>[{s['category']}] {s['title']}:</b> {s['detail']}", style_bullet))
        elements.append(Spacer(1, 4))

    if health_rep["weaknesses"]:
        elements.append(Paragraph("<b>Areas for Monitoring & Weaknesses:</b>", style_body))
        for w in health_rep["weaknesses"][:3]:
            elements.append(Paragraph(f"• <b>[{w['category']}] {w['title']}:</b> {w['detail']}", style_bullet))
        elements.append(Spacer(1, 4))

    if health_rep["red_flags"]:
        elements.append(Paragraph("<b><font color='#C00000'>Red Flags:</font></b>", style_body))
        for r in health_rep["red_flags"][:3]:
            elements.append(Paragraph(f"• <b>[{r['category']}] {r['title']}:</b> {r['detail']}", style_bullet))
        elements.append(Spacer(1, 4))

    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D9D9D9"), spaceBefore=6, spaceAfter=8))

    # Key Ratios Table Function
    def _build_pdf_table(title, df, fmt_func=None):
        tbl_data = []
        # Header row
        header = [Paragraph("<b>Metric</b>", style_th)] + [Paragraph(f"<b>FY {y}</b>", style_th) for y in df.columns]
        tbl_data.append(header)

        for row_label, s in df.iterrows():
            row = [Paragraph(str(row_label), style_td)]
            for y in df.columns:
                row.append(Paragraph(fmt_value(str(row_label), s.get(y), data.currency), style_td_r))
            tbl_data.append(row)

        num_cols = len(df.columns) + 1
        col_w_metric = 220
        col_w_year = (540 - col_w_metric) / (num_cols - 1)
        col_widths = [col_w_metric] + [col_w_year] * (num_cols - 1)

        t = Table(tbl_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), accent_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
        ]))
        return KeepTogether([Paragraph(title, style_h2), t, Spacer(1, 8)])

    elements.append(_build_pdf_table("1. Profitability & Returns", analyzer.calculate_profitability_ratios()))
    elements.append(_build_pdf_table("2. Liquidity", analyzer.calculate_liquidity_ratios()))
    elements.append(_build_pdf_table("3. Leverage & Solvency", analyzer.calculate_solvency_ratios()))
    elements.append(_build_pdf_table("4. Efficiency & Working Capital (365-day year)", analyzer.calculate_efficiency_ratios()))
    elements.append(_build_pdf_table("5. Cash-Flow Quality", analyzer.calculate_cash_flow_quality()))
    dupont = analyzer.calculate_dupont_analysis()
    elements.append(_build_pdf_table("6. DuPont Analysis (3-step)", dupont["three_step"]))
    elements.append(_build_pdf_table("7. DuPont Analysis (5-step)", dupont["five_step"]))
    altman = analyzer.calculate_altman_z_score()
    elements.append(_build_pdf_table("8. Altman Z-Score", altman))
    elements.append(Paragraph(analyzer.ALTMAN_NOTE, style_bullet))
    elements.append(_build_pdf_table("9. Piotroski F-Score", analyzer.calculate_piotroski_f_score()["detailed"]))
    for n in health_rep.get("notes", []):
        elements.append(Paragraph(n, style_bullet))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Ending balances unless a row says 'avg.'. EBIT = operating income. Missing data = n/a. "
                              "Educational project, not investment advice.", style_bullet))

    doc.build(elements)
    return buf.getvalue()
