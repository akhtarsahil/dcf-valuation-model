# utils/helpers.py
"""
General-purpose helper functions.

  - PDF report generation (ReportLab)
  - Formatting utilities for tables and output
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List, TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)

if TYPE_CHECKING:
    import pandas as pd
    from utils.finance import TickerData
    from models.dcf import DCFResult
    from models.valuation import ScenarioResult


# ──────────────────────────────────────────────────────────────────────
# Color palette
# ──────────────────────────────────────────────────────────────────────

_NAVY = colors.HexColor("#0F1B2D")
_DARK_BG = colors.HexColor("#1A2332")
_ACCENT = colors.HexColor("#3B82F6")
_ACCENT_LIGHT = colors.HexColor("#60A5FA")
_GREEN = colors.HexColor("#22C55E")
_RED = colors.HexColor("#EF4444")
_AMBER = colors.HexColor("#F59E0B")
_GRAY_TEXT = colors.HexColor("#6B7280")
_LIGHT_GRAY = colors.HexColor("#F3F4F6")
_WHITE = colors.white
_BLACK = colors.black

# Table styles
_HDR_BG = colors.HexColor("#1E3A5F")
_HDR_TEXT = colors.white
_ROW_ALT = colors.HexColor("#F0F4F8")
_GRID_COLOR = colors.HexColor("#D1D5DB")


# ──────────────────────────────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────────────────────────────

def _fc(val: float, billions: bool = False) -> str:
    """Format currency."""
    if billions:
        return f"${val / 1e9:,.2f}B"
    if abs(val) >= 1e6:
        return f"${val / 1e6:,.1f}M"
    return f"${val:,.2f}"


def _fp(val: float) -> str:
    """Format percentage."""
    return f"{val * 100:.1f}%"


# ──────────────────────────────────────────────────────────────────────
# PDF Report Generator
# ──────────────────────────────────────────────────────────────────────

def _make_table(data, col_widths=None, header=True):
    """Build a styled ReportLab table."""
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)

    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), _BLACK),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, _GRID_COLOR),
    ]

    if header:
        style_cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), _HDR_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), _HDR_TEXT),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
        ]

    # Alternate row shading
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _ROW_ALT))

    t.setStyle(TableStyle(style_cmds))
    return t


def generate_pdf_report(
    ticker_data: "TickerData",
    dcf_result: "DCFResult",
    scenarios: List["ScenarioResult"],
    sensitivity_df: "pd.DataFrame",
    output_dir: str = ".",
) -> str:
    """Generate a professional PDF DCF valuation report.

    Args:
        ticker_data:     Live market data for the ticker.
        dcf_result:      Base-case DCF result.
        scenarios:       List of ScenarioResult (Bull, Base, Bear).
        sensitivity_df:  WACC x TGR sensitivity DataFrame.
        output_dir:      Directory to write the PDF into.

    Returns:
        Absolute path to the generated PDF file.
    """
    ticker = ticker_data.ticker
    filename = f"{ticker}_DCF_Report.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=_NAVY,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=_GRAY_TEXT,
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=_ACCENT,
        spaceBefore=18,
        spaceAfter=8,
        fontName="Helvetica-Bold",
        borderWidth=0,
        borderPadding=0,
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#374151"),
        leading=14,
        spaceAfter=6,
    )
    metric_style = ParagraphStyle(
        "MetricLarge",
        parent=styles["Normal"],
        fontSize=18,
        textColor=_NAVY,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    label_style = ParagraphStyle(
        "MetricLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=_GRAY_TEXT,
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    elements = []
    now = datetime.now().strftime("%B %d, %Y at %H:%M")

    # ── TITLE ────────────────────────────────────────────────────────
    elements.append(Paragraph(
        f"DCF Valuation Report",
        title_style,
    ))
    elements.append(Paragraph(
        f"{ticker_data.company_name} ({ticker}) &bull; {now}",
        subtitle_style,
    ))
    elements.append(HRFlowable(
        width="100%", thickness=2, color=_ACCENT, spaceAfter=12,
    ))

    # ── KEY METRICS (top-level verdict) ──────────────────────────────
    intrinsic = dcf_result.implied_share_price
    current = ticker_data.current_price
    mos = (intrinsic - current) / intrinsic if intrinsic > 0 else -1.0

    if mos > 0.15:
        verdict = "UNDERVALUED"
        verdict_color = _GREEN
    elif mos > 0:
        verdict = "FAIRLY VALUED"
        verdict_color = _AMBER
    else:
        verdict = "OVERVALUED"
        verdict_color = _RED

    verdict_data = [
        [
            Paragraph(f"${intrinsic:,.2f}", metric_style),
            Paragraph(f"${current:,.2f}", metric_style),
            Paragraph(f"{mos:.1%}", metric_style),
            Paragraph(
                f"<font color='{verdict_color.hexval()}'><b>{verdict}</b></font>",
                ParagraphStyle("v", parent=metric_style, textColor=verdict_color),
            ),
        ],
        [
            Paragraph("Intrinsic Value", label_style),
            Paragraph("Market Price", label_style),
            Paragraph("Margin of Safety", label_style),
            Paragraph("Recommendation", label_style),
        ],
    ]
    verdict_table = Table(verdict_data, colWidths=[1.7 * inch] * 4)
    verdict_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_GRAY),
        ("BOX", (0, 0), (-1, -1), 1, _GRID_COLOR),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, _GRID_COLOR),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 12))

    # ── SECTION 1: Company Snapshot ──────────────────────────────────
    elements.append(Paragraph("1. Company Snapshot", section_style))

    snapshot_data = [
        ["Metric", "Value"],
        ["Ticker", ticker],
        ["Company Name", ticker_data.company_name],
        ["Current Price", f"${current:,.2f}"],
        ["Market Cap", _fc(ticker_data.market_cap, True)],
        ["Shares Outstanding", f"{ticker_data.shares_outstanding / 1e9:,.2f}B"],
        ["Beta", f"{ticker_data.beta:.2f}"],
        ["Latest Revenue (LTM)", _fc(ticker_data.latest_revenue, True)],
        ["EBIT Margin", _fp(ticker_data.latest_ebit_margin)],
        ["Total Debt", _fc(ticker_data.total_debt, True)],
        ["Total Cash", _fc(ticker_data.total_cash, True)],
        ["Net Debt", _fc(ticker_data.net_debt, True)],
    ]
    elements.append(_make_table(snapshot_data, col_widths=[2.5 * inch, 4.3 * inch]))
    elements.append(Spacer(1, 8))

    # ── SECTION 2: Model Assumptions ─────────────────────────────────
    elements.append(Paragraph("2. Model Assumptions", section_style))

    w = dcf_result.wacc_result
    elements.append(Paragraph(
        f"<b>Discount Rate (WACC):</b> {_fp(w.wacc)} &mdash; "
        f"Cost of Equity {_fp(w.cost_of_equity)} (CAPM), "
        f"Cost of Debt {_fp(w.cost_of_debt_aftertax)} (after-tax), "
        f"Weights E/D = {_fp(w.equity_ratio)}/{_fp(w.debt_ratio)}",
        body_style,
    ))
    elements.append(Paragraph(
        f"<b>Terminal Growth Rate:</b> {_fp(dcf_result.terminal_growth_rate)}",
        body_style,
    ))

    # Forecast assumptions table
    fi = dcf_result.forecast_result.inputs
    forecast_header = ["Driver", "Yr 1", "Yr 2", "Yr 3", "Yr 4", "Yr 5"]
    forecast_data = [
        forecast_header,
        ["Rev. Growth"] + [_fp(g) for g in fi.revenue_growth_rates],
        ["EBIT Margin"] + [_fp(m) for m in fi.ebit_margins],
        ["Tax Rate"] + [_fp(t) for t in fi.tax_rates],
        ["D&A (% Rev)"] + [_fp(d) for d in fi.depreciation_pct_of_rev],
        ["CapEx (% Rev)"] + [_fp(c) for c in fi.capex_pct_of_rev],
        ["NWC (% dRev)"] + [_fp(n) for n in fi.nwc_pct_of_rev_change],
    ]
    elements.append(_make_table(
        forecast_data,
        col_widths=[1.5 * inch] + [1.1 * inch] * 5,
    ))
    elements.append(Spacer(1, 8))

    # ── SECTION 3: FCF Projections ───────────────────────────────────
    elements.append(Paragraph("3. Projected Free Cash Flows", section_style))

    fcf_header = ["Year", "Revenue", "EBIT", "NOPAT", "FCF", "PV(FCF)"]
    fcf_data = [fcf_header]
    for dy in dcf_result.discounted_years:
        proj = dcf_result.forecast_result.projections[dy.year - 1]
        fcf_data.append([
            f"Year {dy.year}",
            _fc(proj.revenue),
            _fc(proj.ebit),
            _fc(proj.nopat),
            _fc(dy.fcf),
            _fc(dy.present_value_fcf),
        ])
    elements.append(_make_table(
        fcf_data,
        col_widths=[0.8 * inch] + [1.24 * inch] * 5,
    ))
    elements.append(Spacer(1, 8))

    # ── SECTION 4: Valuation Bridge ──────────────────────────────────
    elements.append(Paragraph("4. Valuation Bridge", section_style))

    bridge_data = [
        ["Component", "Value"],
        ["NPV of Projected FCFs", _fc(dcf_result.npv_of_fcfs, True)],
        ["Terminal Value (Gordon Growth)", _fc(dcf_result.terminal_value, True)],
        ["PV of Terminal Value", _fc(dcf_result.pv_of_terminal_value, True)],
        ["Enterprise Value", _fc(dcf_result.enterprise_value, True)],
        ["Less: Net Debt", f"({_fc(dcf_result.net_debt, True)})"],
        ["Equity Value", _fc(dcf_result.equity_value, True)],
        ["Shares Outstanding", f"{ticker_data.shares_outstanding / 1e9:,.2f}B"],
        ["Implied Share Price", f"${intrinsic:,.2f}"],
    ]
    elements.append(_make_table(bridge_data, col_widths=[3.4 * inch, 3.4 * inch]))
    elements.append(Spacer(1, 8))

    # ── SECTION 5: Scenario Analysis ─────────────────────────────────
    elements.append(Paragraph("5. Scenario Analysis", section_style))

    elements.append(Paragraph(
        "The DCF model is stress-tested under three scenarios to bound "
        "the range of plausible outcomes. Revenue growth, operating margins, "
        "and WACC are each adjusted to reflect optimistic, neutral, and "
        "pessimistic views.",
        body_style,
    ))

    sc_header = ["Scenario", "Intrinsic Value", "Enterprise Value", "WACC", "Margin of Safety"]
    sc_data = [sc_header]
    for s in scenarios:
        r = s.dcf_result
        iv = r.implied_share_price
        ev = r.enterprise_value
        sc_mos = (iv - current) / iv if iv > 0 else -1.0
        sc_data.append([
            s.name,
            f"${iv:,.2f}",
            _fc(ev, True),
            _fp(r.wacc_result.wacc),
            f"{sc_mos:.1%}",
        ])
    elements.append(_make_table(
        sc_data,
        col_widths=[1.1 * inch, 1.4 * inch, 1.5 * inch, 1.1 * inch, 1.5 * inch],
    ))
    elements.append(Spacer(1, 8))

    # ── SECTION 6: Sensitivity Matrix ────────────────────────────────
    elements.append(Paragraph("6. Sensitivity Analysis (WACC vs. Terminal Growth)", section_style))

    elements.append(Paragraph(
        "Each cell shows the implied share price for the given WACC and "
        "terminal growth rate combination, holding all other assumptions constant.",
        body_style,
    ))

    # Convert DataFrame to table
    sens_header = ["WACC \\ TGR"] + [str(c) for c in sensitivity_df.columns]
    sens_data = [sens_header]
    for wacc_label, row in sensitivity_df.iterrows():
        row_cells = [str(wacc_label)]
        for val in row.values:
            if val != val:  # NaN check
                row_cells.append("N/A")
            else:
                row_cells.append(f"${val:,.0f}")
        sens_data.append(row_cells)

    sens_col_w = 6.8 / len(sens_header)
    elements.append(_make_table(
        sens_data,
        col_widths=[sens_col_w * inch] * len(sens_header),
    ))
    elements.append(Spacer(1, 12))

    # ── SECTION 7: Conclusion ────────────────────────────────────────
    elements.append(Paragraph("7. Conclusion", section_style))

    bull_iv = scenarios[0].dcf_result.implied_share_price if scenarios else intrinsic
    bear_iv = scenarios[-1].dcf_result.implied_share_price if scenarios else intrinsic

    elements.append(Paragraph(
        f"Based on our discounted cash flow analysis, we estimate an intrinsic "
        f"value of <b>${intrinsic:,.2f}</b> per share for {ticker_data.company_name}, "
        f"compared to the current market price of <b>${current:,.2f}</b>. "
        f"This implies a margin of safety of <b>{mos:.1%}</b>.",
        body_style,
    ))
    elements.append(Paragraph(
        f"Under our scenario analysis, the implied value ranges from "
        f"<b>${bear_iv:,.2f}</b> (Bear) to <b>${bull_iv:,.2f}</b> (Bull), "
        f"providing a valuation corridor for the stock.",
        body_style,
    ))
    elements.append(Paragraph(
        f"<b>Recommendation: <font color='{verdict_color.hexval()}'>"
        f"{verdict}</font></b>",
        body_style,
    ))

    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=_GRAY_TEXT, spaceAfter=6,
    ))
    elements.append(Paragraph(
        f"<i>Report generated on {now}. This analysis is for informational "
        f"purposes only and does not constitute investment advice. Past "
        f"performance is not indicative of future results.</i>",
        ParagraphStyle(
            "Disclaimer", parent=body_style,
            fontSize=8, textColor=_GRAY_TEXT,
        ),
    ))

    # ── Build the PDF ────────────────────────────────────────────────
    doc.build(elements)
    return os.path.abspath(filepath)
